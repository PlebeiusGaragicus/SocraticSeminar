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
  cancelActiveRuns,
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
 * Filters out tool messages but associates their content with the corresponding AI message.
 */
function convertLangGraphMessages(
  lgMessages: LangGraphMessage[],
  threadId: string
): Omit<LocalMessage, 'createdAt'>[] {
  const localMessages: Array<Omit<LocalMessage, 'createdAt'> & { toolCalls?: ToolCallWithStatus[] }> = [];
  
  for (let i = 0; i < lgMessages.length; i++) {
    const msg = lgMessages[i];
    
    if (msg.type === 'human') {
      localMessages.push({
        id: msg.id || `human-${i}`,
        threadId,
        role: 'user',
        content: typeof msg.content === 'string' ? msg.content : JSON.stringify(msg.content)
      });
    } else if (msg.type === 'ai') {
      const content = typeof msg.content === 'string' ? msg.content : '';
      const toolCalls = (msg as { tool_calls?: ToolCall[] }).tool_calls;
      
      if (content || (toolCalls && toolCalls.length > 0)) {
        const localAiMsg = {
          id: msg.id || `ai-${i}`,
          threadId,
          role: 'assistant' as const,
          content,
          toolCalls: toolCalls?.map(tc => ({
            ...tc,
            status: 'completed' as const
          })) || []
        };
        localMessages.push(localAiMsg);
      }
    } else if (msg.type === 'tool') {
      const toolMsg = msg as { tool_call_id?: string };
      const toolCallId = toolMsg.tool_call_id;
      if (!toolCallId) continue;
      
      const content = typeof msg.content === 'string' ? msg.content : JSON.stringify(msg.content);
      
      for (const aiMsg of localMessages) {
        if (aiMsg.role === 'assistant' && aiMsg.toolCalls) {
          const toolCall = aiMsg.toolCalls.find(tc => tc.id === toolCallId);
          if (toolCall) {
            toolCall.result = {
              tool_call_id: toolCallId,
              name: toolCall.name,
              content: content
            };
            toolCall.status = 'completed';
            break;
          }
        }
      }
    }
  }
  
  return localMessages;
}

// =============================================================================
// THREAD-SPECIFIC RUN STATE
// =============================================================================

interface ThreadRunState {
  isStreaming: boolean;
  isInterrupted: boolean;
  langGraphThreadId: string | null;
  error: string | null;
  pendingToolCalls: ToolCallWithStatus[];
  streamingContent: string;
  langGraphMessages: LangGraphMessage[];
  hitlInterrupt: HITLInterrupt | null;
  hitlInterruptId: string | null;
  awaitingHumanResponse: boolean;
  paymentState: CashuPaymentState | null;
  pendingRefund: StoredRefund | null;
  paymentInterrupt: PaymentExhaustedInterrupt | null;
  clientToolInterrupt: ClientToolInterrupt | null;
  clarificationInterrupt: ClarificationInterrupt | null;
  todos: TodoItem[];
}

const runStates = $state<Record<string, ThreadRunState>>({});

/**
 * Get the run state for a specific local thread.
 * Initializes the state if it doesn't exist.
 */
function getThreadState(localThreadId: string): ThreadRunState {
  if (!runStates[localThreadId]) {
    runStates[localThreadId] = {
      isStreaming: false,
      isInterrupted: false,
      langGraphThreadId: null,
      error: null,
      pendingToolCalls: [],
      streamingContent: '',
      langGraphMessages: [],
      hitlInterrupt: null,
      hitlInterruptId: null,
      awaitingHumanResponse: false,
      paymentState: null,
      pendingRefund: null,
      paymentInterrupt: null,
      clientToolInterrupt: null,
      clarificationInterrupt: null,
      todos: []
    };
  }
  return runStates[localThreadId];
}

/**
 * Update thread status in threadStore based on agent state.
 */
function updateThreadStatus(localThreadId: string) {
  const state = getThreadState(localThreadId);
  let status: 'idle' | 'busy' | 'interrupted' | 'error' = 'idle';
  
  if (state.error) {
    status = 'error';
  } else if (state.awaitingHumanResponse) {
    // Only 'interrupted' if we are actually waiting for human input (HITL, payment, etc.)
    status = 'interrupted';
  } else if (state.isStreaming || state.isInterrupted || state.pendingToolCalls.length > 0) {
    // If the agent is running, streaming, or handling tools automatically, it's 'busy'
    status = 'busy';
  }
  
  threadStore.updateThread(localThreadId, { status });
}

// Reactive helpers to access state for the current thread
const currentLocalThreadId = $derived(threadStore.currentThreadId);
const currentState = $derived(currentLocalThreadId ? getThreadState(currentLocalThreadId) : null);

