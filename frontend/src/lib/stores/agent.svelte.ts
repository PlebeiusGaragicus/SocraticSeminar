// Agent store for LangGraph streaming with tool interrupt handling
// Handles direct communication with LangGraph server and client-side tool execution

import { Client } from '@langchain/langgraph-sdk';
import type { 
  PaymentRequest, 
  AgentStreamState, 
  Artifact, 
  ToolCall, 
  ToolCallWithStatus,
  ToolResult,
  ProjectFile
} from './types.js';
import { threadStore } from './threads.svelte.js';
import { artifactStore } from './artifacts.svelte.js';
import { assistantStore } from './assistants.svelte.js';
import { executeToolCalls, toolResultsToMessages } from '$lib/services/tool-executor.js';

// Configuration - LangGraph server default port is 2024
const LANGGRAPH_URL = import.meta.env.PUBLIC_LANGGRAPH_URL ?? 'http://localhost:2024';

// LangGraph client (lazy initialized)
let client: Client | null = null;

function getClient(): Client {
  if (!client) {
    client = new Client({ apiUrl: LANGGRAPH_URL });
  }
  return client;
}

// Reactive state using $state
let isStreaming = $state(false);
let isInterrupted = $state(false);
let threadId = $state<string | null>(null);
let currentRunId = $state<string | null>(null);
let error = $state<string | null>(null);
let pendingToolCalls = $state<ToolCallWithStatus[]>([]);
let streamingContent = $state<string>('');

// Track executed tool calls for saving to message
let executedToolCalls = $state<ToolCall[]>([]);

// Build project files metadata for agent context
function buildProjectFiles(): ProjectFile[] {
  const artifacts = artifactStore.artifacts;
  return artifacts.map(artifact => ({
    id: artifact.id,
    title: artifact.versions[artifact.currentVersionIndex]?.title || 'Untitled',
    file_type: 'artifact' as const
  }));
}

