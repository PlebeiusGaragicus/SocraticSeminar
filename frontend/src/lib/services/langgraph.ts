/**
 * LangGraph Service - SDK wrapper for Svelte
 * 
 * Provides a clean interface to the LangGraph SDK for use in Svelte components.
 * Handles streaming, thread management, and tool interrupts.
 * 
 * Architecture: Agent with Client-Side Tool Execution
 * - Agent decides when to use tools (list_files, get_file, search_files)
 * - Graph interrupts before tool execution
 * - Client executes tools locally (IndexedDB access)
 * - Client resumes graph with tool results
 */

import { Client } from '@langchain/langgraph-sdk';
import type { Message, Thread } from '@langchain/langgraph-sdk';
import type { 
	ToolCall, 
	ToolResult, 
	ProjectFile, 
	HITLInterrupt, 
	HITLDecision,
	HITLResumeResponse,
	CashuPaymentState,
	ClientToolInterrupt,
	PaymentExhaustedInterrupt,
	StoredRefund
} from '../stores/types.js';
import { 
	AUTO_APPROVE_TOOLS as autoApproveTools,
	isClientToolInterrupt,
	isPaymentExhaustedInterrupt,
	isClarificationInterrupt,
	type ClarificationInterrupt
} from '../stores/types.js';

// Re-export Message type for use in other modules
export type { Message, Thread };

// Configuration
const LANGGRAPH_URL = import.meta.env.PUBLIC_LANGGRAPH_URL ?? 'http://localhost:2024';

let clientInstance: Client | null = null;

export function getClient(apiUrl?: string): Client {
	const url = apiUrl || LANGGRAPH_URL;
	
	if (!clientInstance || apiUrl) {
		clientInstance = new Client({ apiUrl: url });
	}
	
	return clientInstance;
}

// =============================================================================
// TYPES
// =============================================================================

export interface StreamCallbacks {
	onToken?: (token: string) => void;
	onMessage?: (message: Message) => void;
	onMessagesSync?: (messages: Message[]) => void;
	onIterationStart?: (iteration: number) => void;
	onComplete?: (messages: Message[]) => void;
	onError?: (error: Error) => void;
	onThreadId?: (threadId: string) => void;
	// Tool handling callbacks
	onToolCall?: (toolCalls: ToolCall[]) => void;
	onToolExecuting?: (toolCalls: ToolCall[]) => void;
	onToolComplete?: (results: ToolResult[]) => void;
	// Human-in-the-loop callbacks (new format with action_requests/review_configs)
	onHITLInterrupt?: (interrupt: HITLInterrupt, interruptId: string) => void;
	// Client tool execution interrupt (write operations needing approval + execution)
	onClientToolInterrupt?: (interrupt: ClientToolInterrupt, interruptId: string) => void;
	// Clarification interrupt (ask_user / ask_choices)
	onClarificationInterrupt?: (interrupt: ClarificationInterrupt, interruptId: string) => void;
}

export interface SubmitOptions {
	threadId?: string | null;
	assistantId?: string;
	projectId?: string;
	projectFiles?: ProjectFile[];
	streamMode?: ('values' | 'messages' | 'updates')[];
	maxToolIterations?: number;
}

// Tool executor function type - injected by the caller
export type ToolExecutor = (toolCall: ToolCall, projectId: string) => Promise<ToolResult>;

// Default no-op executor
const defaultToolExecutor: ToolExecutor = async (toolCall) => ({
	tool_call_id: toolCall.id,
	name: toolCall.name,
	content: '',
	error: `Tool executor not configured for: ${toolCall.name}`
});

// Global tool executor - set by the agent store
let globalToolExecutor: ToolExecutor = defaultToolExecutor;

export function setToolExecutor(executor: ToolExecutor): void {
	globalToolExecutor = executor;
}

// =============================================================================
// MAIN SUBMIT FUNCTION WITH INTERRUPT HANDLING
// =============================================================================

/**
 * Submit a message to the LangGraph agent with streaming and interrupt support.
 * 
 * Flow:
 * 1. Send message to agent
 * 2. Stream response tokens
 * 3. If agent calls tools -> interrupt
 * 4. Execute tools locally via toolExecutor
 * 5. Resume agent with tool results (using updateState + null input)
 * 6. Repeat until no more tool calls
 */
