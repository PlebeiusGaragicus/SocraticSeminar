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
// Uses LangGraph SDK naming convention (tool_call_id not toolCallId)
export interface ToolResult {
  tool_call_id: string;
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
  // Human-in-the-loop interrupt
  humanInterrupt: HumanInterrupt | null;
}

// =============================================================================
// HUMAN-IN-THE-LOOP TYPES (HumanInTheLoopMiddleware format)
// =============================================================================

/**
 * Action request from the agent (from HumanInTheLoopMiddleware).
 */
export interface HITLActionRequest {
  /** Name of the tool being requested */
  name: string;
  /** Arguments for the tool */
  args: Record<string, unknown>;
  /** Description of what the agent wants to do */
  description?: string;
}

/**
 * Review configuration for an action (from HumanInTheLoopMiddleware).
 */
export interface HITLReviewConfig {
  /** Name of the action this config applies to */
  action_name: string;
  /** Allowed decisions: 'approve', 'edit', 'reject' */
  allowed_decisions: ('approve' | 'edit' | 'reject')[];
}

/**
 * Human interrupt from HumanInTheLoopMiddleware.
 * This is the actual format returned by LangGraph.
 */
export interface HITLInterrupt {
  /** Array of action requests the agent wants to perform */
  action_requests: HITLActionRequest[];
  /** Review configuration for each action */
  review_configs: HITLReviewConfig[];
}

/**
 * Decision for a single action in a HITL interrupt.
 */
export interface HITLDecision {
  /** Decision type */
  type: 'approve' | 'edit' | 'reject';
  /** For 'edit': the modified args */
  args?: Record<string, unknown>;
}

/**
 * Response to resume a HITL interrupt.
 * Format: { [interrupt_id]: { decisions: HITLDecision[] } }
 */
export interface HITLResumeResponse {
  decisions: HITLDecision[];
}

// Read-only tools that should be auto-approved (client-side execution)
export const AUTO_APPROVE_TOOLS = ['list_files', 'get_file', 'search_files'];

// =============================================================================
// LEGACY HUMAN INTERRUPT TYPES (for reference/compatibility)
// =============================================================================

/**
 * Configuration for what actions are allowed during a human interrupt.
 * @deprecated Use HITLInterrupt instead
 */
export interface HumanInterruptConfig {
  allow_accept: boolean;
  allow_ignore: boolean;
  allow_edit: boolean;
  allow_respond: boolean;
}

/**
 * @deprecated Use HITLActionRequest instead
 */
export interface ActionRequest {
  action: string;
  args: Record<string, unknown>;
}

/**
 * @deprecated Use HITLInterrupt instead
 */
export interface HumanInterrupt {
  action_request: ActionRequest;
  config: HumanInterruptConfig;
  description?: string;
}

/**
 * Response types for human interrupt.
 */
export type HumanResponseType = 'accept' | 'ignore' | 'edit' | 'response';

/**
 * Human response to an interrupt.
 */
export interface HumanResponse {
  type: HumanResponseType;
  args: string | ActionRequest;
}

/**
 * Choice option for structured questions.
 */
export interface InterruptChoice {
  id: string;
  label: string;
  description?: string;
}