// =============================================================================
// HELPERS
// =============================================================================

import type { ScratchFile, TodoItem } from './types.js';

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

// =============================================================================
// MAIN SEND MESSAGE FUNCTION
// =============================================================================

async function sendMessage(
  message: string,
  langGraphThreadId: string | null,
  localThreadId: string
): Promise<{ langGraphThreadId: string }> {
  const state = getThreadState(localThreadId);
  
  const assistantId = assistantStore.selectedAssistantId || 'seminar_agent';
  const thread = threadStore.threads.find(t => t.id === localThreadId);
  const projectId = thread?.projectId || '';
  
  if (langGraphThreadId !== state.langGraphThreadId) {
    state.langGraphMessages = [];
  }
  
  state.isStreaming = true;
  state.isInterrupted = false;
  state.langGraphThreadId = langGraphThreadId;
  state.error = null;
  state.hitlInterrupt = null;
  state.hitlInterruptId = null;
  state.awaitingHumanResponse = false;
  state.clarificationInterrupt = null;
  state.pendingToolCalls = [];
  state.streamingContent = '';
  
  updateThreadStatus(localThreadId);
  
  state.langGraphMessages = [...state.langGraphMessages, {
    type: 'human',
    content: message,
    id: `optimistic-user-${Date.now()}`
  } as LangGraphMessage];
  
  try {
    threadStore.addMessage(localThreadId, {
      role: 'user',
      content: message
    });
    
    threadStore.updateThread(localThreadId, { description: message });
    
    const result = await submitToLangGraph(
      message,
      {
        threadId: langGraphThreadId,
        assistantId,
        projectId,
        projectFiles: buildProjectFiles(),
        streamMode: ['messages', 'values', 'updates'],
      },
      {
        onToken: (token) => {
          state.streamingContent += token;
          if (state.isInterrupted) {
            state.isInterrupted = false;
            updateThreadStatus(localThreadId);
          }
        },
        
        onMessagesSync: (messages) => {
          const localHasOptimistic = state.langGraphMessages.some(m => m.id?.startsWith('optimistic-'));
          
          if (messages.length >= state.langGraphMessages.length || !localHasOptimistic) {
            state.langGraphMessages = [...messages];
          } else {
            const updatedLocal = [...state.langGraphMessages];
            for (let i = 0; i < messages.length; i++) {
              if (messages[i].content !== updatedLocal[i]?.content) {
                updatedLocal[i] = { ...updatedLocal[i], ...messages[i] };
              }
            }
            state.langGraphMessages = updatedLocal;
          }
          
          const lastHumanIdx = messages.findLastIndex(m => m.type === 'human');
          const lastAi = messages.findLast((m, i) => m.type === 'ai' && i > lastHumanIdx);
          
          if (lastAi) {
            const serverContent = typeof lastAi.content === 'string' ? lastAi.content : '';
            if (serverContent.length > state.streamingContent.length) {
              state.streamingContent = serverContent;
            }

            // If the latest message from AI doesn't have pending tool calls, 
            // and we were in interrupted state, clear it.
            const hasToolCalls = (lastAi as { tool_calls?: unknown[] }).tool_calls?.length > 0;
            if (!hasToolCalls && state.isInterrupted) {
              state.isInterrupted = false;
              updateThreadStatus(localThreadId);
            }
          }
        },
        
        onToolCall: (toolCalls) => {
          state.isInterrupted = true;
          state.pendingToolCalls = toolCalls.map(tc => ({
            ...tc,
            status: 'pending' as const
          }));
          updateThreadStatus(localThreadId);
        },
        
        onToolExecuting: (toolCalls) => {
          state.pendingToolCalls = toolCalls.map(tc => ({
            ...tc,
            status: 'executing' as const
          }));
        },
        
        onToolComplete: (results) => {
          state.pendingToolCalls = state.pendingToolCalls.map(tc => {
            const result = results.find(r => r.tool_call_id === tc.id);
            return {
              ...tc,
              status: result?.error ? 'error' as const : 'completed' as const,
              result: result
            };
          });
          state.isInterrupted = false;
          updateThreadStatus(localThreadId);
        },
        
        onHITLInterrupt: (interrupt, interruptId) => {
          state.hitlInterrupt = interrupt;
          state.hitlInterruptId = interruptId;
          state.awaitingHumanResponse = true;
          state.isInterrupted = true;
          state.isStreaming = false;
          updateThreadStatus(localThreadId);
        },
        
        onClientToolInterrupt: (interrupt, interruptId) => {
          state.clientToolInterrupt = interrupt;
          state.hitlInterruptId = interruptId;
          state.awaitingHumanResponse = true;
          state.isInterrupted = true;
          state.isStreaming = false;
          updateThreadStatus(localThreadId);
        },
        
        onClarificationInterrupt: (interrupt, interruptId) => {
          state.clarificationInterrupt = interrupt;
          state.hitlInterruptId = interruptId;
          state.awaitingHumanResponse = true;
          state.isInterrupted = true;
          state.isStreaming = false;
          updateThreadStatus(localThreadId);
        },
        
        onTodosSync: (todoList) => {
          state.todos = todoList.map((t, i) => ({
            ...t,
            id: t.id || `todo-${i}-${t.content.slice(0, 20)}`
          }));
        },
        
        onNodeUpdate: (nodeName, update) => {
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
              state.pendingToolCalls = toolCalls;
              state.isInterrupted = true;
              updateThreadStatus(localThreadId);
            }
          }
        },
        
        onComplete: (finalMessages) => {
          state.langGraphMessages = [...finalMessages];
          const convertedMessages = convertLangGraphMessages(finalMessages, localThreadId);
          threadStore.syncMessages(localThreadId, convertedMessages);
          
          state.isStreaming = false;
          state.isInterrupted = false;
          state.pendingToolCalls = [];
          state.streamingContent = '';
          
          const lastAi = [...finalMessages].reverse().find(m => m.type === 'ai' && typeof m.content === 'string');
          if (lastAi && typeof lastAi.content === 'string') {
            threadStore.updateThread(localThreadId, { description: lastAi.content });
          }
          
          updateThreadStatus(localThreadId);
        },
        
        onError: (err) => {
          state.error = err.message;
          state.isStreaming = false;
          state.isInterrupted = false;
          state.pendingToolCalls = [];
          state.streamingContent = '';
          updateThreadStatus(localThreadId);
        },
        
        onThreadId: (id) => {
          state.langGraphThreadId = id;
          threadStore.updateThread(localThreadId, { langGraphThreadId: id });
        }
      }
    );
    
    return { langGraphThreadId: result.threadId };
    
  } catch (err) {
    const errorMessage = err instanceof Error ? err.message : 'Unknown error';
    state.error = errorMessage;
    state.isStreaming = false;
    state.isInterrupted = false;
    state.streamingContent = '';
    state.pendingToolCalls = [];
    updateThreadStatus(localThreadId);
    throw err;
  }
}