export async function submitMessage(
	content: string,
	options: SubmitOptions,
	callbacks: StreamCallbacks
): Promise<{ threadId: string; messages: Message[] }> {
	const client = getClient();
	const assistantId = options.assistantId || 'seminar_agent';
	const maxIterations = options.maxToolIterations ?? 10;
	const projectId = options.projectId || '';
	
	let threadId = options.threadId;
	
	// Create thread if needed
	if (!threadId) {
		const thread = await client.threads.create();
		threadId = thread.thread_id;
		callbacks.onThreadId?.(threadId);
	}
	
	// Build the human message
	const humanMessage: Message = {
		type: 'human',
		content: content,
	};
	
	// Build input with project context
	const input: Record<string, unknown> = {
		messages: [humanMessage],
	};
	
	// Include project files metadata so agent knows what files exist
	if (options.projectFiles && options.projectFiles.length > 0) {
		input.project_files = options.projectFiles;
	}
	
	if (projectId) {
		input.current_project_id = projectId;
	}
	
	const messages: Message[] = [];
	let currentContent = '';
	let iteration = 0;
	
	// Input for the current iteration (null means resume from interrupt)
	let currentInput: Record<string, unknown> | null = input;
	
	try {
		// Loop to handle multiple tool call iterations
		while (iteration < maxIterations) {
			iteration++;
			console.log(`[LangGraph] ================================================`);
			console.log(`[LangGraph] Iteration ${iteration}/${maxIterations}`);
			console.log(`[LangGraph] Thread ID: ${threadId}`);
			console.log(`[LangGraph] ================================================`);
			
			// Signal iteration start - allows UI to reset streaming state
			callbacks.onIterationStart?.(iteration);
			currentContent = '';
			
			let interrupted = false;
			let pendingToolCalls: ToolCall[] = [];
			
			console.log(`[LangGraph] Starting stream with input:`, currentInput === null ? 'null (resume)' : 'new message');
			
			// Stream the response
			const stream = client.runs.stream(threadId, assistantId, {
				input: currentInput,
				streamMode: options.streamMode || ['messages', 'values'],
			});
			
			for await (const event of stream) {
				// Log all events for debugging
				console.log('[LangGraph] Stream event:', event.event, 
					event.event === 'values' ? '(state snapshot)' : 
					event.event === 'messages/partial' ? '(streaming chunk)' :
					event.event === 'messages/complete' ? '(message complete)' : '');
				
				// Handle streaming message chunks (incremental AI content)
				if (event.event === 'messages/partial') {
					const chunks = event.data as Array<{ type: string; content?: string; tool_calls?: unknown[] }>;
					if (chunks && chunks.length > 0) {
						const lastChunk = chunks[chunks.length - 1];
						if (lastChunk?.type === 'ai' && lastChunk.content) {
							const newContent = lastChunk.content;
							if (newContent.length > currentContent.length) {
								const newTokens = newContent.slice(currentContent.length);
								callbacks.onToken?.(newTokens);
								currentContent = newContent;
							}
						}
						// Detect tool calls early from streaming
						if (lastChunk?.type === 'ai' && lastChunk.tool_calls && lastChunk.tool_calls.length > 0) {
							const toolCalls = (lastChunk.tool_calls as Array<{ id: string; name: string; args?: Record<string, unknown> }>).map((tc) => ({
								id: tc.id,
								name: tc.name,
								args: tc.args || {},
							}));
							callbacks.onToolCall?.(toolCalls);
						}
					}
				}
				
				// Handle complete message events
				if (event.event === 'messages/complete') {
					const completeMessages = event.data as Message[];
					if (completeMessages && completeMessages.length > 0) {
						const lastMsg = completeMessages[completeMessages.length - 1];
						if (lastMsg) {
							callbacks.onMessage?.(lastMsg);
						}
					}
				}
				
				// Handle values events (full state snapshots)
				if (event.event === 'values') {
					const data = event.data as { messages?: Message[] };
					console.log('[LangGraph] Values event data:', 
						data.messages ? `${data.messages.length} messages` : 'no messages',
						data.messages?.map(m => ({ type: m.type, hasContent: !!(m as { content?: string }).content, hasToolCalls: !!((m as { tool_calls?: unknown[] }).tool_calls?.length) }))
					);
					
					if (data.messages) {
						messages.length = 0;
						messages.push(...data.messages);
						
						// Sync full message state to UI
						callbacks.onMessagesSync?.(messages);
						console.log('[LangGraph] Messages synced to UI:', messages.length);
						
						// Get the latest message
						const lastMessage = messages[messages.length - 1];
						console.log('[LangGraph] Last message:', lastMessage?.type, 
							'content:', typeof (lastMessage as { content?: unknown }).content,
							'tool_calls:', (lastMessage as { tool_calls?: unknown[] }).tool_calls?.length || 0);
						
						// Check for tool calls (indicates interrupt)
						if (lastMessage?.type === 'ai' && (lastMessage as { tool_calls?: unknown[] }).tool_calls?.length) {
							pendingToolCalls = ((lastMessage as { tool_calls: Array<{ id: string; name: string; args?: Record<string, unknown> }> }).tool_calls).map((tc) => ({
								id: tc.id,
								name: tc.name,
								args: tc.args || {},
							}));
							interrupted = true;
							console.log('[LangGraph] Tool calls detected:', pendingToolCalls.map(tc => tc.name));
							callbacks.onToolCall?.(pendingToolCalls);
						}
						
						// Reset content tracker for next iteration
						if (lastMessage?.type === 'ai') {
							currentContent = typeof lastMessage.content === 'string' ? lastMessage.content : '';
						}
					}
				}
			}
			
			console.log(`[LangGraph] Stream ended. Interrupted: ${interrupted}, Pending tools: ${pendingToolCalls.length}`);
			console.log(`[LangGraph] Pending tool calls:`, pendingToolCalls.map(tc => ({ name: tc.name, args: tc.args })));
			
			// ALWAYS check for Human-in-the-Loop interrupt by examining thread state
			// This is necessary because HITL interrupts may not show tool_calls in the
			// streamed messages (the inner agent throws GraphInterrupt before returning)
			console.log('[LangGraph] Checking thread state for HITL interrupt...');
			try {
				const threadState = await client.threads.getState(threadId);
				console.log('[LangGraph] Thread state:', JSON.stringify(threadState, null, 2));
				const tasks = (threadState as { tasks?: Array<{ id?: string; interrupts?: Array<{ value?: unknown }> }> }).tasks;
				console.log('[LangGraph] Tasks:', tasks?.length ?? 0);
				
				if (tasks && tasks.length > 0) {
					const task = tasks[0];
					const interrupts = task.interrupts;
					console.log('[LangGraph] Task interrupts:', interrupts?.length ?? 0);
					
					if (interrupts && interrupts.length > 0) {
						const interruptData = interrupts[0];
						const interruptValue = interruptData.value;
						const interruptId = (interruptData as { id?: string }).id || task.id || '';
						console.log('[LangGraph] Interrupt value:', JSON.stringify(interruptValue, null, 2));
						console.log('[LangGraph] Interrupt ID:', interruptId);
						
						// Check for ClientToolsMiddleware interrupt FIRST (has type: "client_tool_execution")
						// These require tool execution on the client side before resuming
						const isClientTool = isClientToolInterrupt(interruptValue);
						console.log('[LangGraph] Is client tool interrupt?', isClientTool);
						
						if (isClientTool) {
							console.log('[LangGraph] Client tool interrupt detected:', 
								interruptValue.tool_calls.map(tc => tc.name));
							
							// Client tool interrupts: execute tools locally then resume
							if (interruptValue.auto_approve) {
								// Read-only tools - execute immediately
								console.log('[LangGraph] Auto-executing read-only client tools');
								
								if (!toolExecutor) {
									throw new Error('Tool executor not set. Call setToolExecutor first.');
								}
								
								const toolResults = await Promise.all(
									interruptValue.tool_calls.map(async (tc) => {
										const result = await toolExecutor(
											{ id: tc.id, name: tc.name, args: tc.args },
											projectId || ''
										);
										return result;
									})
								);
								
								console.log('[LangGraph] Tool results:', toolResults);
								
								// Resume with tool results
								const resumePayload = { 
									[interruptId]: { 
										tool_results: toolResults.map(r => ({
											tool_call_id: r.tool_call_id,
											content: r.error || r.content,
											status: r.error ? 'error' : 'success',
										}))
									} 
								};
								
								const resumeStream = client.runs.stream(threadId, assistantId, {
									input: null,
									command: { resume: resumePayload },
									streamMode: options.streamMode || ['messages', 'values'],
								});
								
								for await (const resumeEvent of resumeStream) {
									if (resumeEvent.event === 'messages/partial') {
										const chunks = resumeEvent.data as Array<{ type: string; content?: string; tool_calls?: unknown[] }>;
										if (chunks && chunks.length > 0) {
											const lastChunk = chunks[chunks.length - 1];
											if (lastChunk?.type === 'ai' && lastChunk.content) {
												const newContent = lastChunk.content;
												if (newContent.length > currentContent.length) {
													const newTokens = newContent.slice(currentContent.length);
													callbacks.onToken?.(newTokens);
													currentContent = newContent;
												}
											}
										}
									}
									
									if (resumeEvent.event === 'values') {
										const data = resumeEvent.data as { messages?: Message[] };
										if (data.messages) {
											messages.length = 0;
											messages.push(...data.messages);
											callbacks.onMessagesSync?.(messages);
										}
									}
								}
								
								// Check for more tool calls
								const lastMsg = messages[messages.length - 1];
								if (lastMsg?.type === 'ai' && (lastMsg as { tool_calls?: unknown[] }).tool_calls?.length) {
									pendingToolCalls = ((lastMsg as { tool_calls: Array<{ id: string; name: string; args?: Record<string, unknown> }> }).tool_calls).map((tc) => ({
										id: tc.id,
										name: tc.name,
										args: tc.args || {},
									}));
									interrupted = true;
									callbacks.onToolCall?.(pendingToolCalls);
									continue;
								} else {
									interrupted = false;
									break;
								}
							} else {
								// Write tools - need approval first, notify UI with client tool interrupt
								console.log('[LangGraph] Client tool requires approval - notifying UI');
								callbacks.onClientToolInterrupt?.(interruptValue, interruptId);
								return { threadId, messages };
							}
						}
						
						// Check if this is a HITL interrupt (has action_requests and review_configs)
						const isHITL = isHITLInterrupt(interruptValue);
						console.log('[LangGraph] Is HITL interrupt?', isHITL);
						
						if (isHITL) {
							console.log('[LangGraph] HITL interrupt detected:', 
								interruptValue.action_requests.map(a => a.name));
							
							// Check if all actions should be auto-approved (read-only tools)
							const autoApprove = shouldAutoApprove(interruptValue);
							console.log('[LangGraph] Should auto-approve?', autoApprove);
							
							if (autoApprove) {
								console.log('[LangGraph] Auto-approving read-only tools:', 
									interruptValue.action_requests.map(a => a.name));
								const autoResponse = createAutoApproveResponse(interruptValue);
								
								// Resume with auto-approve - set up for next iteration
								const resumePayload = { [interruptId]: autoResponse };
								
								// Stream the resumed execution
								const resumeStream = client.runs.stream(threadId, assistantId, {
									input: null,
									command: { resume: resumePayload },
									streamMode: options.streamMode || ['messages', 'values'],
								});
								
								// Process the resume stream
								for await (const resumeEvent of resumeStream) {
									if (resumeEvent.event === 'messages/partial') {
										const chunks = resumeEvent.data as Array<{ type: string; content?: string; tool_calls?: unknown[] }>;
										if (chunks && chunks.length > 0) {
											const lastChunk = chunks[chunks.length - 1];
											if (lastChunk?.type === 'ai' && lastChunk.content) {
												const newContent = lastChunk.content;
												if (newContent.length > currentContent.length) {
													const newTokens = newContent.slice(currentContent.length);
													callbacks.onToken?.(newTokens);
													currentContent = newContent;
												}
											}
										}
									}
									
									if (resumeEvent.event === 'values') {
										const data = resumeEvent.data as { messages?: Message[] };
										if (data.messages) {
											messages.length = 0;
											messages.push(...data.messages);
											callbacks.onMessagesSync?.(messages);
										}
									}
								}
								
								// After resume stream - check if we're done or need another iteration
								const lastMsg = messages[messages.length - 1];
								if (lastMsg?.type === 'ai' && (lastMsg as { tool_calls?: unknown[] }).tool_calls?.length) {
									// More tool calls - continue the loop
									pendingToolCalls = ((lastMsg as { tool_calls: Array<{ id: string; name: string; args?: Record<string, unknown> }> }).tool_calls).map((tc) => ({
										id: tc.id,
										name: tc.name,
										args: tc.args || {},
									}));
									interrupted = true;
									callbacks.onToolCall?.(pendingToolCalls);
									continue;
								} else {
									// No more tool calls - we're done
									interrupted = false;
									break;
								}
							}
							
							// Not auto-approvable - notify UI and return
							console.log('[LangGraph] HITL interrupt requires human approval - notifying UI');
							callbacks.onHITLInterrupt?.(interruptValue, interruptId);
							return { threadId, messages };
						}
						
						// Check if this is a clarification interrupt (ask_user / ask_choices)
						const isClarify = isClarificationInterrupt(interruptValue);
						console.log('[LangGraph] Is clarification interrupt?', isClarify);
						
						if (isClarify) {
							console.log('[LangGraph] Clarification interrupt detected:', interruptValue.tool);
							callbacks.onClarificationInterrupt?.(interruptValue, interruptId);
							return { threadId, messages };
						} else {
							console.log('[LangGraph] Interrupt value is not a recognized format');
						}
					} else {
						console.log('[LangGraph] No interrupts found in task');
					}
				} else {
					console.log('[LangGraph] No tasks found in thread state');
				}
			} catch (stateError) {
				console.warn('[LangGraph] Could not check thread state for HITL:', stateError);
			}
			
			// If no tool calls detected in messages, we're done
			// (HITL interrupt would have been handled above if present)
			if (!interrupted && pendingToolCalls.length === 0) {
				console.log('[LangGraph] No tool calls and no HITL interrupt - completing');
				break;
			}
			
			// Not a HITL interrupt - execute tools locally (automatic tool execution)
			console.log('[LangGraph] No HITL interrupt detected, falling through to local tool execution');
			if (!projectId) {
				console.warn('[LangGraph] Tool calls require projectId but none provided');
			}
			
			callbacks.onToolExecuting?.(pendingToolCalls);
			console.log('[LangGraph] Executing tools locally:', pendingToolCalls.map(tc => tc.name));
			
			const toolResults = await Promise.all(
				pendingToolCalls.map(tc => globalToolExecutor(tc, projectId))
			);
			
			callbacks.onToolComplete?.(toolResults);
			console.log('[LangGraph] Tool results:', toolResults.map(r => ({
				id: r.tool_call_id,
				hasResult: !!r.content,
				error: r.error
			})));
			
			// Build tool messages to send back
			const toolMessages = toolResults.map(r => ({
				type: 'tool' as const,
				tool_call_id: r.tool_call_id,
				name: r.name,
				content: r.error 
					? JSON.stringify({ error: r.error })
					: r.content,
			}));
			
			console.log('[LangGraph] Updating thread state with tool results...');
			
			// Update thread state with tool results using asNode pattern
			try {
				await client.threads.updateState(threadId, {
					values: {
						messages: toolMessages,
					},
					asNode: 'tools',
				});
				console.log('[LangGraph] Thread state updated successfully');
			} catch (updateError) {
				console.error('[LangGraph] Failed to update thread state:', updateError);
				throw updateError;
			}
			
			// Resume with null input (continue from where we left off)
			currentInput = null;
			console.log('[LangGraph] Resuming graph execution with null input...');
		}
		
		if (iteration >= maxIterations) {
			console.warn(`[LangGraph] Reached max tool iterations (${maxIterations})`);
		}
		
		console.log('[LangGraph] Calling onComplete with', messages.length, 'messages');
		console.log('[LangGraph] Final messages:', messages.map(m => ({ 
			type: m.type, 
			content: typeof (m as { content?: unknown }).content === 'string' 
				? (m as { content: string }).content.substring(0, 100) + '...' 
				: typeof (m as { content?: unknown }).content 
		})));
		callbacks.onComplete?.(messages);
		
		return { threadId, messages };
		
	} catch (error) {
		callbacks.onError?.(error as Error);
		throw error;
	}
}

