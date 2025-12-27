// Core data types for Socratic Seminar

export type ArtifactType = 'text' | 'code' | 'socratic';

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

export interface ToolCall {
  id: string;
  name: string;
  args: string;
  result?: unknown;
}

export interface ArtifactVersion {
  index: number;
  title: string;
  content: string;
  language?: string;
  createdAt: number;
}

export interface Artifact {
  id: string;
  projectId: string;
  type: ArtifactType;
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
}