// =============================================================================
// HUMAN-IN-THE-LOOP RESPONSE
// =============================================================================

async function resumeWithDecisions(decisions: HITLDecision[]): Promise<void> {
  const localThreadId = currentLocalThreadId;
  if (!localThreadId) return;
  
  const state = getThreadState(localThreadId);
  if (!state.langGraphThreadId || !state.awaitingHumanResponse || !state.hitlInterruptId) {
    console.error('[Agent] Cannot resume: no active HITL interrupt');
    return;
  }
  
  const assistantId = assistantStore.selectedAssistantId || 'deeptutor';
  const interruptId = state.hitlInterruptId;
  
  state.hitlInterrupt = null;
  state.hitlInterruptId = null;
  state.awaitingHumanResponse = false;
  state.isStreaming = true;
  state.isInterrupted = false;
  state.streamingContent = '';
  
  updateThreadStatus(localThreadId);
  
  const response: HITLResumeResponse = { decisions };
  
  try {
    await resumeWithHITLDecisions(
      state.langGraphThreadId,
      interruptId,
      response,
      assistantId,
      {
        onToken: (token) => {
          state.streamingContent += token;
          if (state.isInterrupted) {
            state.isInterrupted = false;
            updateThreadStatus(localThreadId);
          }
        },
        onMessagesSync: (messages) => {
          state.langGraphMessages = [...messages];
        },
        onToolCall: (toolCalls) => {
          state.isInterrupted = true;
          state.pendingToolCalls = toolCalls.map(tc => ({
            ...tc,
            status: 'pending' as const
          }));
          updateThreadStatus(localThreadId);
        },
        onHITLInterrupt: (interrupt, newInterruptId) => {
          state.hitlInterrupt = interrupt;
          state.hitlInterruptId = newInterruptId;
          state.awaitingHumanResponse = true;
          state.isInterrupted = true;
          state.isStreaming = false;
          updateThreadStatus(localThreadId);
        },
        onComplete: (finalMessages) => {
          state.langGraphMessages = [...finalMessages];
          const convertedMessages = convertLangGraphMessages(finalMessages, localThreadId);
          threadStore.syncMessages(localThreadId, convertedMessages);
          state.isStreaming = false;
          state.isInterrupted = false;
          state.pendingToolCalls = [];
          state.streamingContent = '';
          updateThreadStatus(localThreadId);
        },
        onError: (err) => {
          state.error = err.message;
          state.isStreaming = false;
          state.isInterrupted = false;
          state.awaitingHumanResponse = false;
          state.pendingToolCalls = [];
          state.streamingContent = '';
          updateThreadStatus(localThreadId);
        }
      }
    );
  } catch (err) {
    const errorMessage = err instanceof Error ? err.message : 'Unknown error';
    state.error = errorMessage;
    state.isStreaming = false;
    state.isInterrupted = false;
    state.awaitingHumanResponse = false;
    state.pendingToolCalls = [];
    state.streamingContent = '';
    updateThreadStatus(localThreadId);
    throw err;
  }
}