// =============================================================================
// HUMAN-IN-THE-LOOP HELPERS
// =============================================================================

/**
 * Check if an interrupt value matches the HITLInterrupt schema.
 * This is the format returned by HumanInTheLoopMiddleware.
 */
export function isHITLInterrupt(value: unknown): value is HITLInterrupt {
	if (!value || typeof value !== 'object') return false;
	
	const obj = value as Record<string, unknown>;
	
	// Check for required fields: action_requests and review_configs
	return (
		'action_requests' in obj && 
		Array.isArray(obj.action_requests) &&
		'review_configs' in obj &&
		Array.isArray(obj.review_configs)
	);
}

/**
 * Check if all action requests in an interrupt should be auto-approved.
 * Returns true if all actions are read-only tools that don't need human approval.
 */
export function shouldAutoApprove(interrupt: HITLInterrupt): boolean {
	return interrupt.action_requests.every(
		action => autoApproveTools.includes(action.name)
	);
}

/**
 * Create auto-approve decisions for all actions in an interrupt.
 */
export function createAutoApproveResponse(interrupt: HITLInterrupt): HITLResumeResponse {
	return {
		decisions: interrupt.action_requests.map(() => ({ type: 'approve' as const }))
	};
}

/**
 * Resume a thread with HITL decisions after an interrupt.
 * 
 * @param threadId - The thread ID to resume
 * @param interruptId - The interrupt ID from the thread state
 * @param response - The HITL resume response with decisions
 * @param assistantId - The assistant ID to use
 * @param callbacks - Stream callbacks for the resumed execution
 */
