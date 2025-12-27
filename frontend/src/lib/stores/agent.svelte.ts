// Agent store for LangGraph streaming with tool interrupt handling
// Uses the langgraph service for communication and handles state reactively

import type { Message } from '@langchain/langgraph-sdk';
import type { 
  ToolCall, 
  ToolCallWithStatus,
  ToolResult,
  ProjectFile
} from './types.js';
import { threadStore } from './threads.svelte.js';
import { artifactStore } from './artifacts.svelte.js';
import { assistantStore } from './assistants.svelte.js';
import { 
  submitMessage as submitToLangGraph,
  setToolExecutor,
  checkHealth,
  getClient
} from '$lib/services/langgraph.js';
import { executeToolCall } from '$lib/services/tool-executor.js';

// Initialize the tool executor in the langgraph service
setToolExecutor(executeToolCall);

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
let langGraphMessages = $state<Message[]>([]);

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
  setPendingToolCalls([]);
  setStreamingContent('');
  langGraphMessages = [];
  
  // Track which AI message ID we're streaming to
  let currentAiMessageId: string | null = null;
  let knownAiMessageIds = new Set<string>();
  
  try {
    // Add user message to local store
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
        
        onComplete: (finalMessages) => {
          console.log('[Agent] Stream completed. Messages:', finalMessages.length);
          langGraphMessages = [...finalMessages];
          
          // Extract the final assistant content
          const lastAiMessage = finalMessages.findLast(m => m.type === 'ai');
          const finalContent = lastAiMessage 
            ? (typeof lastAiMessage.content === 'string' ? lastAiMessage.content : '')
            : streamingContent;
          
          // Extract tool calls from the last AI message
          const toolCalls = lastAiMessage && (lastAiMessage as { tool_calls?: ToolCall[] }).tool_calls
            ? (lastAiMessage as { tool_calls: ToolCall[] }).tool_calls
            : undefined;
          
          // Add assistant message to local store
          if (finalContent || toolCalls) {
            threadStore.addMessage(localThreadId, {
              role: 'assistant',
              content: finalContent,
              toolCalls: toolCalls
            });
          }
          
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
  
  // Actions
  sendMessage,
  clearError,
  resetStream,
  checkHealth,
  getClient
};