async function approveAllActions(): Promise<void> {
  if (!currentState?.hitlInterrupt) return;
  const decisions: HITLDecision[] = currentState.hitlInterrupt.action_requests.map(() => ({
    type: 'approve' as const
  }));
  await resumeWithDecisions(decisions);
}

async function rejectAllActions(): Promise<void> {
  if (!currentState?.hitlInterrupt) return;
  const decisions: HITLDecision[] = currentState.hitlInterrupt.action_requests.map(() => ({
    type: 'reject' as const
  }));
  await resumeWithDecisions(decisions);
}

function dismissHITLInterrupt(): void {
  if (currentState) {
    currentState.hitlInterrupt = null;
    currentState.hitlInterruptId = null;
    currentState.awaitingHumanResponse = false;
    if (currentLocalThreadId) updateThreadStatus(currentLocalThreadId);
  }
}

// =============================================================================
// CASHU PAYMENT FUNCTIONS
// =============================================================================

async function checkThreadForRefunds(langGraphThreadId: string): Promise<StoredRefund | null> {
  try {
    const refund = await checkForUnclaimedRefund(langGraphThreadId);
    if (refund && currentLocalThreadId) {
      const state = getThreadState(currentLocalThreadId);
      state.pendingRefund = refund;
      return refund;
    }
    return null;
  } catch (error) {
    console.error('[Agent] Error checking for refunds:', error);
    return null;
  }
}

async function loadPaymentState(langGraphThreadId: string): Promise<CashuPaymentState | null> {
  try {
    const state = await getPaymentState(langGraphThreadId);
    if (state && currentLocalThreadId) {
      const threadRunState = getThreadState(currentLocalThreadId);
      threadRunState.paymentState = state;
    }
    return state;
  } catch (error) {
    console.error('[Agent] Error loading payment state:', error);
    return null;
  }
}

function markRefundClaimed(): void {
  if (currentState?.pendingRefund) {
    currentState.pendingRefund = { ...currentState.pendingRefund, claimed: true, claimedAt: Date.now() };
  }
}

async function resumeWithAdditionalPayment(paymentToken: string): Promise<void> {
  const localThreadId = currentLocalThreadId;
  if (!localThreadId) return;
  const state = getThreadState(localThreadId);
  
  if (!state.langGraphThreadId || !state.hitlInterruptId) {
    console.error('[Agent] Cannot resume with payment: no active interrupt');
    return;
  }
  
  const assistantId = assistantStore.selectedAssistantId || 'seminar_agent';
  const interruptId = state.hitlInterruptId;
  
  state.paymentInterrupt = null;
  state.hitlInterrupt = null;
  state.hitlInterruptId = null;
  state.awaitingHumanResponse = false;
  state.isStreaming = true;
  state.isInterrupted = false;
  state.streamingContent = '';
  updateThreadStatus(localThreadId);
  
  try {
    await resumeWithPayment(
      state.langGraphThreadId,
      interruptId,
      paymentToken,
      assistantId,
      {
        onToken: (token) => {
          state.streamingContent += token;
          if (state.isInterrupted) {
            state.isInterrupted = false;
            updateThreadStatus(localThreadId);
          }
        },
        onMessagesSync: (messages) => {
          state.langGraphMessages = [...messages];
        },
        onComplete: (finalMessages) => {
          state.langGraphMessages = [...finalMessages];
          const convertedMessages = convertLangGraphMessages(finalMessages, localThreadId);
          threadStore.syncMessages(localThreadId, convertedMessages);
          state.isStreaming = false;
          state.isInterrupted = false;
          state.pendingToolCalls = [];
          state.streamingContent = '';
          if (state.langGraphThreadId) loadPaymentState(state.langGraphThreadId);
          updateThreadStatus(localThreadId);
        },
        onError: (err) => {
          state.error = err.message;
          state.isStreaming = false;
          state.isInterrupted = false;
          state.awaitingHumanResponse = false;
          state.pendingToolCalls = [];
          state.streamingContent = '';
          updateThreadStatus(localThreadId);
        }
      }
    );
  } catch (err) {
    const errorMessage = err instanceof Error ? err.message : 'Unknown error';
    state.error = errorMessage;
    state.isStreaming = false;
    state.isInterrupted = false;
    state.awaitingHumanResponse = false;
    updateThreadStatus(localThreadId);
    throw err;
  }
}