export async function resumeWithHITLDecisions(
	threadId: string,
	interruptId: string,
	response: HITLResumeResponse,
	assistantId: string,
	callbacks: StreamCallbacks
): Promise<{ threadId: string; messages: Message[] }> {
	const client = getClient();
	const messages: Message[] = [];
	let currentContent = '';
	
	// Build the resume payload: { [interrupt_id]: { decisions: [...] } }
	const resumePayload = {
		[interruptId]: response
	};
	
	console.log('[LangGraph] Resuming with HITL decisions:', resumePayload);
	
	try {
		// Stream the response with resume command
		const stream = client.runs.stream(threadId, assistantId, {
			input: null, // null input means resume from interrupt
			command: {
				resume: resumePayload,
			},
			streamMode: ['messages', 'values'],
		});
		
		for await (const event of stream) {
			// Handle streaming message chunks
			if (event.event === 'messages/partial') {
				const chunks = event.data as Array<{ type: string; content?: string; tool_calls?: unknown[] }>;
				if (chunks && chunks.length > 0) {
					const lastChunk = chunks[chunks.length - 1];
					if (lastChunk?.type === 'ai' && lastChunk.content) {
						const newContent = lastChunk.content;
						if (newContent.length > currentContent.length) {
							const newTokens = newContent.slice(currentContent.length);
							callbacks.onToken?.(newTokens);
							currentContent = newContent;
						}
					}
					// Check for new tool calls
					if (lastChunk?.type === 'ai' && lastChunk.tool_calls && lastChunk.tool_calls.length > 0) {
						const toolCalls = (lastChunk.tool_calls as Array<{ id: string; name: string; args?: Record<string, unknown> }>).map((tc) => ({
							id: tc.id,
							name: tc.name,
							args: tc.args || {},
						}));
						callbacks.onToolCall?.(toolCalls);
					}
				}
			}
			
			// Handle values events (full state snapshots)
			if (event.event === 'values') {
				const data = event.data as { messages?: Message[] };
				
				if (data.messages) {
					messages.length = 0;
					messages.push(...data.messages);
					callbacks.onMessagesSync?.(messages);
					
					// Check for tool calls in last message
					const lastMessage = messages[messages.length - 1];
					if (lastMessage?.type === 'ai' && (lastMessage as { tool_calls?: unknown[] }).tool_calls?.length) {
						const toolCalls = ((lastMessage as { tool_calls: Array<{ id: string; name: string; args?: Record<string, unknown> }> }).tool_calls).map((tc) => ({
							id: tc.id,
							name: tc.name,
							args: tc.args || {},
						}));
						callbacks.onToolCall?.(toolCalls);
					}
				}
			}
		}
		
		// After stream ends, check thread state for interrupts
		// The backend may have triggered another interrupt during the resume
		console.log('[LangGraph] Resume stream ended, checking for interrupts...');
		try {
			const threadState = await client.threads.getState(threadId);
			const tasks = (threadState as { tasks?: Array<{ id?: string; interrupts?: Array<{ value?: unknown; id?: string }> }> }).tasks;
			
			if (tasks && tasks.length > 0) {
				const task = tasks[0];
				const interrupts = task.interrupts;
				
				if (interrupts && interrupts.length > 0) {
					const interruptData = interrupts[0];
					const interruptValue = interruptData.value;
					const newInterruptId = (interruptData as { id?: string }).id || task.id || '';
					
					// Check for clarification interrupt
					if (isClarificationInterrupt(interruptValue)) {
						console.log('[LangGraph] Clarification interrupt detected after resume');
						callbacks.onClarificationInterrupt?.(interruptValue, newInterruptId);
						return { threadId, messages };
					}
					
					// Check for client tool interrupt
					if (isClientToolInterrupt(interruptValue)) {
						console.log('[LangGraph] Client tool interrupt detected after resume');
						callbacks.onClientToolInterrupt?.(interruptValue, newInterruptId);
						return { threadId, messages };
					}
					
					// Check for HITL interrupt
					if (isHITLInterrupt(interruptValue)) {
						console.log('[LangGraph] HITL interrupt detected after resume:', 
							interruptValue.action_requests.map(a => a.name));
						callbacks.onHITLInterrupt?.(interruptValue, newInterruptId);
						return { threadId, messages };
					}
				}
			}
		} catch (stateError) {
			console.warn('[LangGraph] Could not check thread state after resume:', stateError);
		}
		
		callbacks.onComplete?.(messages);
		return { threadId, messages };
		
	} catch (error) {
		callbacks.onError?.(error as Error);
		throw error;
	}
}

