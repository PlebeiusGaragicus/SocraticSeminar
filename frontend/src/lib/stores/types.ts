// Core data types for Socratic Seminar

export interface User {
  npub: string;
  pubkeyHex: string;
}

export interface Project {
  id: string;
  npub: string;
  title: string;
  createdAt: number; // Unix timestamp
  updatedAt: number;
}

export interface Thread {
  id: string;
  projectId: string;
  title: string;
  langGraphThreadId?: string; // LangGraph server's thread ID (different from local id)
  metadata?: Record<string, unknown>;
  createdAt: number;
  updatedAt: number;
}

export interface Message {
  id: string;
  threadId: string;
  role: 'user' | 'assistant' | 'system';
  content: string;
  toolCalls?: ToolCall[];
  createdAt: number;
}

// Tool call from LangGraph - matches LangChain's ToolCall structure
export interface ToolCall {
  id: string;
  name: string;
  args: Record<string, unknown>;
  type?: 'tool_call';
}

// Result from executing a tool on the client
export interface ToolResult {
  toolCallId: string;
  name: string;
  content: string;
  error?: string;
}

// Tool execution status for UI display
export type ToolExecutionStatus = 'pending' | 'executing' | 'completed' | 'error';

// Tool call with execution state for UI
export interface ToolCallWithStatus extends ToolCall {
  status: ToolExecutionStatus;
  result?: ToolResult;
}

// Project file metadata - sent to agent so it knows what files exist
// Actual content is fetched via tool calls
export interface ProjectFile {
  id: string;
  title: string;
  file_type: 'artifact' | 'document' | 'code';
}

export interface ArtifactVersion {
  index: number;
  title: string;
  content: string; // Markdown content
  createdAt: number;
}

export interface Artifact {
  id: string;
  projectId: string;
  currentVersionIndex: number;
  versions: ArtifactVersion[];
  createdAt: number;
  updatedAt: number;
}

// Payment types for agent requests
export interface PaymentRequest {
  ecashToken: string;
  amountSats: number;
}

// Agent streaming state
export interface AgentStreamState {
  isStreaming: boolean;
  threadId: string | null;
  currentRunId: string | null;
  error: string | null;
  // Interrupt state for tool execution
  isInterrupted: boolean;
  pendingToolCalls: ToolCallWithStatus[];
}