// =============================================================================
// CLIENT TOOL HANDLING
// =============================================================================

async function handleClientToolInterrupt(
  interrupt: ClientToolInterrupt,
  interruptId: string
): Promise<void> {
  const localThreadId = currentLocalThreadId;
  if (!localThreadId) return;
  const state = getThreadState(localThreadId);
  
  state.clientToolInterrupt = interrupt;
  
  if (interrupt.auto_approve) {
    const projectId = threadStore.currentThread?.projectId || '';
    const toolCalls = interrupt.tool_calls.map(tc => ({
      id: tc.id,
      name: tc.name,
      args: tc.args,
    }));
    
    const results = await executeToolCalls(toolCalls, projectId);
    
    if (state.langGraphThreadId) {
      const assistantId = assistantStore.selectedAssistantId || 'seminar_agent';
      await resumeWithToolResults(
        state.langGraphThreadId,
        interruptId,
        results,
        assistantId,
        {
          onToken: (token) => { state.streamingContent += token; },
          onMessagesSync: (messages) => { state.langGraphMessages = [...messages]; },
          onComplete: (finalMessages) => {
            state.langGraphMessages = [...finalMessages];
            state.clientToolInterrupt = null;
            state.isStreaming = false;
            state.isInterrupted = false;
            updateThreadStatus(localThreadId);
          },
          onHITLInterrupt: (newInterrupt, newInterruptId) => {
            state.hitlInterrupt = newInterrupt;
            state.hitlInterruptId = newInterruptId;
            state.awaitingHumanResponse = true;
            state.isInterrupted = true;
            state.isStreaming = false;
            updateThreadStatus(localThreadId);
          },
          onClarificationInterrupt: (newInterrupt, newInterruptId) => {
            state.clarificationInterrupt = newInterrupt;
            state.hitlInterruptId = newInterruptId;
            state.awaitingHumanResponse = true;
            state.isInterrupted = true;
            state.isStreaming = false;
            updateThreadStatus(localThreadId);
          },
          onClientToolInterrupt: (newInterrupt, newInterruptId) => {
            state.clientToolInterrupt = newInterrupt;
            state.hitlInterruptId = newInterruptId;
            state.awaitingHumanResponse = true;
            state.isInterrupted = true;
            state.isStreaming = false;
            updateThreadStatus(localThreadId);
          },
          onError: (err) => {
            state.error = err.message;
            state.isStreaming = false;
            state.clientToolInterrupt = null;
            updateThreadStatus(localThreadId);
          }
        }
      );
    }
  } else {
    if (interrupt.action_requests && interrupt.review_configs) {
      state.hitlInterrupt = {
        action_requests: interrupt.action_requests,
        review_configs: interrupt.review_configs,
      };
      state.hitlInterruptId = interruptId;
      state.awaitingHumanResponse = true;
      state.isInterrupted = true;
      state.isStreaming = false;
      updateThreadStatus(localThreadId);
    }
  }
}

