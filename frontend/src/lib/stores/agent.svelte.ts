// Agent store for LangGraph streaming with tool interrupt handling
// Uses the langgraph service for communication and handles state reactively
// Includes Cashu payment state tracking and refund detection

import type { 
  ToolCall, 
  ToolCallWithStatus,
  ToolResult,
  ProjectFile,
  Message as LocalMessage,
  HITLInterrupt,
  HITLDecision,
  HITLResumeResponse,
  CashuPaymentState,
  ClientToolInterrupt,
  PaymentExhaustedInterrupt,
  StoredRefund,
  ClarificationInterrupt,
  ClarificationResponse
} from './types.js';
import { 
  isClientToolInterrupt,
  isPaymentExhaustedInterrupt,
  isClarificationInterrupt
} from './types.js';
import { threadStore } from './threads.svelte.js';
import { artifactStore } from './artifacts.svelte.js';
import { assistantStore } from './assistants.svelte.js';
import { 
  submitMessage as submitToLangGraph,
  resumeWithHITLDecisions,
  resumeWithToolResults,
  resumeWithPayment,
  setToolExecutor,
  checkHealth,
  getClient,
  getPaymentState,
  checkForUnclaimedRefund,
  getThreadStateWithInterrupts,
  getThreadTodos,
  debugGetThreadState,
  type Message as LangGraphMessage,
  type ThreadStateInfo
} from '$lib/services/langgraph.js';
import { executeToolCall, executeToolCalls } from '$lib/services/tool-executor.js';

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
// CASHU PAYMENT STATE
// =============================================================================

let paymentState = $state<CashuPaymentState | null>(null);
let pendingRefund = $state<StoredRefund | null>(null);
let paymentInterrupt = $state<PaymentExhaustedInterrupt | null>(null);
let clientToolInterrupt = $state<ClientToolInterrupt | null>(null);
let clarificationInterrupt = $state<ClarificationInterrupt | null>(null);

// =============================================================================
// AGENT SCRATCH FILES & TODOS (visible to user, read-only)
// =============================================================================

import type { ScratchFile, TodoItem } from './types.js';

// Scratch files from agent's working memory (stored in agent state)
let scratchFiles = $state<Record<string, ScratchFile>>({});

// Todos from TodoListMiddleware
let todos = $state<TodoItem[]>([]);

// =============================================================================
// HELPERS
// =============================================================================