// =============================================================================
// THREAD MANAGEMENT
// =============================================================================

/**
 * Get all threads.
 */
export async function getThreads(): Promise<Thread[]> {
	const client = getClient();
	const threads = await client.threads.search();
	return threads;
}

/**
 * Get a specific thread by ID.
 */
export async function getThread(threadId: string): Promise<Thread> {
	const client = getClient();
	return await client.threads.get(threadId);
}

/**
 * Get the message history for a thread.
 */
export async function getThreadMessages(threadId: string): Promise<Message[]> {
	const client = getClient();
	const state = await client.threads.getState(threadId);
	return (state.values as { messages?: Message[] })?.messages || [];
}

/**
 * Delete a thread.
 */
export async function deleteThread(threadId: string): Promise<void> {
	const client = getClient();
	await client.threads.delete(threadId);
}

/**
 * Create a new thread.
 */
export async function createThread(metadata?: Record<string, unknown>): Promise<Thread> {
	const client = getClient();
	return await client.threads.create({ metadata });
}

/**
 * Check if the LangGraph server is available.
 */
export async function checkHealth(): Promise<boolean> {
	try {
		const response = await fetch(`${LANGGRAPH_URL}/ok`, {
			method: 'GET',
			headers: { 'Accept': 'application/json' },
		});
		return response.ok;
	} catch (error) {
		console.warn('LangGraph health check failed:', error);
		return false;
	}
}

