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
  import { Button, Textarea } from './ui/index.js';
  import AgentPicker from './AgentPicker.svelte';
  import ToolCallDisplay from './ToolCallDisplay.svelte';
  import { threadStore, agentStore, projectStore } from '$lib/stores/index.js';
  import { cyphertap } from 'cyphertap';
  import type { ToolCallWithStatus, ToolCall, ClarificationResponse, HITLActionRequest, HITLReviewConfig } from '$lib/stores/types.js';
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

  type InputMode = 'normal' | 'hitl' | 'clarification' | 'choices';

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
  const currentThread = $derived(threadStore.currentThread);
  const currentProjectId = $derived(projectStore.currentProjectId);
  const isWalletReady = $derived(cyphertap.isReady);
  const persistedMessages = $derived(threadStore.currentMessages);
  
  // Agent store derivations
  const isStreaming = $derived(agentStore.isStreaming);
  const isInterrupted = $derived(agentStore.isInterrupted);
  const streamingContent = $derived(agentStore.streamingContent);
  const awaitingHumanResponse = $derived(agentStore.awaitingHumanResponse);
  const langGraphMessages = $derived(agentStore.langGraphMessages);
  
  // Interrupt state
  const hitlInterrupt = $derived(agentStore.hitlInterrupt);
  const clientToolInterrupt = $derived(agentStore.clientToolInterrupt);
  const clarificationInterrupt = $derived(agentStore.clarificationInterrupt);

  // =============================================================================
  // INPUT MODE LOGIC - Unified input area adapts to current context
  // =============================================================================

  const inputMode = $derived.by((): InputMode => {
    if (!awaitingHumanResponse) return 'normal';
    
    if (clarificationInterrupt) {
      if (clarificationInterrupt.tool === 'ask_choices' && clarificationInterrupt.options?.length) {
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
        return clarificationInterrupt?.allow_freeform 
          ? 'Or type your own response...' 
          : 'Select an option above...';
      default:
        return currentThread ? 'Type your message...' : 'Create a new thread to start chatting...';
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
        return selectedChoices.length > 0 || (clarificationInterrupt?.allow_freeform && messageInput.trim().length > 0);
      default:
        return messageInput.trim().length > 0 && currentThread !== null;
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
    
    langGraphMessages.forEach((message: LangGraphMessage) => {
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
          toolCallsInMessage.push(...msgWithKwargs.additional_kwargs.tool_calls);
        } else if (msgWithKwargs.tool_calls && Array.isArray(msgWithKwargs.tool_calls)) {
          toolCallsInMessage.push(
            ...(msgWithKwargs.tool_calls as Array<{ name?: string }>).filter(tc => tc.name !== '')
          );
        } else if (Array.isArray(msgWithKwargs.content)) {
          const toolUseBlocks = (msgWithKwargs.content as Array<{ type?: string }>).filter(block => block.type === 'tool_use');
          toolCallsInMessage.push(...toolUseBlocks);
        }
        
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
        
        const stableId = message.id || `ai-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
        messageMap.set(stableId, { message, toolCalls: toolCallsWithStatus });
        
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
        const stableId = message.id || `human-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
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
    const lastMessage = processedMessages[processedMessages.length - 1];
    if (lastMessage?.type === 'ai' && lastMessage.content) return false;
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
      selectedChoices = [optionId];
    }
  }

  async function handleSendMessage() {
    if (!messageInput.trim() || isStreaming || !isWalletReady) return;

    const message = messageInput.trim();
    messageInput = '';

    let localThreadId = threadStore.currentThreadId;
    if (!localThreadId && currentProjectId) {
      // Use first 25 chars of message as initial thread title
      const initialTitle = message.length > 25 ? message.slice(0, 25) + '...' : message;
      const thread = threadStore.createThread(currentProjectId, initialTitle);
      localThreadId = thread.id;
    }

    if (!localThreadId) return;

    const thread = threadStore.threads.find(t => t.id === localThreadId);
    const langGraphThreadId = thread?.langGraphThreadId ?? null;

    // Update thread title if it's a generic title and this is effectively the first real message
    if (currentThread?.title === 'New Chat' || currentThread?.title === 'New Thread') {
      const titlePreview = message.length > 25 ? message.slice(0, 25) + '...' : message;
      threadStore.updateThread(localThreadId, { title: titlePreview });
    }

    try {
      const result = await agentStore.sendMessage(message, langGraphThreadId, localThreadId);
      if (!langGraphThreadId && result.langGraphThreadId) {
        threadStore.updateThread(localThreadId, { langGraphThreadId: result.langGraphThreadId });
      }
    } catch (error) {
      console.error('Failed to send message:', error);
    }
  }

  async function handleClarificationSubmit() {
    if (!clarificationInterrupt) return;
    isSubmitting = true;

    try {
      if (clarificationInterrupt.tool === 'ask_user') {
        const response: ClarificationResponse = { response: messageInput.trim() };
        await agentStore.resumeWithClarificationResponse(response);
      } else {
        const response: ClarificationResponse = {
          selected: selectedChoices.length > 0 ? selectedChoices : undefined,
          freeform: messageInput.trim() || undefined
        };
        await agentStore.resumeWithClarificationResponse(response);
      }
      messageInput = '';
      selectedChoices = [];
    } finally {
      isSubmitting = false;
    }
  }

  async function handleApprove() {
    isSubmitting = true;
    showDetailsModal = false;
    try {
      if (isClientTool) {
        await agentStore.executeApprovedWriteTools();
      } else {
        await agentStore.approveAllActions();
      }
      messageInput = '';
    } finally {
      isSubmitting = false;
    }
  }

  async function handleReject() {
    isSubmitting = true;
    showDetailsModal = false;
    try {
      if (isClientTool) {
        await agentStore.rejectClientToolInterrupt();
      } else {
        await agentStore.rejectAllActions();
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
              <p class="text-sm text-zinc-400 italic">Processing...</p>
            {/if}
          </div>
        </div>
        
        {#if !isUser && message.toolCalls.length > 0}
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
              <p class="whitespace-pre-wrap text-sm">{streamingContent}</p>
              <span class="animate-pulse text-amber-500">▊</span>
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
  <div class="border-t border-zinc-800">
    <!-- HITL Info Card with collapsible details -->
    {#if inputMode === 'hitl' && activeHitlInterrupt}
      <div class="mx-3 mt-3 rounded-lg border border-amber-500/30 bg-gradient-to-r from-amber-900/20 to-zinc-900/80 overflow-hidden">
        <div class="flex items-center justify-between border-b border-amber-500/20 bg-amber-900/30 px-3 py-2">
          <div class="flex items-center gap-2">
            <MessageCircle class="h-4 w-4 text-amber-400" />
            <span class="text-sm font-medium text-amber-200">Agent Needs Approval</span>
            <span class="text-xs text-amber-300/60">
              ({activeHitlInterrupt.action_requests.length} action{activeHitlInterrupt.action_requests.length !== 1 ? 's' : ''})
              </span>
            </div>
          <div class="flex items-center gap-1">
            <!-- Expand/Collapse button -->
            <button
              onclick={() => hitlDetailsExpanded = !hitlDetailsExpanded}
              class="p-1 rounded text-amber-300/70 hover:text-amber-200 hover:bg-amber-500/10"
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
              class="p-1 rounded text-amber-300/70 hover:text-amber-200 hover:bg-amber-500/10"
              title="View full details"
            >
              <Maximize2 class="h-4 w-4" />
            </button>
          </div>
        </div>
        
        <!-- Collapsed summary -->
        {#if !hitlDetailsExpanded}
          <div class="p-3">
            {#each activeHitlInterrupt.action_requests as action}
              {@const ActionIcon = getToolIcon(action.name)}
              <div class="flex items-center gap-2">
                <svelte:component this={ActionIcon} class="h-4 w-4 text-zinc-400 shrink-0" />
                <span class="text-sm font-medium text-zinc-200">{action.name}</span>
                <span class="text-xs text-zinc-400 truncate">{getActionDescription(action)}</span>
              </div>
            {/each}
          </div>
        {:else}
          <!-- Expanded details -->
          <div class="p-3 space-y-3 max-h-64 overflow-y-auto">
            {#each activeHitlInterrupt.action_requests as action}
              {@const ActionIcon = getToolIcon(action.name)}
              <div class="rounded bg-zinc-800/50 p-3">
                <div class="flex items-center gap-2 mb-2">
                  <svelte:component this={ActionIcon} class="h-4 w-4 text-zinc-400 shrink-0" />
                  <span class="text-sm font-medium text-zinc-200">{action.name}</span>
                </div>
                <p class="text-xs text-zinc-400 mb-2">{getActionDescription(action)}</p>
                {#if Object.keys(action.args || {}).length > 0}
                  <div class="text-xs space-y-1 border-t border-zinc-700/50 pt-2">
                    {#each Object.entries(action.args || {}) as [key, value]}
                      <div class="grid grid-cols-[80px_1fr] gap-2">
                        <span class="font-mono text-zinc-500">{key}:</span>
                        <span class="text-zinc-300 break-all">{formatArgValue(value)}</span>
                      </div>
                    {/each}
                  </div>
                {/if}
              </div>
            {/each}
        </div>
      {/if}
      </div>
    {/if}

    <!-- Clarification Info Card -->
    {#if (inputMode === 'clarification' || inputMode === 'choices') && clarificationInterrupt}
      <div class="mx-3 mt-3 rounded-lg border border-blue-500/30 bg-gradient-to-r from-blue-900/20 to-zinc-900/80 overflow-hidden">
        <div class="flex items-center gap-2 border-b border-blue-500/20 bg-blue-900/30 px-3 py-2">
          <HelpCircle class="h-4 w-4 text-blue-400" />
          <span class="text-sm font-medium text-blue-200">Agent Needs Clarification</span>
  </div>
        <div class="p-3">
          <p class="text-sm text-zinc-200 leading-relaxed">{clarificationInterrupt.question}</p>
          
          {#if inputMode === 'choices' && clarificationInterrupt.options}
            <div class="mt-3 flex flex-wrap gap-2">
              {#each clarificationInterrupt.options as option}
                <button
                  type="button"
                  onclick={() => toggleChoice(option.id)}
                  disabled={isSubmitting}
                  class="px-3 py-1.5 text-sm rounded-lg border transition-colors
                    {selectedChoices.includes(option.id)
                      ? 'border-blue-500 bg-blue-500/20 text-blue-200'
                      : 'border-zinc-600 bg-zinc-800/50 text-zinc-300 hover:border-zinc-500'}"
                >
                  {#if selectedChoices.includes(option.id)}
                    <Check class="h-3 w-3 inline mr-1" />
                  {/if}
                  {option.label}
                </button>
              {/each}
            </div>
          {/if}
        </div>
      </div>
    {/if}

    <!-- Main Input -->
    <div class="p-3">
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
          placeholder={inputPlaceholder}
        bind:value={messageInput}
        onkeydown={handleKeydown}
          disabled={isStreaming || !currentThread || !isWalletReady || backendAvailable === false}
        rows={2}
          class="flex-1 resize-none bg-zinc-800 border-zinc-700 text-zinc-100 placeholder-zinc-500
            {inputMode === 'hitl' ? 'border-amber-500/30' : ''}
            {inputMode === 'clarification' || inputMode === 'choices' ? 'border-blue-500/30' : ''}"
        />
        
        <!-- Action buttons based on mode -->
        <div class="flex flex-col gap-1 self-end">
          {#if inputMode === 'hitl'}
            <!-- HITL: Approve and Reject buttons -->
            <Button
              onclick={handleApprove}
              disabled={isSubmitting || isStreaming}
              size="icon"
              class="bg-emerald-600 hover:bg-emerald-500"
              title="Approve"
            >
              <Check class="h-4 w-4" />
            </Button>
            <Button
              onclick={handleReject}
              disabled={isSubmitting || isStreaming}
              size="icon"
              class="bg-red-600 hover:bg-red-500 text-white"
              title="Reject"
            >
              <X class="h-4 w-4" />
            </Button>
          {:else}
            <!-- Normal/Clarification: Send button -->
      <Button
              onclick={handleSubmit}
              disabled={!canSubmit || isSubmitting}
        size="icon"
              class="self-end {inputMode === 'clarification' || inputMode === 'choices' 
                ? 'bg-blue-600 hover:bg-blue-500' 
                : 'bg-amber-600 hover:bg-amber-500'}"
      >
        <Send class="h-4 w-4" />
      </Button>
          {/if}
        </div>
    </div>
      
    {#if agentStore.error}
      <p class="mt-2 text-xs text-red-500">{agentStore.error}</p>
    {/if}
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
              <svelte:component this={ActionIcon} class="h-5 w-5 text-amber-400 shrink-0" />
              <div>
                <p class="font-medium text-zinc-100">{action.name}</p>
                <p class="text-sm text-zinc-400">{getActionDescription(action)}</p>
              </div>
            </div>
            
            {#if Object.keys(action.args || {}).length > 0}
              <div class="p-4 space-y-3">
                {#each Object.entries(action.args || {}) as [key, value]}
                  <div>
                    <label class="block text-xs font-medium text-zinc-500 mb-1">{key}</label>
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
          <label class="block text-sm font-medium text-zinc-300 mb-2">Feedback (optional)</label>
          <textarea
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