// Build project files with content for agent context
function buildProjectFiles(): ProjectFile[] {
  const artifacts = artifactStore.artifacts;
  return artifacts.map(artifact => {
    const currentVersion = artifact.versions[artifact.currentVersionIndex];
    return {
      id: artifact.id,
      title: currentVersion?.title || 'Untitled',
      file_type: 'artifact' as const,
      content: currentVersion?.content || ''
    };
  });
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
  clarificationInterrupt = null;
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
    // Include 'updates' stream mode for real-time visibility of node execution
    const result = await submitToLangGraph(
      message,
      {
        threadId: langGraphThreadId,
        assistantId,
        projectId,
        projectFiles: buildProjectFiles(),
        streamMode: ['messages', 'values', 'updates'],  // Real-time updates for tool visibility
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
          console.log('[Agent] Messages synced:', messages.length, 'messages');
          console.log('[Agent] Message types:', messages.map(m => m.type));
          // Sync with server state
          langGraphMessages = [...messages];
          
          // Find the latest AI message
          const lastAi = messages.findLast(m => m.type === 'ai');
          console.log('[Agent] Last AI message:', lastAi ? 'found' : 'not found', 
            lastAi ? { id: lastAi.id, hasContent: !!(lastAi as { content?: unknown }).content } : null);
          if (lastAi && lastAi.id) {
            if (!knownAiMessageIds.has(lastAi.id)) {
              currentAiMessageId = lastAi.id;
              // Use server content if we haven't started streaming yet
              if (!streamingContent) {
                const serverContent = typeof lastAi.content === 'string' ? lastAi.content : '';
                streamingContent = serverContent;
                console.log('[Agent] Set streaming content from server:', serverContent.substring(0, 100) + '...');
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
        
        onClientToolInterrupt: (interrupt, interruptId) => {
          console.log('[Agent] Client tool interrupt received:', interrupt.tool_calls.map(tc => tc.name));
          console.log('[Agent] Requires approval:', interrupt.requires_approval);
          
          // Store the interrupt for the UI to handle
          clientToolInterrupt = interrupt;
          hitlInterruptId = interruptId;  // Reuse hitlInterruptId for the resume
          awaitingHumanResponse = true;
          isInterrupted = true;
          isStreaming = false;
        },
        
        onClarificationInterrupt: (interrupt, interruptId) => {
          console.log('[Agent] Clarification interrupt received:', interrupt.tool, interrupt.question);
          
          // Store the interrupt for the UI to handle
          clarificationInterrupt = interrupt;
          hitlInterruptId = interruptId;  // Reuse hitlInterruptId for the resume
          awaitingHumanResponse = true;
          isInterrupted = true;
          isStreaming = false;
        },
        
        onScratchFilesSync: (files) => {
          console.log('[Agent] Scratch files synced:', Object.keys(files).length, 'files');
          scratchFiles = { ...files };
        },
        
        onTodosSync: (todoList) => {
          console.log('[Agent] Todos synced:', todoList.length, 'items');
          console.log('[Agent] Todo details:', todoList.map(t => ({ 
            id: t.id, 
            content: t.content?.substring(0, 40), 
            status: t.status 
          })));
          // Force reactivity by creating a new array
          todos = [...todoList];
          console.log('[Agent] Todos state updated, new length:', todos.length);
        },
        
        onNodeUpdate: (nodeName, update) => {
          // Real-time node execution update
          // This shows what's happening inside the graph as it runs
          const keys = Object.keys(update);
          console.log('[Agent] Node executed:', nodeName, 'keys:', keys);
          
          // Log if we see todos-related data
          if (keys.includes('todos') || keys.includes('todo_list')) {
            console.log('[Agent] Todos in node update!', nodeName, update.todos || update.todo_list);
          }
          
          // If the update contains messages with tool calls, show them immediately
          const messages = update.messages as Array<{ type: string; tool_calls?: unknown[] }> | undefined;
          if (messages && Array.isArray(messages)) {
            const lastMsg = messages[messages.length - 1];
            if (lastMsg?.type === 'ai' && lastMsg.tool_calls?.length) {
              const toolCalls = (lastMsg.tool_calls as Array<{ id: string; name: string; args?: Record<string, unknown> }>).map(tc => ({
                id: tc.id,
                name: tc.name,
                args: tc.args || {},
                status: 'pending' as const,
              }));
              console.log('[Agent] Tool calls from node update:', toolCalls.map(tc => tc.name));
              setPendingToolCalls(toolCalls);
            }
          }
        },
        
        onComplete: async (finalMessages) => {
          console.log('[Agent] Stream completed. Messages:', finalMessages.length);
          console.log('[Agent] Final message types:', finalMessages.map(m => ({
            type: m.type,
            hasContent: !!((m as { content?: unknown }).content),
            contentPreview: typeof (m as { content?: unknown }).content === 'string' 
              ? (m as { content: string }).content.substring(0, 100) 
              : typeof (m as { content?: unknown }).content,
            toolCalls: ((m as { tool_calls?: unknown[] }).tool_calls || []).length
          })));
          
          langGraphMessages = [...finalMessages];
          
          // Convert and sync ALL messages from LangGraph to local store
          // This ensures we have the complete conversation history including
          // multiple AI messages from tool call iterations
          const convertedMessages = convertLangGraphMessages(finalMessages, localThreadId);
          console.log('[Agent] Converted to local messages:', convertedMessages.length);
          threadStore.syncMessages(localThreadId, convertedMessages);
          
          // Fetch todos from thread state after stream completes
          // This ensures we have the final state of todos
          if (threadId) {
            try {
              console.log('[Agent] Fetching todos from thread state after completion...');
              await debugGetThreadState(threadId);
              const stateTodos = await getThreadTodos(threadId);
              if (stateTodos.length > 0) {
                console.log('[Agent] Got todos from thread state:', stateTodos);
                todos = stateTodos;
              }
            } catch (err) {
              console.error('[Agent] Failed to fetch todos from thread state:', err);
            }
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
// CASHU PAYMENT FUNCTIONS
// =============================================================================

/**
 * Check for unclaimed refunds when loading a thread.
 * This is part of session recovery - if the user closed the browser
 * while the agent was running, we detect the refund and offer to claim it.
 */
async function checkThreadForRefunds(langGraphThreadId: string): Promise<StoredRefund | null> {
  try {
    const refund = await checkForUnclaimedRefund(langGraphThreadId);
    if (refund) {
      console.log('[Agent] Found unclaimed refund:', refund.amountSats, 'sats');
      pendingRefund = refund;
      return refund;
    }
    return null;
  } catch (error) {
    console.error('[Agent] Error checking for refunds:', error);
    return null;
  }
}

/**
 * Load payment state for a thread.
 */
async function loadPaymentState(langGraphThreadId: string): Promise<CashuPaymentState | null> {
  try {
    const state = await getPaymentState(langGraphThreadId);
    if (state) {
      paymentState = state;
      console.log('[Agent] Payment state loaded:', state.payment_status, 
        state.payment_balance_sats, 'sats remaining');
    }
    return state;
  } catch (error) {
    console.error('[Agent] Error loading payment state:', error);
    return null;
  }
}

/**
 * Mark a refund as claimed.
 * This should be called after the client wallet has received the refund.
 */
function markRefundClaimed(): void {
  if (pendingRefund) {
    pendingRefund = { ...pendingRefund, claimed: true, claimedAt: Date.now() };
    console.log('[Agent] Refund marked as claimed');
  }
}

/**
 * Resume with additional payment after funds exhausted.
 */
async function resumeWithAdditionalPayment(paymentToken: string): Promise<void> {
  if (!threadId || !hitlInterruptId) {
    console.error('[Agent] Cannot resume with payment: no active interrupt');
    return;
  }
  
  const assistantId = assistantStore.selectedAssistantId || 'deeptutor';
  const localThreadId = currentLocalThreadId;
  const interruptId = hitlInterruptId;
  
  // Reset states
  paymentInterrupt = null;
  hitlInterrupt = null;
  hitlInterruptId = null;
  awaitingHumanResponse = false;
  isStreaming = true;
  isInterrupted = false;
  setStreamingContent('');
  
  console.log('[Agent] Resuming with additional payment');
  
  try {
    await resumeWithPayment(
      threadId,
      interruptId,
      paymentToken,
      assistantId,
      {
        onToken: (token) => {
          streamingContent += token;
        },
        
        onMessagesSync: (messages) => {
          langGraphMessages = [...messages];
        },
        
        onComplete: (finalMessages) => {
          console.log('[Agent] Payment resume completed');
          langGraphMessages = [...finalMessages];
          
          if (localThreadId) {
            const convertedMessages = convertLangGraphMessages(finalMessages, localThreadId);
            threadStore.syncMessages(localThreadId, convertedMessages);
          }
          
          isStreaming = false;
          isInterrupted = false;
          setPendingToolCalls([]);
          setStreamingContent('');
          
          // Reload payment state
          if (threadId) {
            loadPaymentState(threadId);
          }
        },
        
        onError: (err) => {
          console.error('[Agent] Payment resume error:', err.message);
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
    console.error('[Agent] Payment resume error:', errorMessage);
    error = errorMessage;
    isStreaming = false;
    isInterrupted = false;
    awaitingHumanResponse = false;
    throw err;
  }
}

/**
 * Handle client tool execution interrupt.
 * Executes read-only tools automatically, or waits for approval on write tools.
 */
async function handleClientToolInterrupt(
  interrupt: ClientToolInterrupt,
  interruptId: string
): Promise<void> {
  clientToolInterrupt = interrupt;
  
  // If auto-approve (read-only tools), execute immediately
  if (interrupt.auto_approve) {
    console.log('[Agent] Auto-executing read-only tools:', 
      interrupt.tool_calls.map(tc => tc.name));
    
    const projectId = threadStore.currentThread?.projectId || '';
    const toolCalls = interrupt.tool_calls.map(tc => ({
      id: tc.id,
      name: tc.name,
      args: tc.args,
    }));
    
    // Execute tools
    const results = await executeToolCalls(toolCalls, projectId);
    
    // Resume with results
    if (threadId) {
      const assistantId = assistantStore.selectedAssistantId || 'deeptutor';
      await resumeWithToolResults(
        threadId,
        interruptId,
        results,
        assistantId,
        {
          onToken: (token) => {
            streamingContent += token;
          },
          onMessagesSync: (messages) => {
            langGraphMessages = [...messages];
          },
          onComplete: (finalMessages) => {
            langGraphMessages = [...finalMessages];
            clientToolInterrupt = null;
            isStreaming = false;
            isInterrupted = false;
          },
          onHITLInterrupt: (newInterrupt, newInterruptId) => {
            // Another interrupt - handle it
            hitlInterrupt = newInterrupt;
            hitlInterruptId = newInterruptId;
            awaitingHumanResponse = true;
            isInterrupted = true;
            isStreaming = false;
          },
          onClarificationInterrupt: (newInterrupt, newInterruptId) => {
            clarificationInterrupt = newInterrupt;
            hitlInterruptId = newInterruptId;
            awaitingHumanResponse = true;
            isInterrupted = true;
            isStreaming = false;
          },
          onClientToolInterrupt: (newInterrupt, newInterruptId) => {
            clientToolInterrupt = newInterrupt;
            hitlInterruptId = newInterruptId;
            awaitingHumanResponse = true;
            isInterrupted = true;
            isStreaming = false;
          },
          onError: (err) => {
            error = err.message;
            isStreaming = false;
            clientToolInterrupt = null;
          }
        }
      );
    }
  } else {
    // Requires approval - show UI
    console.log('[Agent] Write tools require approval:', 
      interrupt.tool_calls.map(tc => tc.name));
    
    // Convert to HITL format for the UI
    if (interrupt.action_requests && interrupt.review_configs) {
      hitlInterrupt = {
        action_requests: interrupt.action_requests,
        review_configs: interrupt.review_configs,
      };
      hitlInterruptId = interruptId;
      awaitingHumanResponse = true;
      isInterrupted = true;
      isStreaming = false;
    }
  }
}

/**
 * Execute approved write tools and resume.
 */
async function executeApprovedWriteTools(): Promise<void> {
  if (!clientToolInterrupt || !threadId || !hitlInterruptId) {
    console.error('[Agent] No pending write tools to execute');
    return;
  }
  
  const projectId = threadStore.currentThread?.projectId || '';
  const toolCalls = clientToolInterrupt.tool_calls.map(tc => ({
    id: tc.id,
    name: tc.name,
    args: tc.args,
  }));
  
  console.log('[Agent] Executing approved write tools:', toolCalls.map(tc => tc.name));
  
  // Execute the tools
  const results = await executeToolCalls(toolCalls, projectId);
  
  // Resume with results
  const assistantId = assistantStore.selectedAssistantId || 'deeptutor';
  const interruptId = hitlInterruptId;
  
  // Reset states
  clientToolInterrupt = null;
  hitlInterrupt = null;
  hitlInterruptId = null;
  awaitingHumanResponse = false;
  isStreaming = true;
  isInterrupted = false;
  
  await resumeWithToolResults(
    threadId,
    interruptId,
    results,
    assistantId,
    {
      onToken: (token) => {
        streamingContent += token;
      },
      onMessagesSync: (messages) => {
        langGraphMessages = [...messages];
      },
      onComplete: (finalMessages) => {
        langGraphMessages = [...finalMessages];
        
        if (currentLocalThreadId) {
          const convertedMessages = convertLangGraphMessages(finalMessages, currentLocalThreadId);
          threadStore.syncMessages(currentLocalThreadId, convertedMessages);
        }
        
        isStreaming = false;
        isInterrupted = false;
        setPendingToolCalls([]);
        setStreamingContent('');
      },
      onHITLInterrupt: (newInterrupt, newInterruptId) => {
        hitlInterrupt = newInterrupt;
        hitlInterruptId = newInterruptId;
        awaitingHumanResponse = true;
        isInterrupted = true;
        isStreaming = false;
      },
      onClarificationInterrupt: (newInterrupt, newInterruptId) => {
        clarificationInterrupt = newInterrupt;
        hitlInterruptId = newInterruptId;
        awaitingHumanResponse = true;
        isInterrupted = true;
        isStreaming = false;
      },
      onClientToolInterrupt: (newInterrupt, newInterruptId) => {
        clientToolInterrupt = newInterrupt;
        hitlInterruptId = newInterruptId;
        awaitingHumanResponse = true;
        isInterrupted = true;
        isStreaming = false;
      },
      onError: (err) => {
        error = err.message;
        isStreaming = false;
        isInterrupted = false;
      }
    }
  );
}

// =============================================================================
// CLIENT TOOL REJECTION
// =============================================================================

/**
 * Reject a client tool interrupt (user declined to execute the tool).
 */
async function rejectClientToolInterrupt(): Promise<void> {
  if (!clientToolInterrupt || !threadId || !hitlInterruptId) {
    console.error('[Agent] No pending client tool interrupt to reject');
    return;
  }
  
  console.log('[Agent] Rejecting client tool interrupt');
  
  const toolCalls = clientToolInterrupt.tool_calls;
  const assistantId = assistantStore.selectedAssistantId || 'deeptutor';
  const interruptId = hitlInterruptId;
  
  // Reset states
  clientToolInterrupt = null;
  hitlInterrupt = null;
  hitlInterruptId = null;
  awaitingHumanResponse = false;
  isStreaming = true;
  isInterrupted = false;
  
  // Create rejection results
  const rejectionResults = toolCalls.map(tc => ({
    tool_call_id: tc.id,
    content: JSON.stringify({ 
      status: 'rejected', 
      message: 'User declined to execute this action' 
    })
  }));
  
  try {
    await resumeWithToolResults(
      threadId,
      interruptId,
      rejectionResults,
      assistantId,
      {
        onToken: (token) => {
          streamingContent += token;
        },
        onMessagesSync: (messages) => {
          langGraphMessages = [...messages];
        },
        onComplete: (finalMessages) => {
          langGraphMessages = [...finalMessages];
          
          if (currentLocalThreadId) {
            const convertedMessages = convertLangGraphMessages(finalMessages, currentLocalThreadId);
            threadStore.syncMessages(currentLocalThreadId, convertedMessages);
          }
          
          isStreaming = false;
          isInterrupted = false;
          setPendingToolCalls([]);
          setStreamingContent('');
        },
        onHITLInterrupt: (newInterrupt, newInterruptId) => {
          hitlInterrupt = newInterrupt;
          hitlInterruptId = newInterruptId;
          awaitingHumanResponse = true;
          isInterrupted = true;
          isStreaming = false;
        },
        onClarificationInterrupt: (newInterrupt, newInterruptId) => {
          clarificationInterrupt = newInterrupt;
          hitlInterruptId = newInterruptId;
          awaitingHumanResponse = true;
          isInterrupted = true;
          isStreaming = false;
        },
        onClientToolInterrupt: (newInterrupt, newInterruptId) => {
          clientToolInterrupt = newInterrupt;
          hitlInterruptId = newInterruptId;
          awaitingHumanResponse = true;
          isInterrupted = true;
          isStreaming = false;
        },
        onError: (err) => {
          error = err.message;
          isStreaming = false;
          isInterrupted = false;
        }
      }
    );
  } catch (err) {
    const errorMessage = err instanceof Error ? err.message : 'Unknown error';
    console.error('[Agent] Reject error:', errorMessage);
    error = errorMessage;
    isStreaming = false;
    isInterrupted = false;
    awaitingHumanResponse = false;
  }
}

// =============================================================================
// CLARIFICATION RESPONSE
// =============================================================================

/**
 * Resume the agent with a user's response to a clarification question.
 */
async function resumeWithClarificationResponse(response: ClarificationResponse): Promise<void> {
  if (!clarificationInterrupt || !threadId || !hitlInterruptId) {
    console.error('[Agent] No pending clarification interrupt to respond to');
    return;
  }
  
  console.log('[Agent] Resuming with clarification response:', response);
  
  const interrupt = clarificationInterrupt;
  const assistantId = assistantStore.selectedAssistantId || 'deeptutor';
  const interruptId = hitlInterruptId;
  
  // Reset states
  clarificationInterrupt = null;
  hitlInterrupt = null;
  hitlInterruptId = null;
  awaitingHumanResponse = false;
  isStreaming = true;
  isInterrupted = false;
  
  // Format the response content based on tool type
  let responseContent: string;
  if (interrupt.tool === 'ask_user') {
    // Free-form response
    responseContent = response.response || '';
  } else {
    // ask_choices - format as JSON with selected IDs and optional freeform
    responseContent = JSON.stringify({
      selected: response.selected || [],
      freeform: response.freeform
    });
  }
  
  // Create tool result for the clarification
  const toolResult = [{
    tool_call_id: interrupt.tool_call_id,
    content: responseContent
  }];
  
  try {
    await resumeWithToolResults(
      threadId,
      interruptId,
      toolResult,
      assistantId,
      {
        onToken: (token) => {
          streamingContent += token;
        },
        onMessagesSync: (messages) => {
          langGraphMessages = [...messages];
        },
        onComplete: (finalMessages) => {
          langGraphMessages = [...finalMessages];
          
          if (currentLocalThreadId) {
            const convertedMessages = convertLangGraphMessages(finalMessages, currentLocalThreadId);
            threadStore.syncMessages(currentLocalThreadId, convertedMessages);
          }
          
          isStreaming = false;
          isInterrupted = false;
          setPendingToolCalls([]);
          setStreamingContent('');
        },
        onHITLInterrupt: (newInterrupt, newInterruptId) => {
          hitlInterrupt = newInterrupt;
          hitlInterruptId = newInterruptId;
          awaitingHumanResponse = true;
          isInterrupted = true;
          isStreaming = false;
        },
        onClarificationInterrupt: (newInterrupt, newInterruptId) => {
          clarificationInterrupt = newInterrupt;
          hitlInterruptId = newInterruptId;
          awaitingHumanResponse = true;
          isInterrupted = true;
          isStreaming = false;
        },
        onClientToolInterrupt: (interrupt, newInterruptId) => {
          // Client tool interrupt after clarification - handle it
          console.log('[Agent] Client tool interrupt after clarification:', interrupt.tool_calls.map(tc => tc.name));
          clientToolInterrupt = interrupt;
          hitlInterruptId = newInterruptId;
          awaitingHumanResponse = true;
          isInterrupted = true;
          isStreaming = false;
        },
        onError: (err) => {
          error = err.message;
          isStreaming = false;
          isInterrupted = false;
        }
      }
    );
  } catch (err) {
    const errorMessage = err instanceof Error ? err.message : 'Unknown error';
    console.error('[Agent] Clarification response error:', errorMessage);
    error = errorMessage;
    isStreaming = false;
    isInterrupted = false;
    awaitingHumanResponse = false;
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
  hitlInterrupt = null;
  hitlInterruptId = null;
  awaitingHumanResponse = false;
  currentLocalThreadId = null;
  paymentState = null;
  pendingRefund = null;
  paymentInterrupt = null;
  clientToolInterrupt = null;
  clarificationInterrupt = null;
  scratchFiles = {};
  todos = [];
  setPendingToolCalls([]);
  setStreamingContent('');
  langGraphMessages = [];
}

/**
 * Clear all state when switching projects.
 * This prevents stale thread references and clears any in-progress operations.
 */
function clearProjectState(): void {
  resetStream();
}

// =============================================================================
// THREAD STATE RESTORATION
// =============================================================================

/**
 * Load and restore thread state from the LangGraph server.
 * This is called when selecting a thread that has a langGraphThreadId,
 * especially after page refresh to restore pending interrupts.
 * 
 * @param langGraphThreadId - The LangGraph thread ID to load
 * @param localThreadId - The local thread ID for message syncing
 * @returns True if state was loaded successfully
 */
async function loadThreadState(
  langGraphThreadId: string,
  localThreadId: string
): Promise<boolean> {
  console.log('[Agent] Loading thread state for:', langGraphThreadId);
  
  try {
    const stateInfo = await getThreadStateWithInterrupts(langGraphThreadId);
    
    // Update the langGraphMessages for display
    langGraphMessages = [...stateInfo.messages];
    threadId = langGraphThreadId;
    currentLocalThreadId = localThreadId;
    
    // Sync messages to local store
    if (stateInfo.messages.length > 0) {
      const convertedMessages = convertLangGraphMessages(stateInfo.messages, localThreadId);
      threadStore.syncMessages(localThreadId, convertedMessages);
      console.log('[Agent] Synced', convertedMessages.length, 'messages from LangGraph');
    }
    
    // Restore interrupt state if there's a pending interrupt
    if (stateInfo.hasInterrupt && stateInfo.interruptData && stateInfo.interruptId) {
      console.log('[Agent] Restoring interrupt:', stateInfo.interruptType);
      
      hitlInterruptId = stateInfo.interruptId;
      awaitingHumanResponse = true;
      isInterrupted = true;
      isStreaming = false;
      
      switch (stateInfo.interruptType) {
        case 'clarification':
          clarificationInterrupt = stateInfo.interruptData as ClarificationInterrupt;
          console.log('[Agent] Restored clarification interrupt:', clarificationInterrupt.tool);
          break;
          
        case 'client_tool':
          clientToolInterrupt = stateInfo.interruptData as ClientToolInterrupt;
          console.log('[Agent] Restored client tool interrupt');
          break;
          
        case 'hitl':
          hitlInterrupt = stateInfo.interruptData as HITLInterrupt;
          console.log('[Agent] Restored HITL interrupt');
          break;
          
        case 'payment':
          paymentInterrupt = stateInfo.interruptData as PaymentExhaustedInterrupt;
          console.log('[Agent] Restored payment interrupt');
          break;
      }
    } else {
      // No interrupt - ensure interrupt state is clear
      hitlInterrupt = null;
      hitlInterruptId = null;
      clarificationInterrupt = null;
      clientToolInterrupt = null;
      paymentInterrupt = null;
      awaitingHumanResponse = false;
      isInterrupted = false;
    }
    
    // Load todos from thread state
    try {
      const stateTodos = await getThreadTodos(langGraphThreadId);
      if (stateTodos.length > 0) {
        console.log('[Agent] Loaded todos from thread state:', stateTodos.length);
        todos = [...stateTodos];
      }
    } catch (todoErr) {
      console.warn('[Agent] Could not load todos from thread state:', todoErr);
    }
    
    return true;
    
  } catch (err) {
    console.error('[Agent] Failed to load thread state:', err);
    error = err instanceof Error ? err.message : 'Failed to load thread state';
    return false;
  }
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
  
  // Payment getters
  get paymentState() { return paymentState; },
  get pendingRefund() { return pendingRefund; },
  get paymentInterrupt() { return paymentInterrupt; },
  get clientToolInterrupt() { return clientToolInterrupt; },
  
  // Clarification getter
  get clarificationInterrupt() { return clarificationInterrupt; },
  
  // Scratch files & todos (visible to user, read-only)
  get scratchFiles() { return scratchFiles; },
  get todos() { return todos; },
  
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
  dismissHITLInterrupt,
  
  // Payment actions
  checkThreadForRefunds,
  loadPaymentState,
  markRefundClaimed,
  resumeWithAdditionalPayment,
  
  // Client tool actions
  handleClientToolInterrupt,
  executeApprovedWriteTools,
  rejectClientToolInterrupt,
  
  // Clarification actions
  resumeWithClarificationResponse,
  
  // Project state
  clearProjectState,
  
  // Thread state restoration
  loadThreadState,
};
