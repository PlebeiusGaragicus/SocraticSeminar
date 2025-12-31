<script lang="ts">
  import Send from '@lucide/svelte/icons/send';
  import MessageCircle from '@lucide/svelte/icons/message-circle';
  import Bot from '@lucide/svelte/icons/bot';
  import Loader2 from '@lucide/svelte/icons/loader-2';
  import AlertCircle from '@lucide/svelte/icons/alert-circle';
  import Check from '@lucide/svelte/icons/check';
  import X from '@lucide/svelte/icons/x';
  import HelpCircle from '@lucide/svelte/icons/help-circle';
  import Wrench from '@lucide/svelte/icons/wrench';
  import FileText from '@lucide/svelte/icons/file-text';
  import FolderOpen from '@lucide/svelte/icons/folder-open';
  import Search from '@lucide/svelte/icons/search';
  import Edit from '@lucide/svelte/icons/edit';
  import FilePlus from '@lucide/svelte/icons/file-plus';
  import ChevronDown from '@lucide/svelte/icons/chevron-down';
  import ChevronUp from '@lucide/svelte/icons/chevron-up';
  import Maximize2 from '@lucide/svelte/icons/maximize-2';
  import Square from '@lucide/svelte/icons/square';
  import ArrowUp from '@lucide/svelte/icons/arrow-up';
  import { Button, Textarea } from './ui/index.js';
  import AgentPicker from './AgentPicker.svelte';
  import ToolCallDisplay from './ToolCallDisplay.svelte';
  import TodoStatusPopover from './TodoStatusPopover.svelte';
  import Markdown from './Markdown.svelte';
  import { threadStore, agentStore, projectStore } from '$lib/stores/index.js';
  import { cyphertap } from 'cyphertap';
  import type { ToolCallWithStatus, ToolCall, ClarificationResponse, HITLActionRequest, HITLReviewConfig } from '$lib/stores/types.js';
  import { tick, onMount } from 'svelte';
  import { checkHealth, type Message as LangGraphMessage } from '$lib/services/langgraph.js';
  import { extractStringFromMessageContent, cn } from '$lib/utils.js';

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

  type InputMode = 'normal' | 'hitl' | 'clarification' | 'choices';

  interface Props {
    threadId?: string | null;
  }

  let { threadId = null }: Props = $props();

  // =============================================================================
  // LOCAL STATE
  // =============================================================================

  let messageInput = $state('');
  let messagesContainer: HTMLDivElement | undefined = $state();
  let backendAvailable = $state<boolean | null>(null);
  let isSubmitting = $state(false);
  let selectedChoices = $state<string[]>([]);
  
  // HITL details UI state
  let hitlDetailsExpanded = $state(false);
  let showDetailsModal = $state(false);

  // Track if we've loaded state for the current thread
  let loadedLangGraphThreadId = $state<string | null>(null);
  let isLoadingThreadState = $state(false);

  // =============================================================================
  // LIFECYCLE
  // =============================================================================

  onMount(() => {
    checkHealth().then(available => {
      backendAvailable = available;
    });
    threadStore.loadFromStorage();
  });

  // =============================================================================
  // REACTIVE DERIVATIONS
  // =============================================================================

  // Core store derivations
  const effectiveThreadId = $derived(threadId ?? threadStore.currentThreadId);
  const currentThread = $derived(
    effectiveThreadId ? threadStore.threads.find(t => t.id === effectiveThreadId) : null
  );
  const currentProjectId = $derived(projectStore.currentProjectId);
  const isWalletReady = $derived(cyphertap.isReady);
  const persistedMessages = $derived(
    effectiveThreadId ? threadStore.getMessages(effectiveThreadId) : []
  );
  
  // Agent store derivations - now thread-specific for side-by-side support
  const runState = $derived(effectiveThreadId ? agentStore.getRunState(effectiveThreadId) : null);
  const isStreaming = $derived(runState?.isStreaming || false);
  const isInterrupted = $derived(runState?.isInterrupted || false);
  const streamingContent = $derived(runState?.streamingContent || '');
  const awaitingHumanResponse = $derived(runState?.awaitingHumanResponse || false);
  const langGraphMessages = $derived(runState?.langGraphMessages || []);
  
  // Interrupt state
  const hitlInterrupt = $derived(runState?.hitlInterrupt || null);
  const clientToolInterrupt = $derived(runState?.clientToolInterrupt || null);
  const clarificationInterrupt = $derived(runState?.clarificationInterrupt || null);

  // =============================================================================
  // INPUT MODE LOGIC - Unified input area adapts to current context
  // =============================================================================

    // Unified input mode logic
    const inputMode = $derived.by((): InputMode => {
      if (!awaitingHumanResponse) return 'normal';
      
      if (clarificationInterrupt) {
        if (clarificationInterrupt.tool === 'ask_choices' && Array.isArray(clarificationInterrupt.options) && clarificationInterrupt.options.length > 0) {
          return 'choices';
        }
        return 'clarification';
      }
      
      if (hitlInterrupt || clientToolInterrupt) {
        return 'hitl';
      }
      
      return 'normal';
    });

  // Unified interrupt for HITL display
  const activeHitlInterrupt = $derived.by(() => {
    if (clientToolInterrupt) {
      return {
        action_requests: clientToolInterrupt.action_requests || clientToolInterrupt.tool_calls.map(tc => ({
          name: tc.name,
          args: tc.args,
          description: `Execute ${tc.name}`
        })),
        review_configs: clientToolInterrupt.review_configs || [{
          action_name: clientToolInterrupt.tool_calls[0]?.name || '',
          allowed_decisions: ['approve', 'reject'] as const
        }]
      };
    }
    return hitlInterrupt;
  });

  const isClientTool = $derived(!!clientToolInterrupt);

  // Placeholder text based on mode
  const inputPlaceholder = $derived.by(() => {
    switch (inputMode) {
      case 'hitl':
        return 'Optional: Provide feedback or edits for the agent...';
      case 'clarification':
        return 'Type your response...';
      case 'choices':
        return 'Select an option above or type your own response...';
      default:
        return 'What do you want to know?';
    }
  });

  // Can submit based on mode
  const canSubmit = $derived.by(() => {
    if (isStreaming || !isWalletReady || backendAvailable === false) return false;
    
    switch (inputMode) {
      case 'hitl':
        return true;
      case 'clarification':
        return messageInput.trim().length > 0;
      case 'choices':
        return selectedChoices.length > 0 || messageInput.trim().length > 0;
      default:
        return messageInput.trim().length > 0 && (currentThread !== null || currentProjectId !== null);
    }
  });

  // =============================================================================
  // PROCESSED MESSAGES
  // =============================================================================

  const processedMessages = $derived.by((): ProcessedMessage[] => {
    const useServerMessages = (isStreaming || awaitingHumanResponse || isInterrupted) && langGraphMessages.length > 0;
    
    if (!useServerMessages) {
      return persistedMessages.map((msg, index) => {
        const prevMsg = index > 0 ? persistedMessages[index - 1] : null;
        return {
          id: msg.id,
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

    const messageMap = new Map<string, { message: LangGraphMessage; toolCalls: ToolCallWithStatus[] }>();
    
    langGraphMessages.forEach((message: LangGraphMessage, index: number) => {
      if (message.type === 'ai') {
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
          toolCallsInMessage.push(...(msgWithKwargs.additional_kwargs.tool_calls as any[]));
        } else if (msgWithKwargs.tool_calls && Array.isArray(msgWithKwargs.tool_calls)) {
          toolCallsInMessage.push(
            ...(msgWithKwargs.tool_calls as Array<{ name?: string }>).filter(tc => tc.name !== '')
          );
        } else if (Array.isArray(msgWithKwargs.content)) {
          const toolUseBlocks = (msgWithKwargs.content as Array<{ type?: string }>).filter(block => block.type === 'tool_use');
          toolCallsInMessage.push(...toolUseBlocks);
        }
        
        const toolCallsWithStatus: ToolCallWithStatus[] = toolCallsInMessage
          .map(toolCall => {
            const name = toolCall.function?.name || toolCall.name || toolCall.type || 'unknown';
            const args = (toolCall.function?.arguments || toolCall.args || toolCall.input || {}) as Record<string, unknown>;
            return {
              id: toolCall.id || `tool-${index}-${name}`,
              name,
              args,
              status: 'pending' as const
            };
          });
        
        // Only include AI messages if they have content OR tool calls
        // This prevents empty intermediate messages from appearing as "Processing..."
        const messageContent = extractStringFromMessageContent(message);
        const hasContent = messageContent && messageContent.trim() !== '';
        const hasToolCalls = toolCallsWithStatus.length > 0;
        
        if (hasContent || hasToolCalls) {
          // Use server ID if available, otherwise a stable ID based on index
          const stableId = message.id || `ai-${index}`;
          messageMap.set(stableId, { message, toolCalls: toolCallsWithStatus });
        }
        
      } else if (message.type === 'tool') {
        const toolMsg = message as { tool_call_id?: string };
        const toolCallId = toolMsg.tool_call_id;
        if (!toolCallId) return;
        
        for (const [, data] of messageMap.entries()) {
          const toolCallIndex = data.toolCalls.findIndex(tc => tc.id === toolCallId);
          if (toolCallIndex !== -1) {
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
        const stableId = message.id || `human-${index}`;
        messageMap.set(stableId, { message, toolCalls: [] });
      }
    });
    
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

  const showStreamingBubble = $derived.by(() => {
    if (!isStreaming || !streamingContent) return false;
    
    // Find the latest human message index
    const lastHumanIdx = processedMessages.findLastIndex(m => m.type === 'human');
    
    // Find if there is an AI message AFTER the latest human message
    const lastAiAfterHuman = processedMessages.findLast((m, i) => m.type === 'ai' && i > lastHumanIdx);
    
    // If we have an AI message already synced into the history list after your latest prompt,
    // check if it's already showing the same content we're streaming.
    if (lastAiAfterHuman) {
      const historyContent = lastAiAfterHuman.content || '';
      // If the synced history content is already nearly as long as the streaming content,
      // it means the 'values' event has caught up, so we hide the separate bubble.
      if (historyContent.length > 0 && streamingContent.startsWith(historyContent.slice(0, 20))) {
        return false;
      }
    }
    
    return true;
  });

  const showThinkingIndicator = $derived.by(() => {
    return isStreaming && !isInterrupted && processedMessages.length === 0 && !streamingContent;
  });

  // =============================================================================
  // EFFECTS
  // =============================================================================

  // Reset input state when interrupt changes
  $effect(() => {
    if (clarificationInterrupt || hitlInterrupt || clientToolInterrupt) {
      selectedChoices = [];
      hitlDetailsExpanded = false;
    }
  });

  // Load LangGraph thread state when selecting a thread
  $effect(() => {
    const thread = currentThread;
    const langGraphThreadId = thread?.langGraphThreadId;
    const localThreadId = thread?.id;
    
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
    
    if (!langGraphThreadId && loadedLangGraphThreadId) {
      loadedLangGraphThreadId = null;
    }
  });

  // Auto-scroll
  $effect(() => {
    const _msgs = processedMessages.length;
    const _streaming = streamingContent;
    const _lgMsgs = langGraphMessages.length;
    
    tick().then(() => {
      if (messagesContainer) {
        messagesContainer.scrollTop = messagesContainer.scrollHeight;
      }
    });
  });

  // =============================================================================
  // HANDLERS
  // =============================================================================

  function getToolIcon(name: string) {
    switch (name) {
      case 'list_files': return FolderOpen;
      case 'get_file': return FileText;
      case 'search_files': return Search;
      case 'edit_file': return Edit;
      case 'create_file': return FilePlus;
      case 'write_file': return FilePlus;
      default: return Wrench;
    }
  }

  function getActionDescription(action: HITLActionRequest): string {
    const args = action.args || {};
    switch (action.name) {
      case 'list_files': return 'List all files in your project';
      case 'get_file': return `Read file: "${args.file_id || 'unknown'}"`;
      case 'search_files': return `Search files for: "${args.query || 'unknown'}"`;
      case 'edit_file': return `Edit file: "${args.file_id || 'unknown'}"`;
      case 'create_file': return `Create new file: "${args.title || 'unknown'}"`;
      case 'write_file': return `Create file "${args.title || 'unknown'}"`;
      default: return action.description || `Execute: ${action.name}`;
    }
  }

  function formatArgValue(value: unknown): string {
    if (typeof value === 'string') {
      // Truncate long strings for display
      return value.length > 100 ? value.slice(0, 100) + '...' : value;
    }
    return JSON.stringify(value, null, 2);
  }

  function toggleChoice(optionId: string) {
    if (!clarificationInterrupt) return;
    
    if (clarificationInterrupt.allow_multiple) {
      if (selectedChoices.includes(optionId)) {
        selectedChoices = selectedChoices.filter(id => id !== optionId);
      } else {
        selectedChoices = [...selectedChoices, optionId];
      }
    } else {
      if (selectedChoices.includes(optionId)) {
        selectedChoices = [];
      } else {
        selectedChoices = [optionId];
      }
    }
  }

  async function handleSendMessage() {
    if (!messageInput.trim() || isStreaming || !isWalletReady) return;

    const message = messageInput.trim();
    messageInput = '';

    let targetThreadId = effectiveThreadId;
    if (!targetThreadId && currentProjectId) {
      // Use first 25 chars of message as initial thread title
      const initialTitle = message.length > 25 ? message.slice(0, 25) + '...' : message;
      const thread = threadStore.createThread(currentProjectId, initialTitle);
      targetThreadId = thread.id;
    }

    if (!targetThreadId) return;

    const thread = threadStore.threads.find(t => t.id === targetThreadId);
    const langGraphThreadId = thread?.langGraphThreadId ?? null;

    // Update thread title if it's a generic title and this is effectively the first real message
    if (thread?.title === 'New Chat' || thread?.title === 'New Thread') {
      const titlePreview = message.length > 25 ? message.slice(0, 25) + '...' : message;
      threadStore.updateThread(targetThreadId, { title: titlePreview });
    }

    try {
      const result = await agentStore.sendMessage(message, langGraphThreadId, targetThreadId);
      if (!langGraphThreadId && result.langGraphThreadId) {
        threadStore.updateThread(targetThreadId, { langGraphThreadId: result.langGraphThreadId });
      }
    } catch (error) {
      console.error('Failed to send message:', error);
    }
  }

  async function handleClarificationSubmit() {
    if (!clarificationInterrupt || !effectiveThreadId) return;
    isSubmitting = true;

    try {
      if (clarificationInterrupt.tool === 'ask_user') {
        const response: ClarificationResponse = { response: messageInput.trim() };
        await agentStore.resumeWithClarificationResponse(response, effectiveThreadId);
      } else {
        const response: ClarificationResponse = {
          selected: selectedChoices.length > 0 ? selectedChoices : undefined,
          freeform: messageInput.trim() || undefined
        };
        await agentStore.resumeWithClarificationResponse(response, effectiveThreadId);
      }
      messageInput = '';
      selectedChoices = [];
    } finally {
      isSubmitting = false;
    }
  }

  async function handleApprove() {
    if (!effectiveThreadId) return;
    isSubmitting = true;
    showDetailsModal = false;
    try {
      if (isClientTool) {
        await agentStore.executeApprovedWriteTools(effectiveThreadId);
      } else {
        await agentStore.approveAllActions(effectiveThreadId);
      }
      messageInput = '';
    } finally {
      isSubmitting = false;
    }
  }

  async function handleReject() {
    if (!effectiveThreadId) return;
    isSubmitting = true;
    showDetailsModal = false;
    try {
      if (isClientTool) {
        await agentStore.rejectClientToolInterrupt(effectiveThreadId);
      } else {
        await agentStore.rejectAllActions(effectiveThreadId);
      }
      messageInput = '';
    } finally {
      isSubmitting = false;
    }
  }

  function handleKeydown(e: KeyboardEvent) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  }

  function handleSubmit() {
    switch (inputMode) {
      case 'clarification':
      case 'choices':
        handleClarificationSubmit();
        break;
      case 'hitl':
        handleApprove();
        break;
      default:
        handleSendMessage();
    }
  }
  function handleContainerClick() {
    if (effectiveThreadId && threadStore.currentThreadId !== effectiveThreadId) {
      threadStore.selectThread(effectiveThreadId);
    }
  }
</script>

<div 
  class="flex h-full flex-col bg-zinc-900/30"
  onclick={handleContainerClick}
  onkeydown={handleContainerClick}
  role="presentation"
>
  <!-- Header with Agent Picker and Todo Status -->
  <div class="flex items-center justify-between border-b border-zinc-800 px-4 py-2">
    <AgentPicker threadId={effectiveThreadId} />
    <TodoStatusPopover />
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
          <p class="text-sm">Send a message to start a new thread</p>
          <p class="text-xs text-zinc-700 mt-1">Or select an existing one from the sidebar</p>
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
      {#each processedMessages as message (message.id)}
        {@const isUser = message.type === 'human'}
        {@const hasContent = message.content && message.content.trim() !== ''}
        {@const hasToolCalls = !isUser && message.toolCalls.length > 0}
        
        <!-- Only render message bubble if there's content -->
        {#if hasContent}
          <div class="flex {isUser ? 'justify-end' : 'justify-start'}">
            <div
              class="max-w-[85%] rounded-xl px-4 py-2 {isUser
                ? 'bg-amber-600 text-white'
                : 'bg-zinc-800 text-zinc-200'}"
            >
              {#if isUser}
                <p class="whitespace-pre-wrap text-sm">{message.content}</p>
              {:else}
                <Markdown content={message.content} />
              {/if}
            </div>
          </div>
        {/if}
        
        <!-- Tool calls render separately - no "Processing..." fallback needed -->
        {#if hasToolCalls}
          <div class="flex justify-start">
            <div class="max-w-[85%]">
              <ToolCallDisplay toolCalls={message.toolCalls} />
            </div>
          </div>
        {/if}
      {/each}

      {#if showStreamingBubble}
          <div class="flex justify-start">
            <div class="max-w-[85%] rounded-xl bg-zinc-800 px-4 py-2 text-zinc-200">
              <Markdown content={streamingContent} />
            </div>
          </div>
        {/if}
      
      {#if showThinkingIndicator}
        <div class="flex justify-start">
          <div class="max-w-[85%] rounded-xl bg-zinc-800 px-4 py-2 text-zinc-400">
            <span class="animate-pulse text-sm">Thinking...</span>
          </div>
        </div>
      {/if}
    {/if}
  </div>

  <!-- Unified Input Area -->
  <div class="flex-shrink-0 bg-background pt-2">
    <div class="relative mx-auto w-[calc(100%-32px)] max-w-[1024px] mb-6 group">
      <!-- Rainbow perimeter effect -->
      <div class="absolute -inset-[1px] rounded-xl opacity-100 blur-[35px] pointer-events-none overflow-hidden">
        <div class="absolute top-1/2 left-1/2 w-[200%] h-[1000%] bg-[conic-gradient(from_0deg,#ff0000,#ffff00,#00ff00,#00ffff,#0000ff,#ff00ff,#ff0000)] animate-rainbow-spin"></div>
      </div>

      <!-- Pulsing yellow glow border -->
      <div class="absolute -inset-[1px] rounded-xl border border-amber-400/50 pointer-events-none z-0 animate-border-pulse shadow-[0_0_15px_rgba(251,191,36,0.2)]"></div>

      <div
        class="flex flex-shrink-0 flex-col overflow-hidden rounded-xl border border-border bg-background transition-colors duration-200 ease-in-out relative z-10"
      >
      <!-- HITL Info Card with collapsible details -->
      {#if inputMode === 'hitl' && activeHitlInterrupt}
        <div class="flex flex-col border-b border-border bg-amber-500/5 overflow-hidden">
          <div class="flex items-center justify-between bg-amber-500/10 px-[18px] py-2">
            <div class="flex items-center gap-2">
              <MessageCircle class="h-4 w-4 text-amber-600 dark:text-amber-400" />
              <span class="text-sm font-semibold text-amber-900 dark:text-amber-200">Agent Needs Approval</span>
              <span class="text-xs text-amber-700/60 dark:text-amber-300/60">
                ({activeHitlInterrupt.action_requests.length} action{activeHitlInterrupt.action_requests.length !== 1 ? 's' : ''})
              </span>
            </div>
            <div class="flex items-center gap-1">
              <!-- Expand/Collapse button -->
              <button
                onclick={() => hitlDetailsExpanded = !hitlDetailsExpanded}
                class="p-1 rounded text-amber-700/70 hover:text-amber-900 hover:bg-amber-500/10 dark:text-amber-300/70 dark:hover:text-amber-200"
                title={hitlDetailsExpanded ? 'Collapse details' : 'Expand details'}
              >
                {#if hitlDetailsExpanded}
                  <ChevronUp class="h-4 w-4" />
                {:else}
                  <ChevronDown class="h-4 w-4" />
                {/if}
              </button>
              <!-- Modal button -->
              <button
                onclick={() => showDetailsModal = true}
                class="p-1 rounded text-amber-700/70 hover:text-amber-900 hover:bg-amber-500/10 dark:text-amber-300/70 dark:hover:text-amber-200"
                title="View full details"
              >
                <Maximize2 class="h-4 w-4" />
              </button>
            </div>
          </div>
          
          <div class="px-[18px] py-3 max-h-48 overflow-y-auto">
            {#if !hitlDetailsExpanded}
              {#each activeHitlInterrupt.action_requests as action}
                {@const ActionIcon = getToolIcon(action.name)}
                <div class="flex items-center gap-2 py-0.5">
                  <ActionIcon class="h-3.5 w-3.5 text-zinc-500 shrink-0" />
                  <span class="text-sm font-medium text-foreground/80">{action.name}</span>
                  <span class="text-xs text-muted-foreground truncate">{getActionDescription(action)}</span>
                </div>
              {/each}
            {:else}
              <div class="space-y-3">
                {#each activeHitlInterrupt.action_requests as action}
                  {@const ActionIcon = getToolIcon(action.name)}
                  <div class="rounded-lg bg-background/50 border border-border/50 p-3">
                    <div class="flex items-center gap-2 mb-2">
                      <ActionIcon class="h-4 w-4 text-zinc-500 shrink-0" />
                      <span class="text-sm font-semibold">{action.name}</span>
                    </div>
                    <p class="text-xs text-muted-foreground mb-2">{getActionDescription(action)}</p>
                    {#if Object.keys(action.args || {}).length > 0}
                      <div class="text-[10px] space-y-1 border-t border-border pt-2">
                        {#each Object.entries(action.args || {}) as [key, value]}
                          <div class="grid grid-cols-[80px_1fr] gap-2">
                            <span class="font-mono text-muted-foreground uppercase tracking-wider">{key}:</span>
                            <span class="text-foreground/80 break-all font-mono">{formatArgValue(value)}</span>
                          </div>
                        {/each}
                      </div>
                    {/if}
                  </div>
                {/each}
              </div>
            {/if}
          </div>
        </div>
      {/if}

      <!-- Clarification Info Card -->
      {#if (inputMode === 'clarification' || inputMode === 'choices') && clarificationInterrupt}
        <div class="flex flex-col border-b border-border bg-blue-500/5 overflow-hidden">
          <div class="flex items-center gap-2 bg-blue-500/10 px-[18px] py-2">
            <HelpCircle class="h-4 w-4 text-blue-600 dark:text-blue-400" />
            <span class="text-sm font-semibold text-blue-900 dark:text-blue-200">Agent Needs Clarification</span>
          </div>
          <div class="px-[18px] py-3">
            <p class="text-sm text-foreground/90 leading-relaxed mb-3">{clarificationInterrupt.question}</p>
            
            {#if inputMode === 'choices' && Array.isArray(clarificationInterrupt.options)}
              <div class="flex flex-wrap gap-2">
                {#each clarificationInterrupt.options as option}
                  <button
                    type="button"
                    onclick={() => toggleChoice(option.id)}
                    disabled={isSubmitting}
                    class="px-3 py-1.5 text-xs rounded-full border transition-colors
                      {selectedChoices.includes(option.id)
                        ? 'border-blue-500 bg-blue-500/20 text-blue-700 dark:text-blue-200'
                        : 'border-border bg-background hover:border-blue-400 text-muted-foreground'}"
                  >
                    {#if selectedChoices.includes(option.id)}
                      <Check class="h-3 w-3 inline mr-1" />
                    {/if}
                    {option.label || option.id || 'Option'}
                  </button>
                {/each}
              </div>
            {/if}
          </div>
        </div>
      {/if}

      <!-- Main Input -->
      <form onsubmit={(e) => { e.preventDefault(); handleSubmit(); }} class="flex flex-col">
        {#if backendAvailable === false || !isWalletReady || agentStore.error}
          <div class="px-[18px] pt-3 flex flex-col gap-2">
            {#if backendAvailable === false}
              <div class="flex items-center gap-2 rounded-lg bg-red-500/10 px-3 py-1.5 text-xs text-red-600 dark:text-red-400">
                <AlertCircle class="h-3 w-3" />
                <span>LangGraph server unavailable. Start the server to enable AI chat.</span>
              </div>
            {/if}
            
            {#if !isWalletReady}
              <div class="flex items-center gap-2 rounded-lg bg-amber-500/10 px-3 py-1.5 text-xs text-amber-600 dark:text-amber-400">
                <Loader2 class="h-3 w-3 animate-spin" />
                <span>Initializing wallet...</span>
              </div>
            {/if}

            {#if agentStore.error}
              <p class="text-[10px] text-destructive font-medium uppercase tracking-wider px-1">{agentStore.error}</p>
            {/if}
          </div>
        {/if}

        <div class="flex items-end gap-2 p-2 px-3">
          <textarea
            bind:value={messageInput}
            onkeydown={handleKeydown}
            onfocus={handleContainerClick}
            placeholder={inputPlaceholder}
            disabled={isStreaming || (!currentThread && !currentProjectId) || !isWalletReady || backendAvailable === false}
            class="font-inherit [field-sizing:content] flex-1 resize-none border-0 bg-transparent px-3 py-2 text-sm leading-5 text-foreground outline-none placeholder:text-muted-foreground/60 min-h-[36px] max-h-[200px] overflow-y-auto"
            rows={1}
          ></textarea>
          
          <div class="flex shrink-0 gap-2 pb-0.5">
            {#if inputMode === 'hitl'}
              <Button
                onclick={handleReject}
                disabled={isSubmitting || isStreaming}
                variant="ghost"
                size="sm"
                class="text-destructive hover:text-destructive hover:bg-destructive/10"
              >
                <X class="h-4 w-4" />
              </Button>
              <Button
                onclick={handleApprove}
                disabled={isSubmitting || isStreaming}
                size="sm"
                class="bg-emerald-600 hover:bg-emerald-500 text-white"
              >
                <Check class="h-4 w-4" />
              </Button>
            {:else if isStreaming}
              <Button
                onclick={() => agentStore.stopStreaming(effectiveThreadId)}
                disabled={!effectiveThreadId}
                variant="destructive"
                size="sm"
                class="px-3"
              >
                <Square class="h-4 w-4 mr-2 fill-current" />
                <span>Stop</span>
              </Button>
            {:else}
              <Button
                type="submit"
                disabled={!canSubmit || isSubmitting}
                size="sm"
                class={cn(
                  'px-3',
                  inputMode === 'clarification' || inputMode === 'choices' 
                    ? 'bg-blue-600 hover:bg-blue-500 text-white' 
                    : 'bg-foreground text-background hover:opacity-90'
                )}
              >
                <ArrowUp class="h-4 w-4 mr-2" />
                <span>Send</span>
              </Button>
            {/if}
          </div>
        </div>
      </form>
    </div>
  </div>
</div>
</div>

<!-- HITL Details Modal -->
{#if showDetailsModal && activeHitlInterrupt}
  <div class="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm">
    <div class="w-full max-w-2xl mx-4 max-h-[80vh] flex flex-col rounded-xl border border-amber-500/30 bg-zinc-900 shadow-2xl overflow-hidden">
      <!-- Modal Header -->
      <div class="flex items-center justify-between border-b border-amber-500/20 bg-amber-900/30 px-4 py-3">
        <div class="flex items-center gap-2">
          <MessageCircle class="h-5 w-5 text-amber-400" />
          <span class="font-semibold text-amber-200">Action Details</span>
        </div>
        <button
          onclick={() => showDetailsModal = false}
          class="p-1 rounded text-zinc-400 hover:text-zinc-200 hover:bg-zinc-700"
        >
          <X class="h-5 w-5" />
        </button>
      </div>
      
      <!-- Modal Content -->
      <div class="flex-1 overflow-y-auto p-4 space-y-4">
        {#each activeHitlInterrupt.action_requests as action}
          {@const ActionIcon = getToolIcon(action.name)}
          <div class="rounded-lg border border-zinc-700 bg-zinc-800/50 overflow-hidden">
            <div class="flex items-center gap-3 border-b border-zinc-700 bg-zinc-800 px-4 py-3">
              <ActionIcon class="h-5 w-5 text-amber-400 shrink-0" />
              <div>
                <p class="font-medium text-zinc-100">{action.name}</p>
                <p class="text-sm text-zinc-400">{getActionDescription(action)}</p>
              </div>
            </div>
            
            {#if Object.keys(action.args || {}).length > 0}
              <div class="p-4 space-y-3">
                {#each Object.entries(action.args || {}) as [key, value]}
                  <div>
                    <span class="block text-xs font-medium text-zinc-500 mb-1">{key}</span>
                    <div class="rounded bg-zinc-900 p-2 text-sm text-zinc-200 max-h-48 overflow-y-auto">
                      <pre class="whitespace-pre-wrap break-all font-mono text-xs">{typeof value === 'string' ? value : JSON.stringify(value, null, 2)}</pre>
                    </div>
                  </div>
                {/each}
              </div>
            {/if}
          </div>
        {/each}
        
        <!-- Edit feedback input -->
        <div>
          <label for="hitl-feedback" class="block text-sm font-medium text-zinc-300 mb-2">Feedback (optional)</label>
          <textarea
            id="hitl-feedback"
            bind:value={messageInput}
            placeholder="Provide feedback or suggest edits..."
            rows="3"
            class="w-full rounded-lg border border-zinc-600 bg-zinc-800 px-3 py-2 text-sm text-zinc-200 placeholder:text-zinc-500 focus:border-amber-500 focus:outline-none focus:ring-1 focus:ring-amber-500 resize-none"
          ></textarea>
        </div>
</div>
      
      <!-- Modal Footer -->
      <div class="flex items-center justify-between border-t border-zinc-700 bg-zinc-800/50 px-4 py-3">
        <Button
          onclick={handleReject}
          disabled={isSubmitting}
          variant="ghost"
          class="text-red-400 hover:text-red-300 hover:bg-red-500/10 border border-red-500/30"
        >
          <X class="h-4 w-4 mr-2" />
          Reject
        </Button>
        <Button
          onclick={handleApprove}
          disabled={isSubmitting}
          class="bg-emerald-600 hover:bg-emerald-500"
        >
          <Check class="h-4 w-4 mr-2" />
          Approve
        </Button>
      </div>
    </div>
  </div>
{/if}

<style>
  @keyframes rainbow-spin {
    from {
      transform: translate(-50%, -50%) rotate(0deg);
    }
    to {
      transform: translate(-50%, -50%) rotate(360deg);
    }
  }

  :global(.animate-rainbow-spin) {
    animation: rainbow-spin 8s linear infinite;
  }

  @keyframes border-pulse {
    0%, 100% {
      opacity: 0.3;
      box-shadow: 0 0 5px rgba(251, 191, 36, 0.1);
      border-color: rgba(251, 191, 36, 0.3);
    }
    50% {
      opacity: 1;
      box-shadow: 0 0 20px rgba(251, 191, 36, 0.4);
      border-color: rgba(251, 191, 36, 0.8);
    }
  }

  :global(.animate-border-pulse) {
    animation: border-pulse 4s ease-in-out infinite;
  }
</style>
