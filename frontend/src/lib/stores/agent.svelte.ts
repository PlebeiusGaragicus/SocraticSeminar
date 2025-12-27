// Agent store for LangGraph streaming
// Handles direct communication with LangGraph server

import { Client } from '@langchain/langgraph-sdk';
import type { PaymentRequest, AgentStreamState, Artifact } from './types.js';
import { threadStore } from './threads.svelte.js';
import { artifactStore } from './artifacts.svelte.js';
import { assistantStore } from './assistants.svelte.js';

// Configuration
const LANGGRAPH_URL = import.meta.env.PUBLIC_LANGGRAPH_URL ?? 'http://localhost:54367';

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

// Helper to format artifacts for agent context
function formatArtifactsForContext(artifacts: Artifact[]): string {
  if (artifacts.length === 0) return '';
  
  const parts = artifacts.map((artifact) => {
    const version = artifact.versions[artifact.currentVersionIndex];
    if (!version) return null;
    
    const header = `=== ${version.title} (${artifact.type}${version.language ? `, ${version.language}` : ''}) ===`;
    return `${header}\n${version.content}`;
  }).filter(Boolean);
  
  return parts.join('\n\n');
}

// Parse agent response for file edits
function parseFileEdits(content: string): { path: string; newContent: string } | null {
  // Look for common file edit patterns in agent responses
  // Pattern 1: Markdown code blocks with file paths
  const codeBlockMatch = content.match(/```(?:[\w]+)?\s*\n([\s\S]*?)```/);
  if (codeBlockMatch) {
    // Check if there's a file path mentioned before the code block
    const beforeBlock = content.slice(0, content.indexOf('```'));
    const pathMatch = beforeBlock.match(/(?:file|update|edit|modify)[:\s]+[`'"]*([^\s`'"]+)[`'"]*/i);
    
    if (pathMatch) {
      return {
        path: pathMatch[1],
        newContent: codeBlockMatch[1].trim()
      };
    }
  }
  
  return null;
}

// Actions
async function sendMessage(
  message: string,
  threadId: string | null,
  payment?: PaymentRequest,
  includeArtifacts: boolean = true
): Promise<void> {
  const lgClient = getClient();
  
  // Get the selected assistant ID
  const assistantId = assistantStore.selectedAssistantId || 'seminar_agent';
  
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
    
    // Build input with optional payment and artifact context
    const input: Record<string, unknown> = {
      messages: [{ role: 'user', content: message }]
    };
    
    if (payment) {
      input.payment = {
        ecash_token: payment.ecashToken,
        amount_sats: payment.amountSats
      };
    }
    
    // Include artifacts in context if requested
    if (includeArtifacts) {
      const artifacts = artifactStore.artifacts;
      if (artifacts.length > 0) {
        const artifactContext = formatArtifactsForContext(artifacts);
        if (artifactContext) {
          input.artifact = {
            id: artifacts[0]?.id,
            project_id: artifacts[0]?.projectId,
            current_index: artifacts[0]?.currentVersionIndex ?? 0,
            contents: artifacts.map(a => {
              const v = a.versions[a.currentVersionIndex];
              return {
                index: a.currentVersionIndex,
                title: v?.title || 'Untitled',
                content: v?.content || '',
                language: v?.language,
                type: a.type
              };
            })
          };
        }
      }
    }
    
    // Add user message to local store
    threadStore.addMessage(activeThreadId, {
      role: 'user',
      content: message
    });
    
    // Stream the response
    const streamResponse = lgClient.runs.stream(
      activeThreadId,
      assistantId,
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
        
        // Check for artifact updates in the event
        const artifact = event.data?.artifact;
        if (artifact && artifact.contents && artifact.contents.length > 0) {
          // Agent has proposed changes to an artifact
          const latestContent = artifact.contents[artifact.contents.length - 1];
          const existingArtifact = artifactStore.artifacts.find(a => a.id === artifact.id);
          
          if (existingArtifact) {
            const currentVersion = existingArtifact.versions[existingArtifact.currentVersionIndex];
            if (currentVersion && latestContent.content !== currentVersion.content) {
              // Set pending changes for diff view
              artifactStore.setPendingChanges(
                artifact.id,
                latestContent.content,
                currentVersion.content
              );
            }
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
      
      // Try to parse file edits from the response if no explicit artifact update
      if (!artifactStore.pendingChanges) {
        const edit = parseFileEdits(assistantContent);
        if (edit && artifactStore.currentArtifact) {
          const currentVersion = artifactStore.currentArtifact.versions[
            artifactStore.currentArtifact.currentVersionIndex
          ];
          if (currentVersion) {
            artifactStore.setPendingChanges(
              artifactStore.currentArtifact.id,
              edit.newContent,
              currentVersion.content
            );
          }
        }
      }
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
