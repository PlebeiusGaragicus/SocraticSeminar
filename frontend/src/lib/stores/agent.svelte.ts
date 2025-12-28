// Agent store for LangGraph streaming with tool interrupt handling
// Uses the langgraph service for communication and handles state reactively

import type { 
  ToolCall, 
  ToolCallWithStatus,
  ToolResult,
  ProjectFile,
  Message as LocalMessage,
  HITLInterrupt,
  HITLDecision,
  HITLResumeResponse
} from './types.js';
import { threadStore } from './threads.svelte.js';
import { artifactStore } from './artifacts.svelte.js';
import { assistantStore } from './assistants.svelte.js';
import { 
  submitMessage as submitToLangGraph,
  resumeWithHITLDecisions,
  setToolExecutor,
  checkHealth,
  getClient,
  type Message as LangGraphMessage
} from '$lib/services/langgraph.js';
import { executeToolCall } from '$lib/services/tool-executor.js';

// Initialize the tool executor in the langgraph service
setToolExecutor(executeToolCall);

// =============================================================================
// MESSAGE CONVERSION
// =============================================================================

/**
 * Convert LangGraph messages to local message format.
 * Filters out tool messages (they're displayed as part of AI messages).
 */
function convertLangGraphMessages(
  lgMessages: LangGraphMessage[],
  threadId: string
): Omit<LocalMessage, 'id' | 'createdAt'>[] {
  const localMessages: Omit<LocalMessage, 'id' | 'createdAt'>[] = [];
  
  for (let i = 0; i < lgMessages.length; i++) {
    const msg = lgMessages[i];
    
    if (msg.type === 'human') {
      localMessages.push({
        threadId,
        role: 'user',
        content: typeof msg.content === 'string' ? msg.content : JSON.stringify(msg.content)
      });
    } else if (msg.type === 'ai') {
      const content = typeof msg.content === 'string' ? msg.content : '';
      const toolCalls = (msg as { tool_calls?: ToolCall[] }).tool_calls;
      
      // Only add if there's content or tool calls
      if (content || (toolCalls && toolCalls.length > 0)) {
        localMessages.push({
          threadId,
          role: 'assistant',
          content,
          toolCalls: toolCalls
        });
      }
    }
    // Skip 'tool' messages - they're displayed as part of the AI message's tool calls
  }
  
  return localMessages;
}

// =============================================================================
// REACTIVE STATE
// =============================================================================

let isStreaming = $state(false);
let isInterrupted = $state(false);
let threadId = $state<string | null>(null);
let error = $state<string | null>(null);
let pendingToolCalls = $state<ToolCallWithStatus[]>([]);
let streamingContent = $state<string>('');

// Track LangGraph messages for the current conversation
let langGraphMessages = $state<LangGraphMessage[]>([]);

// Human-in-the-loop interrupt state
let hitlInterrupt = $state<HITLInterrupt | null>(null);
let hitlInterruptId = $state<string | null>(null);
let awaitingHumanResponse = $state(false);

// Store the local thread ID for resuming after HITL
let currentLocalThreadId = $state<string | null>(null);

// =============================================================================
// HELPERS
// =============================================================================

// Build project files metadata for agent context
function buildProjectFiles(): ProjectFile[] {
  const artifacts = artifactStore.artifacts;
  return artifacts.map(artifact => ({
    id: artifact.id,
    title: artifact.versions[artifact.currentVersionIndex]?.title || 'Untitled',
    file_type: 'artifact' as const
  }));
}

// Update streaming content (triggers reactivity)
function setStreamingContent(content: string) {
  streamingContent = content;
}

// Update pending tool calls (triggers reactivity)
function setPendingToolCalls(calls: ToolCallWithStatus[]) {
  pendingToolCalls = [...calls];
}

// =============================================================================
// MAIN SEND MESSAGE FUNCTION
// =============================================================================