// =============================================================================
// CASHU PAYMENT HELPERS
// =============================================================================

/**
 * Extract payment state from thread state.
 */
export async function getPaymentState(threadId: string): Promise<CashuPaymentState | null> {
	try {
		const client = getClient();
		const state = await client.threads.getState(threadId);
		const values = state.values as Record<string, unknown>;
		
		if (!values) return null;
		
		// Check if payment state fields exist
		if (!('payment_status' in values)) return null;
		
		return {
			payment_token: (values.payment_token as string) || null,
			payment_balance_sats: (values.payment_balance_sats as number) || 0,
			payment_spent_sats: (values.payment_spent_sats as number) || 0,
			payment_refund_token: (values.payment_refund_token as string) || null,
			payment_status: (values.payment_status as CashuPaymentState['payment_status']) || 'pending',
			payment_refund_claimed: (values.payment_refund_claimed as boolean) || false,
		};
	} catch (error) {
		console.warn('[LangGraph] Could not get payment state:', error);
		return null;
	}
}

/**
 * Check if a thread has an unclaimed refund.
 * Used for session recovery - detects refunds that weren't claimed due to session interruption.
 */
export async function checkForUnclaimedRefund(threadId: string): Promise<StoredRefund | null> {
	try {
		const paymentState = await getPaymentState(threadId);
		
		if (!paymentState) return null;
		
		// Check if there's a refund token that hasn't been claimed
		if (
			paymentState.payment_refund_token &&
			!paymentState.payment_refund_claimed &&
			paymentState.payment_balance_sats > 0
		) {
			return {
				id: `refund-${threadId}-${Date.now()}`,
				threadId,
				refundToken: paymentState.payment_refund_token,
				amountSats: paymentState.payment_balance_sats,
				createdAt: Date.now(),
				claimed: false,
			};
		}
		
		return null;
	} catch (error) {
		console.warn('[LangGraph] Could not check for unclaimed refund:', error);
		return null;
	}
}

