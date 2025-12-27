<script lang="ts">
  import Send from '@lucide/svelte/icons/send';
  import PanelLeftClose from '@lucide/svelte/icons/panel-left-close';
  import PanelLeft from '@lucide/svelte/icons/panel-left';
  import Plus from '@lucide/svelte/icons/plus';
  import Trash2 from '@lucide/svelte/icons/trash-2';
  import MessageCircle from '@lucide/svelte/icons/message-circle';
  import Clock from '@lucide/svelte/icons/clock';
  import { Button, Textarea } from './ui/index.js';
  import PaymentGate from './PaymentGate.svelte';
  import { threadStore, agentStore, projectStore } from '$lib/stores/index.js';
  import type { PaymentRequest } from '$lib/stores/types.js';
  import type { Thread } from '$lib/stores/types.js';

  interface Props {
    collapsed: boolean;
    onToggleCollapse: () => void;
  }

  let { collapsed, onToggleCollapse }: Props = $props();

  let messageInput = $state('');
  let messagesContainer: HTMLDivElement;
  let currentPayment = $state<PaymentRequest | null>(null);
  let showThreadHistory = $state(false);

  const currentMessages = $derived(threadStore.currentMessages);
  const isStreaming = $derived(agentStore.isStreaming);
  const streamingContent = $derived(agentStore.streamingContent);
  const currentThread = $derived(threadStore.currentThread);
  const currentProjectId = $derived(projectStore.currentProjectId);
  
  const projectThreads = $derived(
    currentProjectId ? threadStore.getProjectThreads(currentProjectId) : []
  );

  function formatDate(timestamp: number): string {
    const date = new Date(timestamp);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffHours = diffMs / (1000 * 60 * 60);
    const diffDays = diffMs / (1000 * 60 * 60 * 24);

    if (diffHours < 1) {
      const mins = Math.floor(diffMs / (1000 * 60));
      return `${mins}m ago`;
    } else if (diffHours < 24) {
      return `${Math.floor(diffHours)}h ago`;
    } else if (diffDays < 7) {
      return `${Math.floor(diffDays)}d ago`;
    } else {
      return date.toLocaleDateString();
    }
  }

  async function handleSendMessage() {
    if (!messageInput.trim() || isStreaming) return;

    const message = messageInput.trim();
    messageInput = '';

    // If no thread, create one first
    let threadId = threadStore.currentThreadId;
    if (!threadId && currentProjectId) {
      const thread = threadStore.createThread(currentProjectId, 'Chat');
      threadId = thread.id;
    }

    if (!threadId) return;

    try {
      await agentStore.sendMessage(message, threadId, currentPayment ?? undefined);
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

  function handleNewThread() {
    if (!currentProjectId) return;
    threadStore.createThread(currentProjectId, 'New Chat');
    showThreadHistory = false;
  }

  function handleSelectThread(thread: Thread) {
    threadStore.selectThread(thread.id);
    showThreadHistory = false;
  }

  function handleDeleteThread(threadId: string, e: Event) {
    e.stopPropagation();
    threadStore.deleteThread(threadId);
  }

  // Auto-scroll to bottom when new messages arrive
  $effect(() => {
    if (messagesContainer && (currentMessages.length > 0 || streamingContent)) {
      messagesContainer.scrollTop = messagesContainer.scrollHeight;
    }
  });
</script>

<div class="flex h-full flex-col border-r border-zinc-800 bg-zinc-900/50">
  <!-- Header -->
  <div class="flex items-center justify-between border-b border-zinc-800 px-3 py-2">
    {#if !collapsed}
      <div class="flex items-center gap-2">
        <button
          onclick={() => (showThreadHistory = !showThreadHistory)}
          class="rounded p-1 text-zinc-500 transition-colors hover:bg-zinc-800 hover:text-zinc-300"
          title="Thread history"
        >
          <MessageCircle class="h-4 w-4" />
        </button>
        <span class="text-sm font-medium text-zinc-300 truncate max-w-[150px]">
          {currentThread?.title ?? 'New Chat'}
        </span>
      </div>
      <div class="flex items-center gap-1">
        <button
          onclick={handleNewThread}
          class="rounded p-1 text-zinc-500 transition-colors hover:bg-zinc-800 hover:text-zinc-300"
          title="New thread"
        >
          <Plus class="h-4 w-4" />
        </button>
        <button
          onclick={onToggleCollapse}
          class="rounded p-1 text-zinc-500 transition-colors hover:bg-zinc-800 hover:text-zinc-300"
          title="Collapse panel"
        >
          <PanelLeftClose class="h-4 w-4" />
        </button>
      </div>
    {:else}
      <button
        onclick={onToggleCollapse}
        class="mx-auto rounded p-1 text-zinc-500 transition-colors hover:bg-zinc-800 hover:text-zinc-300"
        title="Expand panel"
      >
        <PanelLeft class="h-4 w-4" />
      </button>
    {/if}
  </div>

  {#if !collapsed}
    <div class="relative flex flex-1 overflow-hidden">
      <!-- Thread History Sidebar -->
      {#if showThreadHistory}
        <div class="absolute inset-0 z-10 flex flex-col bg-zinc-900 border-r border-zinc-800">
          <div class="flex items-center justify-between border-b border-zinc-800 px-3 py-2">
            <span class="text-xs font-semibold uppercase tracking-wider text-zinc-500">
              Threads
            </span>
            <button
              onclick={() => (showThreadHistory = false)}
              class="rounded p-1 text-zinc-500 transition-colors hover:bg-zinc-800 hover:text-zinc-300"
            >
              <PanelLeftClose class="h-4 w-4" />
            </button>
          </div>
          
          <div class="flex-1 overflow-y-auto py-1">
            {#if projectThreads.length === 0}
              <div class="p-4 text-center text-sm text-zinc-600">
                No threads yet
              </div>
            {:else}
              {#each projectThreads as thread (thread.id)}
                <div class="group relative">
                  <button
                    onclick={() => handleSelectThread(thread)}
                    class="flex w-full items-center gap-2 px-3 py-2 text-left transition-colors hover:bg-zinc-800/50
                      {thread.id === threadStore.currentThreadId ? 'bg-zinc-800/70' : ''}"
                  >
                    <MessageCircle class="h-4 w-4 flex-shrink-0 text-zinc-500" />
                    <div class="flex-1 min-w-0">
                      <span class="block truncate text-sm text-zinc-300">
                        {thread.title}
                      </span>
                      <span class="flex items-center gap-1 text-xs text-zinc-600">
                        <Clock class="h-3 w-3" />
                        {formatDate(thread.updatedAt)}
                      </span>
                    </div>
                  </button>
                  <button
                    onclick={(e) => handleDeleteThread(thread.id, e)}
                    class="absolute right-2 top-1/2 -translate-y-1/2 rounded p-1 text-zinc-600 opacity-0 transition-all hover:bg-red-500/10 hover:text-red-500 group-hover:opacity-100"
                  >
                    <Trash2 class="h-3.5 w-3.5" />
                  </button>
                </div>
              {/each}
            {/if}
          </div>
          
          <div class="border-t border-zinc-800 p-2">
            <button
              onclick={handleNewThread}
              class="flex w-full items-center justify-center gap-2 rounded-lg bg-amber-600 px-3 py-2 text-sm font-medium text-white transition-colors hover:bg-amber-500"
            >
              <Plus class="h-4 w-4" />
              New Thread
            </button>
          </div>
        </div>
      {/if}

      <!-- Messages -->
      <div class="flex flex-1 flex-col">
        <div
          bind:this={messagesContainer}
          class="flex-1 space-y-4 overflow-y-auto p-4"
        >
          {#if !currentThread}
            <div class="flex h-full items-center justify-center text-zinc-600">
              <div class="text-center">
                <MessageCircle class="mx-auto h-8 w-8 mb-2 opacity-50" />
                <p class="text-sm">Start a new conversation</p>
              </div>
            </div>
          {:else if currentMessages.length === 0 && !streamingContent}
            <div class="flex h-full items-center justify-center text-zinc-600">
              <div class="text-center">
                <p class="text-sm">Send a message to start chatting...</p>
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
          <div class="mb-2">
            <PaymentGate
              onPaymentReady={(p) => (currentPayment = p)}
              disabled={isStreaming}
            />
          </div>

          <div class="flex gap-2">
            <Textarea
              placeholder="Type your message..."
              bind:value={messageInput}
              onkeydown={handleKeydown}
              disabled={isStreaming || !projectStore.currentProject}
              rows={2}
              class="flex-1 resize-none bg-zinc-800 border-zinc-700 text-zinc-100 placeholder-zinc-500"
            />
            <Button
              onclick={handleSendMessage}
              disabled={!messageInput.trim() || isStreaming || !projectStore.currentProject}
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
    </div>
  {/if}
</div>
