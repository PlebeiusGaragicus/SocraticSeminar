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

export interface ProjectTag {
  name: string;
  color: string;
  deletable?: boolean;
}

export interface Project {
  id: string;
  npub: string;
  title: string;
  createdAt: number; // Unix timestamp
  updatedAt: number;
  tags?: ProjectTag[];
}

export type ThreadStatus = 'idle' | 'busy' | 'interrupted' | 'error';

// =============================================================================
// AGENT SETTINGS (per-thread configuration)
// =============================================================================

/** Available LLM models for agent use */
export type LLMModel = 'qwen3-coder-30b-a3b-instruct-mlx' | 'grok-4-1-fast-non-reasoning';

/** Agent settings configurable per-thread */
export interface AgentSettings {
  /** LLM model to use for this thread */
  llm_model: LLMModel;
  /** Maximum parallel research tasks (1-10) - deepresearch only */
  max_concurrent_research_units: number;
  /** Maximum iterations per research task (1-10) - deepresearch only */
  max_researcher_iterations: number;
  /** Enable thinking/reflection tool - deeptutor only */
  enable_thinking_tool: boolean;
}

/** Default agent settings */
export const DEFAULT_AGENT_SETTINGS: AgentSettings = {
  llm_model: 'qwen3-coder-30b-a3b-instruct-mlx',
  max_concurrent_research_units: 3,
  max_researcher_iterations: 3,
  enable_thinking_tool: true,
};

export interface Thread {
  id: string;
  projectId: string;
  title: string;
  description?: string; // Last message preview or summary
  status: ThreadStatus;
  langGraphThreadId?: string; // LangGraph server's thread ID (different from local id)
  assistantId?: string; // ID of the agent assigned to this thread
  agentSettings?: AgentSettings; // Per-thread agent configuration
  metadata?: Record<string, unknown>;
  createdAt: number;
  updatedAt: number;
  viewed?: boolean;
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
  viewed?: boolean;
  tags?: string[];
  // Dirty tracking - true if artifact has unsaved changes in liveContentMap
  isDirty?: boolean;
}

// =============================================================================
// SOURCE TYPES (Web resources for research)
// =============================================================================

/**
 * Bibliography metadata for citation purposes.
 * Extracted from web pages during scraping.
 */
export interface Bibliography {
  /** Author name, e.g., 'Karpathy, A.' or 'Stanford HAI' */
  author?: string;
  /** The title of the article, post, or page */
  title?: string;
  /** When the content was originally published (ISO string) */
  publishedDate?: string;
  /** Publisher or platform, e.g., 'X', 'Medium', 'Nature' */
  publisher?: string;
  /** Resource type, e.g., 'Post', 'Article', 'Dataset' */
  resourceType?: string;
}

/** Type of source - web URL or uploaded file */
export type SourceType = 'url' | 'file';

/** 
 * Method used to extract markdown content from a URL.
 * - 'markdownify': Built-in markdownify HTML-to-Markdown conversion
 * - 'firecrawl': Firecrawl API (better for complex/JS-heavy pages)
 * - 'manual': User-provided text
 */
export type ContentCrawlMethod = 'markdownify' | 'firecrawl' | 'manual';

/**
 * Method used to generate PDF preview.
 * - 'weasyprint': WeasyPrint HTML-to-PDF rendering
 * - 'firecrawl': Firecrawl full-page screenshot
 * - 'manual': User-uploaded PDF
 */
export type PreviewCrawlMethod = 'weasyprint' | 'firecrawl' | 'manual';

/** Allowed MIME types for file uploads */
export const ALLOWED_FILE_TYPES = [
  'application/pdf',
  'text/plain',
  'text/markdown',
  'image/png',
  'image/jpeg',
] as const;

export type AllowedMimeType = typeof ALLOWED_FILE_TYPES[number];

export interface Source {
  id: string;
  projectId: string;
  title: string;
  url: string; // URL for web sources, or filename for file sources
  content: string; // Markdown/text content (empty for binary files like PDF/images)
  bibliography?: Bibliography;
  scrapedAt?: number; // When the agent scraped the content
  metadata?: Record<string, unknown>;
  createdAt: number;
  updatedAt: number;
  viewed?: boolean;
  
  // File source fields
  sourceType?: SourceType; // 'url' (default) or 'file'
  fileHash?: string; // SHA256 hash for deduplication
  mimeType?: string; // MIME type of the file
  fileSize?: number; // File size in bytes
  blobId?: string; // Reference to blob in sourceFiles store
  
  // Preview fields (for URL sources)
  previewBlobId?: string; // Reference to preview PDF blob in sourceFiles store
  previewError?: string; // Error message if PDF generation failed
  
  // Crawl method tracking (for URL sources)
  contentMethod?: ContentCrawlMethod; // How markdown content was obtained
  previewMethod?: PreviewCrawlMethod; // How PDF preview was obtained
}

/**
 * Stored file blob for file-based sources.
 * Stored separately in sourceFiles object store.
 */
export interface SourceFile {
  id: string; // Same as blobId in Source
  sourceId: string; // Reference back to Source
  blob: Blob; // The actual file data
  createdAt: number;
}

export type TabType = 'artifact' | 'thread' | 'source';

export interface TabItem {
  id: string;
  type: TabType;
}

export interface WorkspaceState {
  leftTabs: TabItem[];
  rightTabs: TabItem[];
  activeLeftTabId: string | null;
  activeRightTabId: string | null;
  rightPanelCollapsed: boolean;
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

// Read and write tools that should be auto-approved (client-side execution)
export const AUTO_APPROVE_TOOLS = ['list_files', 'read_file', 'search_files', 'grep_files', 'glob_files', 'create_source'];

// Tools that require human approval
export const WRITE_TOOLS = ['write_file', 'patch_file'];

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