/**
 * Resume a thread with additional payment after funds exhausted.
 */
export async function resumeWithPayment(
	threadId: string,
	interruptId: string,
	paymentToken: string,
	assistantId: string,
	callbacks: StreamCallbacks
): Promise<{ threadId: string; messages: Message[] }> {
	// The resume payload includes the new payment token
	const resumePayload = {
		[interruptId]: {
			payment_token: paymentToken,
		}
	};
	
	console.log('[LangGraph] Resuming with additional payment');
	
	const client = getClient();
	const messages: Message[] = [];
	let currentContent = '';
	
	try {
		const stream = client.runs.stream(threadId, assistantId, {
			input: null,
			command: { resume: resumePayload },
			streamMode: ['messages', 'values'],
		});
		
		for await (const event of stream) {
			if (event.event === 'messages/partial') {
				const chunks = event.data as Array<{ type: string; content?: string }>;
				if (chunks && chunks.length > 0) {
					const lastChunk = chunks[chunks.length - 1];
					if (lastChunk?.type === 'ai' && lastChunk.content) {
						const newContent = lastChunk.content;
						if (newContent.length > currentContent.length) {
							callbacks.onToken?.(newContent.slice(currentContent.length));
							currentContent = newContent;
						}
					}
				}
			}
			
			if (event.event === 'values') {
				const data = event.data as { messages?: Message[] };
				if (data.messages) {
					messages.length = 0;
					messages.push(...data.messages);
					callbacks.onMessagesSync?.(messages);
				}
			}
		}
		
		// Check for interrupts after payment resume
		try {
			const threadState = await client.threads.getState(threadId);
			const tasks = (threadState as { tasks?: Array<{ id?: string; interrupts?: Array<{ value?: unknown; id?: string }> }> }).tasks;
			
			if (tasks && tasks.length > 0) {
				const task = tasks[0];
				const interrupts = task.interrupts;
				
				if (interrupts && interrupts.length > 0) {
					const interruptData = interrupts[0];
					const interruptValue = interruptData.value;
					const newInterruptId = (interruptData as { id?: string }).id || task.id || '';
					
					if (isClarificationInterrupt(interruptValue)) {
						callbacks.onClarificationInterrupt?.(interruptValue, newInterruptId);
						return { threadId, messages };
					}
					
					if (isClientToolInterrupt(interruptValue)) {
						callbacks.onClientToolInterrupt?.(interruptValue, newInterruptId);
						return { threadId, messages };
					}
					
					if (isHITLInterrupt(interruptValue)) {
						callbacks.onHITLInterrupt?.(interruptValue, newInterruptId);
						return { threadId, messages };
					}
				}
			}
		} catch (stateError) {
			console.warn('[LangGraph] Could not check thread state after payment resume:', stateError);
		}
		
		callbacks.onComplete?.(messages);
		return { threadId, messages };
		
	} catch (error) {
		callbacks.onError?.(error as Error);
		throw error;
	}
}

