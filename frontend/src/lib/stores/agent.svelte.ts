// Agent store for LangGraph streaming
// Handles direct communication with LangGraph server

import { Client } from '@langchain/langgraph-sdk';
import type { PaymentRequest, AgentStreamState } from './types';
import { threadStore } from './threads.svelte';

// Configuration
const LANGGRAPH_URL = import.meta.env.PUBLIC_LANGGRAPH_URL ?? 'http://localhost:54367';
const ASSISTANT_ID = import.meta.env.PUBLIC_ASSISTANT_ID ?? 'seminar_agent';

// LangGraph client (lazy initialized)
let client: Client | null = null;

function getClient(): Client {
  if (!client) {
    client = new Client({ apiUrl: LANGGRAPH_URL });
  }
  return client;
}

// Reactive state
let streamState = $state<AgentStreamState>({
  isStreaming: false,
  threadId: null,
  currentRunId: null,
  error: null
});

let streamingContent = $state<string>('');

// Actions
async function sendMessage(
  message: string,
  threadId: string | null,
  payment?: PaymentRequest
): Promise<void> {
  const lgClient = getClient();
  
  // Reset state
  streamState = {
    isStreaming: true,
    threadId,
    currentRunId: null,
    error: null
  };
  streamingContent = '';
  
  try {
    // Create thread if needed
    let activeThreadId = threadId;
    if (!activeThreadId) {
      const thread = await lgClient.threads.create();
      activeThreadId = thread.thread_id;
      streamState.threadId = activeThreadId;
    }
    
    // Build input with optional payment
    const input: Record<string, unknown> = {
      messages: [{ role: 'user', content: message }]
    };
    
    if (payment) {
      input.payment = {
        ecash_token: payment.ecashToken,
        amount_sats: payment.amountSats
      };
    }
    
    // Add user message to local store
    threadStore.addMessage(activeThreadId, {
      role: 'user',
      content: message
    });
    
    // Stream the response
    const streamResponse = lgClient.runs.stream(
      activeThreadId,
      ASSISTANT_ID,
      { input }
    );
    
    let assistantContent = '';
    
    for await (const event of streamResponse) {
      if (event.event === 'values') {
        const messages = event.data?.messages;
        if (Array.isArray(messages) && messages.length > 0) {
          const lastMessage = messages[messages.length - 1];
          if (lastMessage?.type === 'ai' || lastMessage?.role === 'assistant') {
            assistantContent = typeof lastMessage.content === 'string' 
              ? lastMessage.content 
              : JSON.stringify(lastMessage.content);
            streamingContent = assistantContent;
          }
        }
      } else if (event.event === 'error') {
        throw new Error(event.data?.message ?? 'Stream error');
      }
    }
    
    // Add assistant message to local store
    if (assistantContent) {
      threadStore.addMessage(activeThreadId, {
        role: 'assistant',
        content: assistantContent
      });
    }
    
    streamState = {
      ...streamState,
      isStreaming: false
    };
    
  } catch (error) {
    const errorMessage = error instanceof Error ? error.message : 'Unknown error';
    streamState = {
      ...streamState,
      isStreaming: false,
      error: errorMessage
    };
    throw error;
  }
}

function clearError(): void {
  streamState = { ...streamState, error: null };
}

function resetStream(): void {
  streamState = {
    isStreaming: false,
    threadId: null,
    currentRunId: null,
    error: null
  };
  streamingContent = '';
}

// Export reactive getters and actions
export const agentStore = {
  get streamState() { return streamState; },
  get streamingContent() { return streamingContent; },
  get isStreaming() { return streamState.isStreaming; },
  get error() { return streamState.error; },
  
  sendMessage,
  clearError,
  resetStream,
  getClient
};

