<script lang="ts">
  import ChevronDown from '@lucide/svelte/icons/chevron-down';
  import Bot from '@lucide/svelte/icons/bot';
  import Loader2 from '@lucide/svelte/icons/loader-2';
  import RefreshCw from '@lucide/svelte/icons/refresh-cw';
  import AlertCircle from '@lucide/svelte/icons/alert-circle';
  import { assistantStore, threadStore } from '$lib/stores/index.js';
  import { onMount } from 'svelte';

  interface Props {
    threadId?: string | null;
  }

  let { threadId = null }: Props = $props();

  let isOpen = $state(false);
  let dropdownRef: HTMLDivElement;

  const currentThread = $derived(
    threadId ? threadStore.threads.find(t => t.id === threadId) : null
  );

  const selectedAssistantId = $derived(
    currentThread?.assistantId || assistantStore.selectedAssistantId
  );

  const assistants = $derived(assistantStore.assistants);
  const selectedAssistant = $derived(
    assistants.find(a => a.assistant_id === selectedAssistantId) || assistantStore.selectedAssistant
  );
  const isLoading = $derived(assistantStore.isLoading);
  const hasError = $derived(!!assistantStore.error);

  function getAssistantName(assistant: any): string {
    if (!assistant) {
      return isLoading ? 'Loading...' : 'Select Agent';
    }
    const metadata = assistant.metadata as Record<string, unknown> | undefined;
    return (metadata?.name as string) || assistant.name || assistant.assistant_id.slice(0, 8);
  }

  function getAssistantDescription(assistant: any): string {
    if (!assistant) return '';
    const metadata = assistant.metadata as Record<string, unknown> | undefined;
    return (metadata?.description as string) || '';
  }

  function handleSelect(id: string) {
    if (threadId) {
      threadStore.updateThread(threadId, { assistantId: id });
    } else {
      assistantStore.selectAssistant(id);
    }
    isOpen = false;
  }

  function handleClickOutside(event: MouseEvent) {
    if (isOpen && dropdownRef && !dropdownRef.contains(event.target as Node)) {
      isOpen = false;
    }
  }

  onMount(() => {
    assistantStore.fetchAssistants();
    document.addEventListener('click', handleClickOutside);
    return () => {
      document.removeEventListener('click', handleClickOutside);
    };
  });
</script>

<div bind:this={dropdownRef} class="relative" role="presentation">
  <button
    onclick={() => isOpen = !isOpen}
    disabled={isLoading}
    class="flex items-center gap-2 rounded-lg border border-zinc-700 bg-zinc-800 px-3 py-1.5 text-sm text-zinc-200 transition-colors hover:bg-zinc-700 hover:border-zinc-600 disabled:opacity-50"
  >
    {#if isLoading}
      <Loader2 class="h-4 w-4 animate-spin text-zinc-400" />
    {:else if hasError}
      <AlertCircle class="h-4 w-4 text-red-500" />
    {:else}
      <Bot class="h-4 w-4 text-amber-500" />
    {/if}
    <span class="max-w-[120px] truncate">
      {getAssistantName(selectedAssistant)}
    </span>
    <ChevronDown
      class="h-4 w-4 text-zinc-500 transition-transform {isOpen ? 'rotate-180' : ''}"
    />
  </button>

  {#if isOpen}
    <div class="absolute left-0 top-full z-50 mt-1 min-w-[220px] rounded-lg border border-zinc-700 bg-zinc-800 py-1 shadow-xl">
      <!-- Header -->
      <div class="flex items-center justify-between border-b border-zinc-700 px-3 py-2">
        <span class="text-xs font-semibold uppercase tracking-wider text-zinc-500">
          Agents
        </span>
        <!-- <button
          onclick={() => assistantStore.fetchAssistants()}
          disabled={isLoading}
          class="rounded p-1 text-zinc-500 transition-colors hover:bg-zinc-700 hover:text-zinc-300 disabled:opacity-50"
          title="Refresh agents"
        >
          <RefreshCw class="h-3.5 w-3.5 {isLoading ? 'animate-spin' : ''}" />
        </button> -->
      </div>

      <!-- Agent list -->
      <div class="max-h-[300px] overflow-y-auto py-1">
        {#if isLoading}
          <div class="flex items-center justify-center px-3 py-4">
            <Loader2 class="h-5 w-5 animate-spin text-zinc-500" />
          </div>
        {:else if hasError}
          <div class="px-3 py-3">
            <div class="flex items-center gap-2 text-red-400 mb-2">
              <AlertCircle class="h-4 w-4" />
              <span class="text-sm font-medium">Connection Error</span>
            </div>
            <p class="text-xs text-zinc-500 mb-3">
              Unable to connect to agent server.
            </p>
            <button
              onclick={() => assistantStore.fetchAssistants()}
              class="w-full rounded bg-zinc-700 px-3 py-1.5 text-xs text-zinc-300 hover:bg-zinc-600 transition-colors"
            >
              Try Again
            </button>
          </div>
        {:else if assistants.length === 0}
          <div class="px-3 py-4 text-center text-sm text-zinc-500">
            No agents found on server
          </div>
        {:else}
          {#each assistants as assistant (assistant.assistant_id)}
            {@const isSelected = assistant.assistant_id === selectedAssistantId}
            <button
              onclick={() => handleSelect(assistant.assistant_id)}
              class="flex w-full items-start gap-3 px-3 py-2 text-left transition-colors hover:bg-zinc-700/50
                {isSelected ? 'bg-amber-500/10' : ''}"
            >
              <div class="mt-0.5 flex h-6 w-6 flex-shrink-0 items-center justify-center rounded-md 
                {isSelected ? 'bg-amber-500/20 text-amber-500' : 'bg-zinc-700 text-zinc-400'}">
                <Bot class="h-4 w-4" />
              </div>
              <div class="flex-1 min-w-0">
                <div class="flex items-center gap-2">
                  <span class="font-medium text-zinc-200 truncate">
                    {getAssistantName(assistant)}
                  </span>
                  {#if isSelected}
                    <span class="rounded bg-amber-500/20 px-1.5 py-0.5 text-xs text-amber-400">
                      Active
                    </span>
                  {/if}
                </div>
                {#if getAssistantDescription(assistant)}
                  <p class="mt-0.5 text-xs text-zinc-500 line-clamp-2">
                    {getAssistantDescription(assistant)}
                  </p>
                {/if}
              </div>
            </button>
          {/each}
        {/if}
      </div>
    </div>
  {/if}
</div>