async function sendMessage(
  message: string,
  langGraphThreadId: string | null,
  localThreadId: string
): Promise<{ langGraphThreadId: string }> {
  // Get the selected assistant ID
  const assistantId = assistantStore.selectedAssistantId || 'seminar_agent';
  
  // Get project ID from current thread
  const thread = threadStore.threads.find(t => t.id === localThreadId);
  const projectId = thread?.projectId || '';
  
  // Reset state
  isStreaming = true;
  isInterrupted = false;
  threadId = langGraphThreadId;
  error = null;
  hitlInterrupt = null;
  hitlInterruptId = null;
  awaitingHumanResponse = false;
  currentLocalThreadId = localThreadId;
  setPendingToolCalls([]);
  setStreamingContent('');
  
  // Initialize langGraphMessages with user message for immediate display
  // This will be replaced by server state via onMessagesSync
  langGraphMessages = [{
    type: 'human',
    content: message,
    id: `optimistic-user-${Date.now()}`
  } as LangGraphMessage];
  
  // Track which AI message ID we're streaming to
  let currentAiMessageId: string | null = null;
  let knownAiMessageIds = new Set<string>();
  
  try {
    // Add user message to local store (persisted)
    threadStore.addMessage(localThreadId, {
      role: 'user',
      content: message
    });
    
    console.log('[Agent] Starting stream for thread:', langGraphThreadId || 'new');
    
    // Submit to LangGraph with callbacks
    const result = await submitToLangGraph(
      message,
      {
        threadId: langGraphThreadId,
        assistantId,
        projectId,
        projectFiles: buildProjectFiles(),
      },
      {
        onToken: (token) => {
          // Append token to streaming content
          streamingContent += token;
        },
        
        onIterationStart: (iteration) => {
          // Reset for new iteration (after tool execution)
          if (currentAiMessageId) {
            knownAiMessageIds.add(currentAiMessageId);
          }
          console.log(`[Agent] Iteration ${iteration} starting`);
          currentAiMessageId = null;
          streamingContent = '';
        },
        
        onMessagesSync: (messages) => {
          // Sync with server state
          langGraphMessages = [...messages];
          
          // Find the latest AI message
          const lastAi = messages.findLast(m => m.type === 'ai');
          if (lastAi && lastAi.id) {
            if (!knownAiMessageIds.has(lastAi.id)) {
              currentAiMessageId = lastAi.id;
              // Use server content if we haven't started streaming yet
              if (!streamingContent) {
                const serverContent = typeof lastAi.content === 'string' ? lastAi.content : '';
                streamingContent = serverContent;
              }
            }
          }
        },
        
        onToolCall: (toolCalls) => {
          console.log('[Agent] Tool calls detected:', toolCalls.map(t => t.name));
          isInterrupted = true;
          setPendingToolCalls(toolCalls.map(tc => ({
            ...tc,
            status: 'pending' as const
          })));
        },
        
        onToolExecuting: (toolCalls) => {
          console.log('[Agent] Executing tools:', toolCalls.map(t => t.name));
          setPendingToolCalls(toolCalls.map(tc => ({
            ...tc,
            status: 'executing' as const
          })));
        },
        
        onToolComplete: (results) => {
          console.log('[Agent] Tools completed:', results.map(r => ({ id: r.tool_call_id, hasError: !!r.error })));
          // Update tool calls with results
          setPendingToolCalls(pendingToolCalls.map(tc => {
            const result = results.find(r => r.tool_call_id === tc.id);
            return {
              ...tc,
              status: result?.error ? 'error' as const : 'completed' as const,
              result: result
            };
          }));
          // Clear interrupt state - agent is resuming
          isInterrupted = false;
        },
        
        onHITLInterrupt: (interrupt, interruptId) => {
          console.log('[Agent] HITL interrupt received:', interrupt.action_requests.map(a => a.name));
          hitlInterrupt = interrupt;
          hitlInterruptId = interruptId;
          awaitingHumanResponse = true;
          isInterrupted = true;
          // Keep streaming false since we're waiting for human input
          isStreaming = false;
        },
        
        onComplete: (finalMessages) => {
          console.log('[Agent] Stream completed. Messages:', finalMessages.length);
          langGraphMessages = [...finalMessages];
          
          // Convert and sync ALL messages from LangGraph to local store
          // This ensures we have the complete conversation history including
          // multiple AI messages from tool call iterations
          const convertedMessages = convertLangGraphMessages(finalMessages, localThreadId);
          threadStore.syncMessages(localThreadId, convertedMessages);
          
          isStreaming = false;
          isInterrupted = false;
          setPendingToolCalls([]);
          setStreamingContent('');
        },
        
        onError: (err) => {
          console.error('[Agent] Error:', err.message);
          error = err.message;
          isStreaming = false;
          isInterrupted = false;
          setPendingToolCalls([]);
          setStreamingContent('');
        },
        
        onThreadId: (id) => {
          threadId = id;
          console.log('[Agent] Thread ID assigned:', id);
        }
      }
    );
    
    return { langGraphThreadId: result.threadId };
    
  } catch (err) {
    const errorMessage = err instanceof Error ? err.message : 'Unknown error';
    console.error('[Agent] Error:', errorMessage);
    error = errorMessage;
    isStreaming = false;
    isInterrupted = false;
    setStreamingContent('');
    setPendingToolCalls([]);
    throw err;
  }
}

// =============================================================================
// HUMAN-IN-THE-LOOP RESPONSE
// =============================================================================

/**
 * Resume the agent after a HITL interrupt with the user's decisions.
 * 
 * @param decisions - Array of decisions for each action_request
 */
