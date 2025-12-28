<script lang="ts">
  import Send from '@lucide/svelte/icons/send';
  import MessageCircle from '@lucide/svelte/icons/message-circle';
  import Bot from '@lucide/svelte/icons/bot';
  import Loader2 from '@lucide/svelte/icons/loader-2';
  import AlertCircle from '@lucide/svelte/icons/alert-circle';
  import { Button, Textarea } from './ui/index.js';
  import AgentPicker from './AgentPicker.svelte';
  import ToolCallDisplay from './ToolCallDisplay.svelte';
  import HumanInterruptPanel from './HumanInterruptPanel.svelte';
  import ClarificationPanel from './ClarificationPanel.svelte';
  import { threadStore, agentStore, projectStore } from '$lib/stores/index.js';
  import { cyphertap } from 'cyphertap';
  import type { ToolCallWithStatus, ToolCall } from '$lib/stores/types.js';
  import { tick, onMount } from 'svelte';
  import { checkHealth, type Message as LangGraphMessage } from '$lib/services/langgraph.js';
  import { extractStringFromMessageContent } from '$lib/utils.js';

  // =============================================================================
  // TYPES
  // =============================================================================

  interface ProcessedMessage {
    id: string;
    type: 'human' | 'ai';
    content: string;
    toolCalls: ToolCallWithStatus[];
    showAvatar: boolean;
  }

  // =============================================================================
  // LOCAL STATE
  // =============================================================================

  let messageInput = $state('');
  let messagesContainer: HTMLDivElement | undefined = $state();
  let backendAvailable = $state<boolean | null>(null);

  // Track if we've loaded state for the current thread
  let loadedLangGraphThreadId = $state<string | null>(null);
  let isLoadingThreadState = $state(false);

  // =============================================================================
  // LIFECYCLE
  // =============================================================================

  // Check backend health on mount and load threads
  onMount(() => {
    checkHealth().then(available => {
      backendAvailable = available;
    });
    
    // Load threads from IndexedDB
    threadStore.loadFromStorage();
  });

  // =============================================================================
  // REACTIVE DERIVATIONS - Using simpler $derived pattern (Bug 5 fix)
  // =============================================================================

  // Core store derivations
  const currentThread = $derived(threadStore.currentThread);
  const currentProjectId = $derived(projectStore.currentProjectId);
  const isWalletReady = $derived(cyphertap.isReady);
  const persistedMessages = $derived(threadStore.currentMessages);
  
  // Agent store derivations - using direct $derived instead of $derived.by
  const isStreaming = $derived(agentStore.isStreaming);
  const isInterrupted = $derived(agentStore.isInterrupted);
  const streamingContent = $derived(agentStore.streamingContent);
  const awaitingHumanResponse = $derived(agentStore.awaitingHumanResponse);
  const langGraphMessages = $derived(agentStore.langGraphMessages);

  // =============================================================================
  // PROCESSED MESSAGES - Following reference implementation pattern (Bug 2, 3, 4 fix)
  // =============================================================================

  /**
   * Process messages following the reference implementation pattern.
   * Builds a messageMap that:
   * - Uses stable IDs from LangGraph messages
   * - Tracks tool call status by correlating tool result messages
   * - Provides unified message source to avoid flickering
   */
  const processedMessages = $derived.by((): ProcessedMessage[] => {
    // Determine which message source to use:
    // - During streaming/interrupt: use langGraphMessages (live server state)
    // - Otherwise: convert persistedMessages
    const useServerMessages = (isStreaming || awaitingHumanResponse || isInterrupted) && langGraphMessages.length > 0;
    
    if (!useServerMessages) {
      // Convert persisted messages to ProcessedMessage format
      return persistedMessages.map((msg, index) => {
        const prevMsg = index > 0 ? persistedMessages[index - 1] : null;
        return {
          id: msg.id, // Stable ID from persistence
          type: msg.role === 'user' ? 'human' : 'ai',
          content: msg.content,
          toolCalls: msg.toolCalls?.map(tc => ({
            ...tc,
            status: 'completed' as const
          })) ?? [],
          showAvatar: msg.role !== prevMsg?.role
        };
      });
    }

    // Build message map following reference pattern
    // This correlates AI messages with their tool calls and updates status from tool result messages
    const messageMap = new Map<string, { message: LangGraphMessage; toolCalls: ToolCallWithStatus[] }>();
    
    langGraphMessages.forEach((message: LangGraphMessage) => {
      if (message.type === 'ai') {
        // Extract tool calls from various possible locations
        const toolCallsInMessage: Array<{
          id?: string;
          function?: { name?: string; arguments?: unknown };
          name?: string;
          type?: string;
          args?: unknown;
          input?: unknown;
        }> = [];
        
        const msgWithKwargs = message as { additional_kwargs?: { tool_calls?: unknown[] }; tool_calls?: unknown[]; content?: unknown };
        
        if (msgWithKwargs.additional_kwargs?.tool_calls && Array.isArray(msgWithKwargs.additional_kwargs.tool_calls)) {
          toolCallsInMessage.push(...msgWithKwargs.additional_kwargs.tool_calls);
        } else if (msgWithKwargs.tool_calls && Array.isArray(msgWithKwargs.tool_calls)) {
          toolCallsInMessage.push(
            ...(msgWithKwargs.tool_calls as Array<{ name?: string }>).filter(tc => tc.name !== '')
          );
        } else if (Array.isArray(msgWithKwargs.content)) {
          const toolUseBlocks = (msgWithKwargs.content as Array<{ type?: string }>).filter(block => block.type === 'tool_use');
          toolCallsInMessage.push(...toolUseBlocks);
        }
        
        // Map tool calls with status - initially pending/interrupted based on current state
        const toolCallsWithStatus: ToolCallWithStatus[] = toolCallsInMessage.map(toolCall => {
          const name = toolCall.function?.name || toolCall.name || toolCall.type || 'unknown';
          const args = (toolCall.function?.arguments || toolCall.args || toolCall.input || {}) as Record<string, unknown>;
          return {
            id: toolCall.id || `tool-${Math.random().toString(36).substr(2, 9)}`,
            name,
            args,
            status: isInterrupted ? 'pending' : 'pending' as const
          };
        });
        
        // Use stable ID from LangGraph message (Bug 3 fix)
        const stableId = message.id || `ai-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
        messageMap.set(stableId, { message, toolCalls: toolCallsWithStatus });
        
      } else if (message.type === 'tool') {
        // Find the corresponding AI message and update tool call status
        const toolMsg = message as { tool_call_id?: string };
        const toolCallId = toolMsg.tool_call_id;
        if (!toolCallId) return;
        
        for (const [, data] of messageMap.entries()) {
          const toolCallIndex = data.toolCalls.findIndex(tc => tc.id === toolCallId);
          if (toolCallIndex !== -1) {
            // Update status to completed and add result
            data.toolCalls[toolCallIndex] = {
              ...data.toolCalls[toolCallIndex],
              status: 'completed' as const,
              result: {
                tool_call_id: toolCallId,
                name: data.toolCalls[toolCallIndex].name,
                content: extractStringFromMessageContent(message)
              }
            };
            break;
          }
        }
        
      } else if (message.type === 'human') {
        // Use stable ID from LangGraph message
        const stableId = message.id || `human-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
        messageMap.set(stableId, { message, toolCalls: [] });
      }
    });
    
    // Convert map to array and add showAvatar flag
    const processedArray = Array.from(messageMap.entries()).map(([id, data]) => ({
      id,
      ...data
    }));
    
    return processedArray.map((data, index): ProcessedMessage => {
      const prevMessage = index > 0 ? processedArray[index - 1].message : null;
      return {
        id: data.id,
        type: data.message.type as 'human' | 'ai',
        content: extractStringFromMessageContent(data.message),
        toolCalls: data.toolCalls,
        showAvatar: data.message.type !== prevMessage?.type
      };
    });
  });

  // =============================================================================
  // STREAMING CONTENT DISPLAY (Bug 3 fix)
  // Determine if we should show streaming content separately or it's already in messages
  // =============================================================================
  
  const showStreamingBubble = $derived.by(() => {
    if (!isStreaming || !streamingContent) return false;
    
    // Check if the last AI message already has this content
    const lastMessage = processedMessages[processedMessages.length - 1];
    if (lastMessage?.type === 'ai' && lastMessage.content) {
      // Content is already being shown via processedMessages
      return false;
    }
    
    return true;
  });

  const showThinkingIndicator = $derived.by(() => {
    return isStreaming && !isInterrupted && processedMessages.length === 0 && !streamingContent;
  });

  // =============================================================================
  // EFFECTS
  // =============================================================================

  // Load LangGraph thread state when selecting a thread with langGraphThreadId
  // This restores chat history and any pending interrupts (like clarification questions)
  $effect(() => {
    const thread = currentThread;
    const langGraphThreadId = thread?.langGraphThreadId;
    const localThreadId = thread?.id;
    
    // Only load if:
    // 1. We have a thread with a langGraphThreadId
    // 2. We haven't already loaded this thread's state
    // 3. We're not currently streaming (don't interrupt active conversations)
    // 4. Backend is available
    if (
      langGraphThreadId &&
      localThreadId &&
      langGraphThreadId !== loadedLangGraphThreadId &&
      !isStreaming &&
      !isLoadingThreadState &&
      backendAvailable
    ) {
      console.log('[ChatPanel] Loading LangGraph state for thread:', langGraphThreadId);
      isLoadingThreadState = true;
      
      agentStore.loadThreadState(langGraphThreadId, localThreadId)
        .then((success) => {
          if (success) {
            loadedLangGraphThreadId = langGraphThreadId;
            console.log('[ChatPanel] Thread state loaded successfully');
          }
        })
        .finally(() => {
          isLoadingThreadState = false;
        });
    }
    
    // Reset loaded thread ID when switching to a different thread
    if (!langGraphThreadId && loadedLangGraphThreadId) {
      loadedLangGraphThreadId = null;
    }
  });

  // Debug logging for message count
  $effect(() => {
    console.log('[ChatPanel] Processed messages:', processedMessages.length, 'Streaming:', isStreaming, 'LG messages:', langGraphMessages.length);
  });

  // Auto-scroll to bottom when messages change
  $effect(() => {
    // Access dependencies to trigger effect
    const _msgs = processedMessages.length;
    const _streaming = streamingContent;
    const _lgMsgs = langGraphMessages.length;
    
    // Scroll after DOM update
    tick().then(() => {
      if (messagesContainer) {
        messagesContainer.scrollTop = messagesContainer.scrollHeight;
      }
    });
  });

  // =============================================================================
  // HANDLERS
  // =============================================================================

  async function handleSendMessage() {
    if (!messageInput.trim() || isStreaming || !isWalletReady) return;

    const message = messageInput.trim();
    messageInput = '';

    // If no local thread, create one first
    let localThreadId = threadStore.currentThreadId;
    if (!localThreadId && currentProjectId) {
      // Use first 10 chars of message as initial thread title
      const initialTitle = message.length > 10 ? message.slice(0, 10) + '...' : message;
      const thread = threadStore.createThread(currentProjectId, initialTitle);
      localThreadId = thread.id;
    }

    if (!localThreadId) return;

    // Get the LangGraph thread ID if it exists (from previous messages)
    const thread = threadStore.threads.find(t => t.id === localThreadId);
    const langGraphThreadId = thread?.langGraphThreadId ?? null;

    // Update thread title if it's the first message and title is generic
    if (currentThread?.title === 'Chat' || currentThread?.title === 'New Thread') {
      const titlePreview = message.length > 10 ? message.slice(0, 10) + '...' : message;
      threadStore.updateThread(localThreadId, { title: titlePreview });
    }

    try {
      const result = await agentStore.sendMessage(message, langGraphThreadId, localThreadId);
      
      // If a new LangGraph thread was created, store its ID
      if (!langGraphThreadId && result.langGraphThreadId) {
        threadStore.updateThread(localThreadId, { langGraphThreadId: result.langGraphThreadId });
      }
    } catch (error) {
      console.error('Failed to send message:', error);
    }
  }

  function handleKeydown(e: KeyboardEvent) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSendMessage();
    }
  }