async function executeApprovedWriteTools(): Promise<void> {
  const localThreadId = currentLocalThreadId;
  if (!localThreadId) return;
  const state = getThreadState(localThreadId);

  if (!state.clientToolInterrupt || !state.langGraphThreadId || !state.hitlInterruptId) {
    console.error('[Agent] No pending write tools to execute');
    return;
  }
  
  const projectId = threadStore.currentThread?.projectId || '';
  const toolCalls = state.clientToolInterrupt.tool_calls.map(tc => ({
    id: tc.id,
    name: tc.name,
    args: tc.args,
  }));
  
  const results = await executeToolCalls(toolCalls, projectId);
  const assistantId = assistantStore.selectedAssistantId || 'seminar_agent';
  const interruptId = state.hitlInterruptId;
  
  state.clientToolInterrupt = null;
  state.hitlInterrupt = null;
  state.hitlInterruptId = null;
  state.awaitingHumanResponse = false;
  state.isStreaming = true;
  state.isInterrupted = false;
  updateThreadStatus(localThreadId);
  
  await resumeWithToolResults(
    state.langGraphThreadId,
    interruptId,
    results,
    assistantId,
    {
      onToken: (token) => { state.streamingContent += token; },
      onMessagesSync: (messages) => { state.langGraphMessages = [...messages]; },
      onComplete: (finalMessages) => {
        state.langGraphMessages = [...finalMessages];
        const convertedMessages = convertLangGraphMessages(finalMessages, localThreadId);
        threadStore.syncMessages(localThreadId, convertedMessages);
        state.isStreaming = false;
        state.isInterrupted = false;
        state.pendingToolCalls = [];
        state.streamingContent = '';
        updateThreadStatus(localThreadId);
      },
      onHITLInterrupt: (newInterrupt, newInterruptId) => {
        state.hitlInterrupt = newInterrupt;
        state.hitlInterruptId = newInterruptId;
        state.awaitingHumanResponse = true;
        state.isInterrupted = true;
        state.isStreaming = false;
        updateThreadStatus(localThreadId);
      },
      onClarificationInterrupt: (newInterrupt, newInterruptId) => {
        state.clarificationInterrupt = newInterrupt;
        state.hitlInterruptId = newInterruptId;
        state.awaitingHumanResponse = true;
        state.isInterrupted = true;
        state.isStreaming = false;
        updateThreadStatus(localThreadId);
      },
      onClientToolInterrupt: (newInterrupt, newInterruptId) => {
        state.clientToolInterrupt = newInterrupt;
        state.hitlInterruptId = newInterruptId;
        state.awaitingHumanResponse = true;
        state.isInterrupted = true;
        state.isStreaming = false;
        updateThreadStatus(localThreadId);
      },
      onError: (err) => {
        state.error = err.message;
        state.isStreaming = false;
        state.isInterrupted = false;
        updateThreadStatus(localThreadId);
      }
    }
  );
}

async function rejectClientToolInterrupt(): Promise<void> {
  const localThreadId = currentLocalThreadId;
  if (!localThreadId) return;
  const state = getThreadState(localThreadId);

  if (!state.clientToolInterrupt || !state.langGraphThreadId || !state.hitlInterruptId) {
    console.error('[Agent] No pending client tool interrupt to reject');
    return;
  }
  
  const toolCalls = state.clientToolInterrupt.tool_calls;
  const assistantId = assistantStore.selectedAssistantId || 'seminar_agent';
  const interruptId = state.hitlInterruptId;
  
  state.clientToolInterrupt = null;
  state.hitlInterrupt = null;
  state.hitlInterruptId = null;
  state.awaitingHumanResponse = false;
  state.isStreaming = true;
  state.isInterrupted = false;
  updateThreadStatus(localThreadId);
  
  const rejectionResults = toolCalls.map(tc => ({
    tool_call_id: tc.id,
    content: JSON.stringify({ status: 'rejected', message: 'User declined to execute this action' })
  }));
  
  try {
    await resumeWithToolResults(
      state.langGraphThreadId,
      interruptId,
      rejectionResults,
      assistantId,
      {
        onToken: (token) => { state.streamingContent += token; },
        onMessagesSync: (messages) => { state.langGraphMessages = [...messages]; },
        onComplete: (finalMessages) => {
          state.langGraphMessages = [...finalMessages];
          const convertedMessages = convertLangGraphMessages(finalMessages, localThreadId);
          threadStore.syncMessages(localThreadId, convertedMessages);
          state.isStreaming = false;
          state.isInterrupted = false;
          state.pendingToolCalls = [];
          state.streamingContent = '';
          updateThreadStatus(localThreadId);
        },
        onHITLInterrupt: (newInterrupt, newInterruptId) => {
          state.hitlInterrupt = newInterrupt;
          state.hitlInterruptId = newInterruptId;
          state.awaitingHumanResponse = true;
          state.isInterrupted = true;
          state.isStreaming = false;
          updateThreadStatus(localThreadId);
        },
        onClarificationInterrupt: (newInterrupt, newInterruptId) => {
          state.clarificationInterrupt = newInterrupt;
          state.hitlInterruptId = newInterruptId;
          state.awaitingHumanResponse = true;
          state.isInterrupted = true;
          state.isStreaming = false;
          updateThreadStatus(localThreadId);
        },
        onClientToolInterrupt: (newInterrupt, newInterruptId) => {
          state.clientToolInterrupt = newInterrupt;
          state.hitlInterruptId = newInterruptId;
          state.awaitingHumanResponse = true;
          state.isInterrupted = true;
          state.isStreaming = false;
          updateThreadStatus(localThreadId);
        },
        onError: (err) => {
          state.error = err.message;
          state.isStreaming = false;
          state.isInterrupted = false;
          updateThreadStatus(localThreadId);
        }
      }
    );
  } catch (err) {
    const errorMessage = err instanceof Error ? err.message : 'Unknown error';
    state.error = errorMessage;
    state.isStreaming = false;
    state.isInterrupted = false;
    state.awaitingHumanResponse = false;
    updateThreadStatus(localThreadId);
  }
}

