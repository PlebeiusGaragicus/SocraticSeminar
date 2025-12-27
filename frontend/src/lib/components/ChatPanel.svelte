<script lang="ts">
  import Send from '@lucide/svelte/icons/send';
  import MessageCircle from '@lucide/svelte/icons/message-circle';
  import Bot from '@lucide/svelte/icons/bot';
  import Loader2 from '@lucide/svelte/icons/loader-2';
  import { Button, Textarea } from './ui/index.js';
  import AgentPicker from './AgentPicker.svelte';
  import { threadStore, agentStore, projectStore } from '$lib/stores/index.js';
  import { cyphertap } from 'cyphertap';

  let messageInput = $state('');
  let messagesContainer: HTMLDivElement;

  const currentMessages = $derived(threadStore.currentMessages);
  const isStreaming = $derived(agentStore.isStreaming);
  const streamingContent = $derived(agentStore.streamingContent);
  const currentThread = $derived(threadStore.currentThread);
  const currentProjectId = $derived(projectStore.currentProjectId);
  
  // Wallet readiness (safe to use directly with SSR disabled)
  const isWalletReady = $derived(cyphertap.isReady);

  async function handleSendMessage() {
    if (!messageInput.trim() || isStreaming || !isWalletReady) return;

    const message = messageInput.trim();
    messageInput = '';

    // If no local thread, create one first
    let localThreadId = threadStore.currentThreadId;
    if (!localThreadId && currentProjectId) {
      const thread = threadStore.createThread(currentProjectId, 'Chat');
      localThreadId = thread.id;
    }

    if (!localThreadId) return;

    // Get the LangGraph thread ID if it exists (from previous messages)
    const thread = threadStore.threads.find(t => t.id === localThreadId);
    const langGraphThreadId = thread?.langGraphThreadId ?? null;

    // Update thread title if it's the first message and title is "New Chat"
    if (currentThread?.title === 'New Chat') {
      const titlePreview = message.length > 30 ? message.slice(0, 30) + '...' : message;
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

  // Auto-scroll to bottom when new messages arrive
  $effect(() => {
    if (messagesContainer && (currentMessages.length > 0 || streamingContent)) {
      messagesContainer.scrollTop = messagesContainer.scrollHeight;
    }
  });
</script>

<div class="flex h-full flex-col bg-zinc-900/30">
  <!-- Header with Agent Picker -->
  <div class="flex items-center justify-between border-b border-zinc-800 px-4 py-2">
    <div class="flex items-center gap-2">
      <MessageCircle class="h-4 w-4 text-blue-400" />
      <span class="text-sm font-medium text-zinc-300 truncate max-w-[200px]">
        {currentThread?.title ?? 'Select a thread'}
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
    {:else if currentMessages.length === 0 && !streamingContent}
      <div class="flex h-full items-center justify-center text-zinc-600">
        <div class="text-center">
          <Bot class="mx-auto h-12 w-12 mb-3 opacity-30" />
          <p class="text-sm">Send a message to start the conversation</p>
        </div>
      </div>
    {:else}
      {#each currentMessages as message}
        <div
          class="flex {message.role === 'user' ? 'justify-end' : 'justify-start'}"
        >
          <div
            class="max-w-[85%] rounded-xl px-4 py-2 {message.role === 'user'
              ? 'bg-amber-600 text-white'
              : 'bg-zinc-800 text-zinc-200'}"
          >
            <p class="whitespace-pre-wrap text-sm">{message.content}</p>
          </div>
        </div>
      {/each}

      <!-- Streaming response -->
      {#if isStreaming && streamingContent}
        <div class="flex justify-start">
          <div class="max-w-[85%] rounded-xl bg-zinc-800 px-4 py-2 text-zinc-200">
            <p class="whitespace-pre-wrap text-sm">{streamingContent}</p>
            <span class="animate-pulse text-amber-500">▊</span>
          </div>
        </div>
      {:else if isStreaming}
        <div class="flex justify-start">
          <div class="max-w-[85%] rounded-xl bg-zinc-800 px-4 py-2 text-zinc-400">
            <span class="animate-pulse text-sm">Thinking...</span>
          </div>
        </div>
      {/if}
    {/if}
  </div>

  <!-- Input -->
  <div class="border-t border-zinc-800 p-3">
    {#if !isWalletReady}
      <div class="mb-2 flex items-center gap-2 rounded-lg bg-amber-500/10 px-3 py-2 text-xs text-amber-400">
        <Loader2 class="h-3 w-3 animate-spin" />
        <span>Initializing wallet...</span>
      </div>
    {/if}
    
    <div class="flex gap-2">
      <Textarea
        placeholder={currentThread ? "Type your message..." : "Select a thread first..."}
        bind:value={messageInput}
        onkeydown={handleKeydown}
        disabled={isStreaming || !currentThread || !isWalletReady}
        rows={2}
        class="flex-1 resize-none bg-zinc-800 border-zinc-700 text-zinc-100 placeholder-zinc-500"
      />
      <Button
        onclick={handleSendMessage}
        disabled={!messageInput.trim() || isStreaming || !currentThread || !isWalletReady}
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
