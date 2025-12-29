// Core data types for Socratic Seminar

export interface User {
  npub: string;
  pubkeyHex: string;
}

// =============================================================================
// AGENT SCRATCH FILES & TODOS (visible to user, read-only)
// =============================================================================

/**
 * Scratch file data from agent state.
 * These are agent's working memory files - visible to user for transparency.
 */
export interface ScratchFile {
  path: string;
  content: string[];  // Lines of the file
  created_at?: string;
  modified_at?: string;
}

/**
 * Todo item from TodoListMiddleware.
 */
export interface TodoItem {
  id?: string;  // Optional - may not be sent by backend
  content: string;
  status: 'pending' | 'in_progress' | 'completed' | 'cancelled';
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
// Content is included so the agent can read files server-side
export interface ProjectFile {
  id: string;
  title: string;
  file_type: 'artifact' | 'document' | 'code';
  content?: string;  // Optional: included for file reading via get_file tool
  tags?: string[];   // Optional: tags for organization and filtering
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
  tags?: string[];     // Tags for organization and filtering
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
export const AUTO_APPROVE_TOOLS = ['list_files', 'read_file', 'search_files', 'grep_files', 'glob_files'];

// Write tools that require human approval
export const WRITE_TOOLS = ['write_file', 'edit_file', 'tag_file'];

// =============================================================================
// CASHU PAYMENT TYPES
// =============================================================================

/** Payment status values */
export type PaymentStatus = 'pending' | 'active' | 'exhausted' | 'completed' | 'error' | 'refunded';

/**
 * Cashu payment state from the agent.
 * Tracks streaming micropayment lifecycle.
 */
export interface CashuPaymentState {
  /** Original token from client */
  payment_token: string | null;
  
  /** Remaining balance in satoshis */
  payment_balance_sats: number;
  
  /** Total spent this session */
  payment_spent_sats: number;
  
  /** Refund token for unused balance (for session recovery) */
  payment_refund_token: string | null;
  
  /** Current payment status */
  payment_status: PaymentStatus;
  
  /** Whether refund has been claimed by client */
  payment_refund_claimed: boolean;
}

/**
 * Payment interrupt when funds are exhausted.
 */
export interface PaymentExhaustedInterrupt {
  type: 'payment_exhausted';
  spent_sats: number;
  message: string;
  action_requests: HITLActionRequest[];
  review_configs: HITLReviewConfig[];
}

/**
 * Client tool execution interrupt format from ClientToolsMiddleware.
 */
export interface ClientToolInterrupt {
  type: 'client_tool_execution';
  tool_calls: Array<{
    id: string;
    name: string;
    args: Record<string, unknown>;
  }>;
  /** True if tools can be auto-executed without approval */
  auto_approve: boolean;
  /** True if human approval is required */
  requires_approval: boolean;
  /** HITL data for approval UI (only for write tools) */
  action_requests?: HITLActionRequest[];
  review_configs?: HITLReviewConfig[];
}

/**
 * Clarification request interrupt from ClarifyWithHumanMiddleware.
 */
export interface ClarificationInterrupt {
  type: 'clarification_request';
  /** Tool that triggered this: 'ask_user' or 'ask_choices' */
  tool: 'ask_user' | 'ask_choices';
  /** Tool call ID for resumption */
  tool_call_id: string;
  /** The question being asked */
  question: string;
  /** Options for ask_choices (empty for ask_user) */
  options?: Array<{ id: string; label: string }>;
  /** Allow multiple selections (ask_choices only) */
  allow_multiple?: boolean;
  /** Allow free-form text input (ask_choices only) */
  allow_freeform?: boolean;
}

/**
 * Response to a clarification request.
 */
export interface ClarificationResponse {
  /** For ask_user: the user's text response */
  response?: string;
  /** For ask_choices: selected option IDs */
  selected?: string[];
  /** For ask_choices with allow_freeform: optional free text */
  freeform?: string;
}

/**
 * Check if an interrupt is a clarification request.
 */
export function isClarificationInterrupt(value: unknown): value is ClarificationInterrupt {
  if (!value || typeof value !== 'object') return false;
  const obj = value as Record<string, unknown>;
  return obj.type === 'clarification_request' && typeof obj.tool === 'string';
}

/**
 * Stored refund record for session recovery.
 * Tracked in IndexedDB to detect unswiped refunds on reload.
 */
export interface StoredRefund {
  id: string;
  threadId: string;
  refundToken: string;
  amountSats: number;
  createdAt: number;
  claimed: boolean;
  claimedAt?: number;
}

/**
 * Check if an interrupt is a payment exhausted interrupt.
 */
export function isPaymentExhaustedInterrupt(value: unknown): value is PaymentExhaustedInterrupt {
  if (!value || typeof value !== 'object') return false;
  const obj = value as Record<string, unknown>;
  return obj.type === 'payment_exhausted';
}

/**
 * Check if an interrupt is a client tool execution interrupt.
 */
export function isClientToolInterrupt(value: unknown): value is ClientToolInterrupt {
  if (!value || typeof value !== 'object') return false;
  const obj = value as Record<string, unknown>;
  return obj.type === 'client_tool_execution' && Array.isArray(obj.tool_calls);
}

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
