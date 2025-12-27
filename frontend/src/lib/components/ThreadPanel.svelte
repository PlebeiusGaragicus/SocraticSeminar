<script lang="ts">
  import { Send } from '@lucide/svelte';
  import { Button, Textarea } from './ui';
  import PaymentGate from './PaymentGate.svelte';
  import { threadStore, agentStore, projectStore, type PaymentRequest } from '$lib/stores';

  let messageInput = $state('');
  let messagesContainer: HTMLDivElement;
  let currentPayment = $state<PaymentRequest | null>(null);

  const currentMessages = $derived(threadStore.currentMessages);
  const isStreaming = $derived(agentStore.isStreaming);
  const streamingContent = $derived(agentStore.streamingContent);
  const currentThread = $derived(threadStore.currentThread);

  async function handleSendMessage() {
    if (!messageInput.trim() || isStreaming) return;

    const message = messageInput.trim();
    messageInput = '';

    // If no thread, create one first
    let threadId = threadStore.currentThreadId;
    if (!threadId && projectStore.currentProjectId) {
      const thread = threadStore.createThread(projectStore.currentProjectId, 'Chat');
      threadId = thread.id;
    }

    if (!threadId) return;

    try {
      // Send message to agent with optional payment
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

  // Auto-scroll to bottom when new messages arrive
  $effect(() => {
    if (messagesContainer && (currentMessages.length > 0 || streamingContent)) {
      messagesContainer.scrollTop = messagesContainer.scrollHeight;
    }
  });
</script>

<div class="flex h-full flex-col">
  <!-- Header -->
  <div class="flex items-center justify-between border-b border-border p-4">
    <h3 class="font-semibold">
      {currentThread?.title ?? 'Select or create a thread'}
    </h3>
  </div>

  <!-- Messages -->
  <div 
    bind:this={messagesContainer}
    class="flex-1 overflow-y-auto p-4 space-y-4"
  >
    {#if !currentThread}
      <div class="flex h-full items-center justify-center text-muted-foreground">
        <p>Select a thread or create a new one to start chatting</p>
      </div>
    {:else if currentMessages.length === 0 && !streamingContent}
      <div class="flex h-full items-center justify-center text-muted-foreground">
        <p>Start a conversation...</p>
      </div>
    {:else}
      {#each currentMessages as message}
        <div class="flex {message.role === 'user' ? 'justify-end' : 'justify-start'}">
          <div 
            class="max-w-[80%] rounded-lg p-3 
              {message.role === 'user' 
                ? 'bg-primary text-primary-foreground' 
                : 'bg-muted text-muted-foreground'}"
          >
            <p class="whitespace-pre-wrap">{message.content}</p>
          </div>
        </div>
      {/each}

      <!-- Streaming response -->
      {#if isStreaming && streamingContent}
        <div class="flex justify-start">
          <div class="max-w-[80%] rounded-lg bg-muted p-3 text-muted-foreground">
            <p class="whitespace-pre-wrap">{streamingContent}</p>
            <span class="animate-pulse">▊</span>
          </div>
        </div>
      {:else if isStreaming}
        <div class="flex justify-start">
          <div class="max-w-[80%] rounded-lg bg-muted p-3 text-muted-foreground">
            <span class="animate-pulse">Thinking...</span>
          </div>
        </div>
      {/if}
    {/if}
  </div>

  <!-- Input -->
  <div class="border-t border-border p-4">
    <!-- Payment toggle -->
    <div class="mb-2">
      <PaymentGate 
        onPaymentReady={(p) => currentPayment = p} 
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
        class="flex-1 resize-none"
      />
      <Button 
        onclick={handleSendMessage} 
        disabled={!messageInput.trim() || isStreaming || !projectStore.currentProject}
        size="icon"
        class="self-end"
      >
        <Send class="h-4 w-4" />
      </Button>
    </div>
    {#if agentStore.error}
      <p class="mt-2 text-sm text-destructive">{agentStore.error}</p>
    {/if}
  </div>
</div>