async function resumeWithDecisions(decisions: HITLDecision[]): Promise<void> {
  if (!threadId || !awaitingHumanResponse || !hitlInterruptId) {
    console.error('[Agent] Cannot resume: no active HITL interrupt');
    return;
  }
  
  const assistantId = assistantStore.selectedAssistantId || 'deeptutor';
  const localThreadId = currentLocalThreadId;
  const interruptId = hitlInterruptId;
  
  // Reset HITL state
  hitlInterrupt = null;
  hitlInterruptId = null;
  awaitingHumanResponse = false;
  isStreaming = true;
  isInterrupted = false;
  setStreamingContent('');
  
  const response: HITLResumeResponse = { decisions };
  console.log('[Agent] Resuming with HITL decisions:', decisions);
  
  try {
    await resumeWithHITLDecisions(
      threadId,
      interruptId,
      response,
      assistantId,
      {
        onToken: (token) => {
          streamingContent += token;
        },
        
        onMessagesSync: (messages) => {
          langGraphMessages = [...messages];
        },
        
        onToolCall: (toolCalls) => {
          console.log('[Agent] Tool calls detected after resume:', toolCalls.map(t => t.name));
          isInterrupted = true;
          setPendingToolCalls(toolCalls.map(tc => ({
            ...tc,
            status: 'pending' as const
          })));
        },
        
        onHITLInterrupt: (interrupt, newInterruptId) => {
          console.log('[Agent] Another HITL interrupt received:', interrupt.action_requests.map(a => a.name));
          hitlInterrupt = interrupt;
          hitlInterruptId = newInterruptId;
          awaitingHumanResponse = true;
          isInterrupted = true;
          isStreaming = false;
        },
        
        onComplete: (finalMessages) => {
          console.log('[Agent] Resumed stream completed. Messages:', finalMessages.length);
          langGraphMessages = [...finalMessages];
          
          // Sync messages to local store
          if (localThreadId) {
            const convertedMessages = convertLangGraphMessages(finalMessages, localThreadId);
            threadStore.syncMessages(localThreadId, convertedMessages);
          }
          
          isStreaming = false;
          isInterrupted = false;
          setPendingToolCalls([]);
          setStreamingContent('');
        },
        
        onError: (err) => {
          console.error('[Agent] Resume error:', err.message);
          error = err.message;
          isStreaming = false;
          isInterrupted = false;
          awaitingHumanResponse = false;
          setPendingToolCalls([]);
          setStreamingContent('');
        }
      }
    );
    
  } catch (err) {
    const errorMessage = err instanceof Error ? err.message : 'Unknown error';
    console.error('[Agent] Resume error:', errorMessage);
    error = errorMessage;
    isStreaming = false;
    isInterrupted = false;
    awaitingHumanResponse = false;
    setPendingToolCalls([]);
    setStreamingContent('');
    throw err;
  }
}

/**
 * Approve all actions in the current HITL interrupt.
 */
async function approveAllActions(): Promise<void> {
  if (!hitlInterrupt) return;
  
  const decisions: HITLDecision[] = hitlInterrupt.action_requests.map(() => ({
    type: 'approve' as const
  }));
  
  await resumeWithDecisions(decisions);
}

/**
 * Reject all actions in the current HITL interrupt.
 */
async function rejectAllActions(): Promise<void> {
  if (!hitlInterrupt) return;
  
  const decisions: HITLDecision[] = hitlInterrupt.action_requests.map(() => ({
    type: 'reject' as const
  }));
  
  await resumeWithDecisions(decisions);
}

/**
 * Dismiss the current HITL interrupt without responding.
 * This will leave the agent in an interrupted state.
 */
function dismissHITLInterrupt(): void {
  hitlInterrupt = null;
  hitlInterruptId = null;
  awaitingHumanResponse = false;
}

// =============================================================================
// UTILITY FUNCTIONS
// =============================================================================

function clearError(): void {
  error = null;
}

function resetStream(): void {
  isStreaming = false;
  isInterrupted = false;
  threadId = null;
  error = null;
  hitlInterrupt = null;
  hitlInterruptId = null;
  awaitingHumanResponse = false;
  currentLocalThreadId = null;
  setPendingToolCalls([]);
  setStreamingContent('');
  langGraphMessages = [];
}

// =============================================================================
// EXPORTS
// =============================================================================

export const agentStore = {
  // Reactive getters
  get streamingContent() { return streamingContent; },
  get isStreaming() { return isStreaming; },
  get isInterrupted() { return isInterrupted; },
  get pendingToolCalls() { return pendingToolCalls; },
  get error() { return error; },
  get threadId() { return threadId; },
  get langGraphMessages() { return langGraphMessages; },
  
  // Human-in-the-loop getters
  get hitlInterrupt() { return hitlInterrupt; },
  get awaitingHumanResponse() { return awaitingHumanResponse; },
  
  // Actions
  sendMessage,
  clearError,
  resetStream,
  checkHealth,
  getClient,
  
  // Human-in-the-loop actions
  resumeWithDecisions,
  approveAllActions,
  rejectAllActions,
  dismissHITLInterrupt
};