/**
 * Resume a thread with client tool execution results.
 * Used after ClientToolsMiddleware interrupts for file operations.
 */
export async function resumeWithToolResults(
	threadId: string,
	interruptId: string,
	toolResults: ToolResult[],
	assistantId: string,
	callbacks: StreamCallbacks
): Promise<{ threadId: string; messages: Message[] }> {
	const resumePayload = {
		[interruptId]: {
			tool_results: toolResults.map(r => ({
				tool_call_id: r.tool_call_id,
				content: r.error ? JSON.stringify({ error: r.error }) : r.content,
			})),
		}
	};
	
	console.log('[LangGraph] Resuming with tool results:', toolResults.map(r => r.tool_call_id));
	
	const client = getClient();
	const messages: Message[] = [];
	let currentContent = '';
	
	try {
		const stream = client.runs.stream(threadId, assistantId, {
			input: null,
			command: { resume: resumePayload },
			streamMode: ['messages', 'values'],
		});
		
		for await (const event of stream) {
			if (event.event === 'messages/partial') {
				const chunks = event.data as Array<{ type: string; content?: string }>;
				if (chunks && chunks.length > 0) {
					const lastChunk = chunks[chunks.length - 1];
					if (lastChunk?.type === 'ai' && lastChunk.content) {
						const newContent = lastChunk.content;
						if (newContent.length > currentContent.length) {
							callbacks.onToken?.(newContent.slice(currentContent.length));
							currentContent = newContent;
						}
					}
				}
			}
			
			if (event.event === 'values') {
				const data = event.data as { messages?: Message[] };
				if (data.messages) {
					messages.length = 0;
					messages.push(...data.messages);
					callbacks.onMessagesSync?.(messages);
				}
			}
		}
		
		// Check for another interrupt after resume
		try {
			const threadState = await client.threads.getState(threadId);
			const tasks = (threadState as { tasks?: Array<{ id?: string; interrupts?: Array<{ value?: unknown; id?: string }> }> }).tasks;
			
			if (tasks && tasks.length > 0) {
				const task = tasks[0];
				const interrupts = task.interrupts;
				
				if (interrupts && interrupts.length > 0) {
					const interruptData = interrupts[0];
					const interruptValue = interruptData.value;
					const newInterruptId = (interruptData as { id?: string }).id || task.id || '';
					
					// Check for clarification interrupt
					if (isClarificationInterrupt(interruptValue)) {
						console.log('[LangGraph] Clarification interrupt detected after tool resume');
						callbacks.onClarificationInterrupt?.(interruptValue, newInterruptId);
						return { threadId, messages };
					}
					
					// Check for client tool interrupt
					if (isClientToolInterrupt(interruptValue)) {
						console.log('[LangGraph] Client tool interrupt detected after tool resume');
						callbacks.onClientToolInterrupt?.(interruptValue, newInterruptId);
						return { threadId, messages };
					}
					
					// Check for HITL interrupt
					if (isHITLInterrupt(interruptValue)) {
						callbacks.onHITLInterrupt?.(interruptValue, newInterruptId);
						return { threadId, messages };
					}
				}
			}
		} catch (stateError) {
			console.warn('[LangGraph] Could not check thread state after tool resume:', stateError);
		}
		
		callbacks.onComplete?.(messages);
		return { threadId, messages };
		
	} catch (error) {
		callbacks.onError?.(error as Error);
		throw error;
	}
}