// =============================================================================
// CLARIFICATION RESPONSE
// =============================================================================

async function resumeWithClarificationResponse(response: ClarificationResponse): Promise<void> {
  const localThreadId = currentLocalThreadId;
  if (!localThreadId) return;
  const state = getThreadState(localThreadId);

  if (!state.clarificationInterrupt || !state.langGraphThreadId || !state.hitlInterruptId) {
    console.error('[Agent] No pending clarification interrupt to respond to');
    return;
  }
  
  const interrupt = state.clarificationInterrupt;
  const assistantId = assistantStore.selectedAssistantId || 'seminar_agent';
  const interruptId = state.hitlInterruptId;
  
  state.clarificationInterrupt = null;
  state.hitlInterrupt = null;
  state.hitlInterruptId = null;
  state.awaitingHumanResponse = false;
  state.isStreaming = true;
  state.isInterrupted = false;
  updateThreadStatus(localThreadId);
  
  let responseContent: string;
  if (interrupt.tool === 'ask_user') {
    responseContent = response.response || '';
  } else {
    responseContent = JSON.stringify({
      selected: response.selected || [],
      freeform: response.freeform
    });
  }
  
  const toolResult = [{
    tool_call_id: interrupt.tool_call_id,
    content: responseContent
  }];
  
  try {
    await resumeWithToolResults(
      state.langGraphThreadId,
      interruptId,
      toolResult,
      assistantId,
      {
        onToken: (token) => { state.streamingContent += token; },
        onMessagesSync: (messages) => { state.langGraphMessages = [...messages]; },
        onComplete: (finalMessages) => {
          state.langGraphMessages = [...finalMessages];
          const convertedMessages = convertLangGraphMessages(finalMessages, localThreadId);
          threadStore.syncMessages(localThreadId, convertedMessages);
          state.isStreaming = false;
          state.isInterrupted = false;
          state.pendingToolCalls = [];
          state.streamingContent = '';
          updateThreadStatus(localThreadId);
        },
        onHITLInterrupt: (newInterrupt, newInterruptId) => {
          state.hitlInterrupt = newInterrupt;
          state.hitlInterruptId = newInterruptId;
          state.awaitingHumanResponse = true;
          state.isInterrupted = true;
          state.isStreaming = false;
          updateThreadStatus(localThreadId);
        },
        onClarificationInterrupt: (newInterrupt, newInterruptId) => {
          state.clarificationInterrupt = newInterrupt;
          state.hitlInterruptId = newInterruptId;
          state.awaitingHumanResponse = true;
          state.isInterrupted = true;
          state.isStreaming = false;
          updateThreadStatus(localThreadId);
        },
        onClientToolInterrupt: (interrupt, newInterruptId) => {
          state.clientToolInterrupt = interrupt;
          state.hitlInterruptId = newInterruptId;
          state.awaitingHumanResponse = true;
          state.isInterrupted = true;
          state.isStreaming = false;
          updateThreadStatus(localThreadId);
        },
        onError: (err) => {
          state.error = err.message;
          state.isStreaming = false;
          state.isInterrupted = false;
          updateThreadStatus(localThreadId);
        }
      }
    );
  } catch (err) {
    const errorMessage = err instanceof Error ? err.message : 'Unknown error';
    state.error = errorMessage;
    state.isStreaming = false;
    state.isInterrupted = false;
    state.awaitingHumanResponse = false;
    updateThreadStatus(localThreadId);
  }
}

// =============================================================================
// STREAM CONTROL
// =============================================================================

async function stopStreaming(): Promise<void> {
  const localThreadId = currentLocalThreadId;
  if (!localThreadId) return;
  const state = getThreadState(localThreadId);
  
  if (state.langGraphThreadId) {
    try {
      await cancelActiveRuns(state.langGraphThreadId);
    } catch (err) {
      console.error('[Agent] Failed to cancel runs:', err);
    }
  }
  
  state.isStreaming = false;
  state.isInterrupted = false;
  updateThreadStatus(localThreadId);
}

// =============================================================================
// UTILITY FUNCTIONS
// =============================================================================

function clearError(): void {
  if (currentState) currentState.error = null;
}

function resetStream(): void {
  if (currentLocalThreadId) {
    const state = getThreadState(currentLocalThreadId);
    state.isStreaming = false;
    state.isInterrupted = false;
    state.langGraphThreadId = null;
    state.error = null;
    state.hitlInterrupt = null;
    state.hitlInterruptId = null;
    state.awaitingHumanResponse = false;
    state.paymentState = null;
    state.pendingRefund = null;
    state.paymentInterrupt = null;
    state.clientToolInterrupt = null;
    state.clarificationInterrupt = null;
    state.todos = [];
    state.pendingToolCalls = [];
    state.streamingContent = '';
    state.langGraphMessages = [];
    updateThreadStatus(currentLocalThreadId);
  }
}