</script>

<div class="flex h-full flex-col bg-zinc-900/30">
  <!-- Header with Agent Picker -->
  <div class="flex items-center justify-between border-b border-zinc-800 px-4 py-2">
    <div class="flex items-center gap-2">
      <MessageCircle class="h-4 w-4 text-blue-400" />
      <span class="text-sm font-medium text-zinc-300 truncate max-w-[200px]">
        {currentThread?.title ?? ''}
      </span>
    </div>
    <AgentPicker />
  </div>

  <!-- Messages -->
  <div
    bind:this={messagesContainer}
    class="flex-1 space-y-4 overflow-y-auto p-4"
  >
    {#if !currentThread}
      <div class="flex h-full items-center justify-center text-zinc-600">
        <div class="text-center">
          <Bot class="mx-auto h-12 w-12 mb-3 opacity-30" />
          <p class="text-sm">Select or create a thread to start chatting</p>
          <p class="text-xs text-zinc-700 mt-1">Use the sidebar on the left</p>
        </div>
      </div>
    {:else if isLoadingThreadState}
      <div class="flex h-full items-center justify-center text-zinc-600">
        <div class="text-center">
          <Loader2 class="mx-auto h-8 w-8 mb-3 animate-spin text-amber-500" />
          <p class="text-sm">Loading conversation...</p>
        </div>
      </div>
    {:else if processedMessages.length === 0 && !isStreaming}
      <div class="flex h-full items-center justify-center text-zinc-600">
        <div class="text-center">
          <Bot class="mx-auto h-12 w-12 mb-3 opacity-30" />
          <p class="text-sm">Send a message to start the conversation</p>
        </div>
      </div>
    {:else}
      <!-- Render processed messages with stable IDs -->
      {#each processedMessages as message (message.id)}
        {@const isUser = message.type === 'human'}
        <div class="flex {isUser ? 'justify-end' : 'justify-start'}">
          <div
            class="max-w-[85%] rounded-xl px-4 py-2 {isUser
              ? 'bg-amber-600 text-white'
              : 'bg-zinc-800 text-zinc-200'}"
          >
            {#if message.content}
              <p class="whitespace-pre-wrap text-sm">{message.content}</p>
            {:else if !isUser}
              <!-- AI message with no content yet (tool calls only) -->
              <p class="text-sm text-zinc-400 italic">Processing...</p>
            {/if}
          </div>
        </div>
        
        <!-- Show tool calls for AI messages (unified display - Bug 4 fix) -->
        {#if !isUser && message.toolCalls.length > 0}
          <div class="flex justify-start">
            <div class="max-w-[85%]">
              <ToolCallDisplay toolCalls={message.toolCalls} />
            </div>
          </div>
        {/if}
      {/each}

      <!-- Show streaming content bubble only when needed (Bug 3 fix) -->
      {#if showStreamingBubble}
        <div class="flex justify-start">
          <div class="max-w-[85%] rounded-xl bg-zinc-800 px-4 py-2 text-zinc-200">
            <p class="whitespace-pre-wrap text-sm">{streamingContent}</p>
            <span class="animate-pulse text-amber-500">▊</span>
          </div>
        </div>
      {/if}
      
      <!-- Show thinking indicator when no content yet -->
      {#if showThinkingIndicator}
        <div class="flex justify-start">
          <div class="max-w-[85%] rounded-xl bg-zinc-800 px-4 py-2 text-zinc-400">
            <span class="animate-pulse text-sm">Thinking...</span>
          </div>
        </div>
      {/if}
    {/if}
  </div>

  <!-- Human-in-the-Loop Interrupt Panel -->
  <HumanInterruptPanel />
  
  <!-- Clarification Panel (ask_user / ask_choices) -->
  <ClarificationPanel />

  <!-- Input -->
  <div class="border-t border-zinc-800 p-3">
    {#if backendAvailable === false}
      <div class="mb-2 flex items-center gap-2 rounded-lg bg-red-500/10 px-3 py-2 text-xs text-red-400">
        <AlertCircle class="h-3 w-3" />
        <span>LangGraph server unavailable. Start the server to enable AI chat.</span>
      </div>
    {/if}
    
    {#if !isWalletReady}
      <div class="mb-2 flex items-center gap-2 rounded-lg bg-amber-500/10 px-3 py-2 text-xs text-amber-400">
        <Loader2 class="h-3 w-3 animate-spin" />
        <span>Initializing wallet...</span>
      </div>
    {/if}
    
    <div class="flex gap-2">
      <Textarea
        placeholder={awaitingHumanResponse ? "Respond to the agent above..." : currentThread ? "Type your message..." : "Create a new thread to start chatting..."}
        bind:value={messageInput}
        onkeydown={handleKeydown}
        disabled={isStreaming || awaitingHumanResponse || !currentThread || !isWalletReady || backendAvailable === false}
        rows={2}
        class="flex-1 resize-none bg-zinc-800 border-zinc-700 text-zinc-100 placeholder-zinc-500"
      />
      <Button
        onclick={handleSendMessage}
        disabled={!messageInput.trim() || isStreaming || awaitingHumanResponse || !currentThread || !isWalletReady || backendAvailable === false}
        size="icon"
        class="self-end bg-amber-600 hover:bg-amber-500"
      >
        <Send class="h-4 w-4" />
      </Button>
    </div>
    {#if agentStore.error}
      <p class="mt-2 text-xs text-red-500">{agentStore.error}</p>
    {/if}
  </div>
</div>