// Parse agent response for file edits (legacy - now handled via edit_file tool)
function parseFileEdits(content: string): { path: string; newContent: string } | null {
  const codeBlockMatch = content.match(/```(?:[\w]+)?\s*\n([\s\S]*?)```/);
  if (codeBlockMatch) {
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

// Handle edit_file tool results - set up pending changes for user approval
function handleEditFileResult(result: ToolResult): void {
  if (result.name !== 'edit_file' || result.error) return;
  
  try {
    const data = JSON.parse(result.content);
    if (data.success && data.file_id && data.new_content !== undefined) {
      artifactStore.setPendingChanges(
        data.file_id,
        data.new_content,
        data.old_content || ''
      );
    }
  } catch (e) {
    console.error('[Agent] Failed to parse edit_file result:', e);
  }
}

// Update streaming content (triggers reactivity)
function setStreamingContent(content: string) {
  streamingContent = content;
}

// Update pending tool calls (triggers reactivity)
function setPendingToolCalls(calls: ToolCallWithStatus[]) {
  pendingToolCalls = [...calls];
}

// Stream and handle a run, including tool interrupts
// Returns: { content: string, toolCalls: ToolCall[] }
async function streamWithToolHandling(
  lgClient: Client,
  lgThreadId: string,
  assistantId: string,
  input: Record<string, unknown> | null,
  projectId: string
): Promise<{ content: string; toolCalls: ToolCall[] }> {
  let assistantContent = '';
  let allToolCalls: ToolCall[] = [];
  let resumeData: unknown = null;
  let continueStreaming = true;
  
  while (continueStreaming) {
    console.log('[Agent] Starting stream iteration, input:', input ? 'provided' : 'null', 'resume:', resumeData ? 'yes' : 'no');
    
    // Build stream options
    const streamOptions: Record<string, unknown> = {};
    if (input !== null) {
      streamOptions.input = input;
    }
    
    // If we have resume data from tool execution, use command to resume
    if (resumeData !== null) {
      streamOptions.command = { resume: resumeData };
      resumeData = null; // Clear after using
    }
    
    const streamResponse = lgClient.runs.stream(
      lgThreadId,
      assistantId,
      streamOptions
    );
    
    let currentToolCalls: ToolCall[] = [];
    
    for await (const event of streamResponse) {
      // Only log non-metadata events to reduce noise
      if (event.event !== 'metadata') {
        console.log('[Agent] Stream event:', event.event);
      }
      
      if (event.event === 'values') {
        const messages = event.data?.messages;
        if (Array.isArray(messages) && messages.length > 0) {
          // Find the last AI message
          for (let i = messages.length - 1; i >= 0; i--) {
            const msg = messages[i];
            if (msg?.type === 'ai' || msg?.role === 'assistant') {
              const content = typeof msg.content === 'string' 
                ? msg.content 
                : (Array.isArray(msg.content) ? '' : JSON.stringify(msg.content));
              
              if (content) {
                assistantContent = content;
                setStreamingContent(content);
              }
              
              // Check for tool calls
              if (msg.tool_calls && msg.tool_calls.length > 0) {
                currentToolCalls = msg.tool_calls.map((tc: Record<string, unknown>) => ({
                  id: tc.id as string,
                  name: tc.name as string,
                  args: tc.args as Record<string, unknown>
                }));
                console.log('[Agent] Tool calls detected:', currentToolCalls.map(tc => tc.name));
              }
              break; // Found the last AI message
            }
          }
        }
        
        // Check for artifact updates in the event (legacy)
        const artifact = event.data?.artifact;
        if (artifact && artifact.contents && artifact.contents.length > 0) {
          const latestContent = artifact.contents[artifact.contents.length - 1];
          const existingArtifact = artifactStore.artifacts.find(a => a.id === artifact.id);
          
          if (existingArtifact) {
            const currentVersion = existingArtifact.versions[existingArtifact.currentVersionIndex];
            if (currentVersion && latestContent.content !== currentVersion.content) {
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
    
    // Check if we have pending tool calls (interrupted before tools node)
    if (currentToolCalls.length > 0) {
      // Track these tool calls
      allToolCalls = [...allToolCalls, ...currentToolCalls];
      
      // Update state to show tool calls are being executed
      isInterrupted = true;
      const toolCallsWithStatus: ToolCallWithStatus[] = currentToolCalls.map(tc => ({
        ...tc,
        status: 'executing' as const
      }));
      setPendingToolCalls(toolCallsWithStatus);
      
      console.log('[Agent] Executing tools locally...');
      
      // Execute tools locally against IndexedDB
      const results = await executeToolCalls(currentToolCalls, projectId);
      
      console.log('[Agent] Tool results:', results.map(r => ({ name: r.name, error: r.error, contentLen: r.content?.length })));
      
      // Handle edit_file results specially - set up pending changes
      for (const result of results) {
        if (result.name === 'edit_file') {
          handleEditFileResult(result);
        }
      }
      
      // Update state with completed tool calls
      setPendingToolCalls(toolCallsWithStatus.map((tc, i) => ({
        ...tc,
        status: results[i]?.error ? 'error' as const : 'completed' as const,
        result: results[i]
      })));
      
      console.log('[Agent] Tools executed, resuming graph with command...');
      
      // Convert results to LangGraph message format for resumption
      const toolMessages = toolResultsToMessages(results);
      
      // Set resume data for next iteration - using the command: { resume: ... } pattern
      // This is how LangGraph expects tool results when resuming after interrupt
      resumeData = toolMessages;
      
      // Clear input for next iteration (we're resuming, not starting fresh)
      input = null;
      
      // Clear interrupt state
      isInterrupted = false;
      
      // The while loop continues, resuming the graph with tool results
    } else {
      // No tool calls, we're done
      continueStreaming = false;
    }
  }
  
  // Clear pending tool calls now that we're done
  setPendingToolCalls([]);
  
  return { content: assistantContent, toolCalls: allToolCalls };
}

// Actions
async function sendMessage(
  message: string,
  langGraphThreadId: string | null,
  localThreadId: string,
  payment?: PaymentRequest,
  includeArtifacts: boolean = true
): Promise<{ langGraphThreadId: string }> {
  const lgClient = getClient();
  
  // Get the selected assistant ID
  const assistantId = assistantStore.selectedAssistantId || 'seminar_agent';
  
  // Get project ID from current thread
  const thread = threadStore.threads.find(t => t.id === localThreadId);
  const projectId = thread?.projectId || '';
  
  // Reset state
  isStreaming = true;
  isInterrupted = false;
  threadId = langGraphThreadId;
  currentRunId = null;
  error = null;
  setPendingToolCalls([]);
  setStreamingContent('');
  executedToolCalls = [];
  
  let activeThreadId = langGraphThreadId;
  
  try {
    // Create LangGraph thread if needed
    if (!activeThreadId) {
      const lgThread = await lgClient.threads.create();
      activeThreadId = lgThread.thread_id;
      threadId = activeThreadId;
      console.log('[Agent] Created new LangGraph thread:', activeThreadId);
    }
    
    // Build input with project files for tool context
    const input: Record<string, unknown> = {
      messages: [{ role: 'user', content: message }],
      // Inject project files metadata so agent knows what files exist
      project_files: buildProjectFiles(),
      current_project_id: projectId
    };
    
    if (payment) {
      input.payment = {
        ecash_token: payment.ecashToken,
        amount_sats: payment.amountSats
      };
    }
    
    // Include legacy artifact context if requested
    if (includeArtifacts) {
      const artifacts = artifactStore.artifacts;
      if (artifacts.length > 0) {
        input.artifact = {
          id: artifacts[0]?.id,
          project_id: artifacts[0]?.projectId,
          current_index: artifacts[0]?.currentVersionIndex ?? 0,
          contents: artifacts.map(a => {
            const v = a.versions[a.currentVersionIndex];
            return {
              index: a.currentVersionIndex,
              title: v?.title || 'Untitled',
              content: v?.content || ''
            };
          })
        };
      }
    }
    
    // Add user message to local store
    threadStore.addMessage(localThreadId, {
      role: 'user',
      content: message
    });
    
    console.log('[Agent] Starting stream for thread:', activeThreadId);
    
    // Stream with tool handling
    const result = await streamWithToolHandling(
      lgClient,
      activeThreadId,
      assistantId,
      input,
      projectId
    );
    
    console.log('[Agent] Stream completed. Content length:', result.content.length, 'Tool calls:', result.toolCalls.length);
    
    // Add assistant message to local store with tool calls
    if (result.content) {
      threadStore.addMessage(localThreadId, {
        role: 'assistant',
        content: result.content,
        toolCalls: result.toolCalls.length > 0 ? result.toolCalls : undefined
      });
      
      // Legacy: Try to parse file edits from response if no explicit update
      if (!artifactStore.pendingChanges) {
        const edit = parseFileEdits(result.content);
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
    
    // Clear streaming state
    isStreaming = false;
    isInterrupted = false;
    setStreamingContent('');
    
    return { langGraphThreadId: activeThreadId! };
    
  } catch (err) {
    const errorMessage = err instanceof Error ? err.message : 'Unknown error';
    console.error('[Agent] Error:', errorMessage);
    isStreaming = false;
    isInterrupted = false;
    error = errorMessage;
    setStreamingContent('');
    setPendingToolCalls([]);
    throw err;
  }
}

function clearError(): void {
  error = null;
}

function resetStream(): void {
  isStreaming = false;
  isInterrupted = false;
  threadId = null;
  currentRunId = null;
  error = null;
  setPendingToolCalls([]);
  setStreamingContent('');
  executedToolCalls = [];
}

// Export reactive getters and actions
export const agentStore = {
  get streamingContent() { return streamingContent; },
  get isStreaming() { return isStreaming; },
  get isInterrupted() { return isInterrupted; },
  get pendingToolCalls() { return pendingToolCalls; },
  get error() { return error; },
  get threadId() { return threadId; },
  
  sendMessage,
  clearError,
  resetStream,
  getClient
};