function clearProjectState(): void {
  for (const tid in runStates) {
    delete runStates[tid];
  }
}

// =============================================================================
// THREAD STATE RESTORATION
// =============================================================================

async function loadThreadState(
  langGraphThreadId: string,
  localThreadId: string
): Promise<boolean> {
  try {
    const state = getThreadState(localThreadId);
    
    // If we're already actively streaming this thread in this session,
    // don't overwrite the states that are being managed by sendMessage.
    if (state.isStreaming) {
      return true;
    }

    const stateInfo = await getThreadStateWithInterrupts(langGraphThreadId);
    
    state.langGraphMessages = [...stateInfo.messages];
    state.langGraphThreadId = langGraphThreadId;
    
    if (stateInfo.messages.length > 0) {
      const convertedMessages = convertLangGraphMessages(stateInfo.messages, localThreadId);
      threadStore.syncMessages(localThreadId, convertedMessages);
    }
    
    if (stateInfo.hasInterrupt && stateInfo.interruptData && stateInfo.interruptId) {
      state.hitlInterruptId = stateInfo.interruptId;
      state.awaitingHumanResponse = true;
      state.isInterrupted = true;
      state.isStreaming = false;
      
      switch (stateInfo.interruptType) {
        case 'clarification':
          state.clarificationInterrupt = stateInfo.interruptData as ClarificationInterrupt;
          break;
        case 'client_tool':
          state.clientToolInterrupt = stateInfo.interruptData as ClientToolInterrupt;
          break;
        case 'hitl':
          state.hitlInterrupt = stateInfo.interruptData as HITLInterrupt;
          break;
        case 'payment':
          state.paymentInterrupt = stateInfo.interruptData as PaymentExhaustedInterrupt;
          break;
      }
    } else {
      state.hitlInterrupt = null;
      state.hitlInterruptId = null;
      state.clarificationInterrupt = null;
      state.clientToolInterrupt = null;
      state.paymentInterrupt = null;
      state.awaitingHumanResponse = false;
      state.isInterrupted = false;
      
      // Check if there's an active run on the server even if not interrupted.
      // This helps show 'busy' status for background runs after page refresh.
      try {
        const client = getClient();
        const runs = await client.runs.list(langGraphThreadId, { limit: 1 });
        if (runs.length > 0 && (runs[0].status === 'pending' || runs[0].status === 'running')) {
          console.log('[Agent] Detected active run on server for thread:', langGraphThreadId);
          // We can't easily hook back into the stream here without re-submitting,
          // but we can at least show it as busy.
          state.isStreaming = true;
        }
      } catch (runErr) {
        console.warn('[Agent] Could not check active runs:', runErr);
      }
    }
    
    try {
      const stateTodos = await getThreadTodos(langGraphThreadId);
      state.todos = [...stateTodos];
    } catch (todoErr) {
      console.warn('[Agent] Could not load todos from thread state:', todoErr);
    }
    
    updateThreadStatus(localThreadId);
    return true;
  } catch (err) {
    console.error('[Agent] Failed to load thread state:', err);
    return false;
  }
}

// =============================================================================
// EXPORTS
// =============================================================================

export const agentStore = {
  // Reactive getters
  get streamingContent() { return currentState?.streamingContent || ''; },
  get isStreaming() { return currentState?.isStreaming || false; },
  get isInterrupted() { return currentState?.isInterrupted || false; },
  get pendingToolCalls() { return currentState?.pendingToolCalls || []; },
  get error() { return currentState?.error || null; },
  get threadId() { return currentState?.langGraphThreadId || null; },
  get langGraphMessages() { return currentState?.langGraphMessages || []; },
  
  // Human-in-the-loop getters
  get hitlInterrupt() { return currentState?.hitlInterrupt || null; },
  get awaitingHumanResponse() { return currentState?.awaitingHumanResponse || false; },
  
  // Payment getters
  get paymentState() { return currentState?.paymentState || null; },
  get pendingRefund() { return currentState?.pendingRefund || null; },
  get paymentInterrupt() { return currentState?.paymentInterrupt || null; },
  get clientToolInterrupt() { return currentState?.clientToolInterrupt || null; },
  
  // Clarification getter
  get clarificationInterrupt() { return currentState?.clarificationInterrupt || null; },
  
  // Todos from TodoListMiddleware
  get todos() { return currentState?.todos || []; },
  
  // Actions
  sendMessage,
  stopStreaming,
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
