<script lang="ts">
  import { format, differenceInDays, isYesterday, isToday, isThisWeek } from "date-fns";
  import MessageCircle from '@lucide/svelte/icons/message-circle';
  import Trash2 from '@lucide/svelte/icons/trash-2';
  import ChevronDown from '@lucide/svelte/icons/chevron-down';
  import { threadStore, agentStore } from '$lib/stores/index.js';
  import type { Thread, ThreadStatus } from '$lib/stores/types.js';
  import { cn } from '$lib/utils.js';

  interface Props {
    threads: Thread[];
    currentThreadId: string | null;
    onThreadSelect: (threadId: string) => void;
    onThreadDelete: (threadId: string) => void;
  }

  let { threads, currentThreadId, onThreadSelect, onThreadDelete }: Props = $props();

  type StatusFilter = "all" | ThreadStatus;
  let statusFilter = $state<StatusFilter>("all");
  let isFilterOpen = $state(false);

  const STATUS_COLORS: Record<ThreadStatus, string> = {
    idle: "bg-green-500",
    busy: "bg-blue-500",
    interrupted: "bg-orange-500",
    error: "bg-red-600",
  };

  const GROUP_LABELS = {
    today: "Today",
    yesterday: "Yesterday",
    week: "This Week",
    older: "Older",
  } as const;

  function formatTime(timestamp: number): string {
    const date = new Date(timestamp);
    if (isToday(date)) return format(date, "HH:mm");
    if (isYesterday(date)) return "Yesterday";
    if (isThisWeek(date)) return format(date, "EEEE");
    return format(date, "MM/dd");
  }

  const filteredThreads = $derived(
    statusFilter === "all" 
      ? threads 
      : threads.filter(t => t.status === statusFilter)
  );

  const interruptedCount = $derived(
    threads.filter(t => t.status === 'interrupted').length
  );

  const groupedThreads = $derived.by(() => {
    const now = new Date();
    const groups: Record<keyof typeof GROUP_LABELS, Thread[]> = {
      interrupted: [],
      today: [],
      yesterday: [],
      week: [],
      older: [],
    };

    filteredThreads.forEach((thread) => {
      const date = new Date(thread.updatedAt);
      if (isToday(date)) {
        groups.today.push(thread);
      } else if (isYesterday(date)) {
        groups.yesterday.push(thread);
      } else if (isThisWeek(date)) {
        groups.week.push(thread);
      } else {
        groups.older.push(thread);
      }
    });

    return groups;
  });

  function handleStatusChange(status: StatusFilter) {
    statusFilter = status;
    isFilterOpen = false;
  }
</script>

<div class="flex h-full flex-col">
  <!-- Filter Header -->
  <div class="flex items-center justify-between border-b border-zinc-800 px-3 py-2">
    <div class="relative">
      <button
        onclick={() => isFilterOpen = !isFilterOpen}
        class="flex items-center gap-1.5 rounded px-2 py-1 text-xs font-medium text-zinc-400 transition-colors hover:bg-zinc-800 hover:text-zinc-200"
      >
        <span>{statusFilter === 'all' ? 'All Statuses' : statusFilter.charAt(0).toUpperCase() + statusFilter.slice(1)}</span>
        <ChevronDown class="h-3 w-3" />
      </button>

      {#if isFilterOpen}
        <div class="absolute left-0 top-full z-50 mt-1 w-40 rounded-lg border border-zinc-800 bg-zinc-900 p-1 shadow-xl">
          <button
            onclick={() => handleStatusChange('all')}
            class="flex w-full items-center gap-2 rounded px-2 py-1.5 text-left text-xs text-zinc-300 hover:bg-zinc-800"
          >
            All Statuses
          </button>
          <div class="my-1 border-t border-zinc-800"></div>
          {#each ['idle', 'busy', 'interrupted', 'error'] as status}
            <button
              onclick={() => handleStatusChange(status as ThreadStatus)}
              class="flex w-full items-center gap-2 rounded px-2 py-1.5 text-left text-xs text-zinc-300 hover:bg-zinc-800"
            >
              <span class={cn("size-1.5 rounded-full", STATUS_COLORS[status as ThreadStatus])}></span>
              <span class="capitalize">{status}</span>
              {#if status === 'interrupted' && interruptedCount > 0}
                <span class="ml-auto flex size-4 items-center justify-center rounded-full bg-red-600 text-[10px] font-bold text-white">
                  {interruptedCount}
                </span>
              {/if}
            </button>
          {/each}
        </div>
      {/if}
    </div>
  </div>

  <!-- Scrollable List -->
  <div class="flex-1 overflow-y-auto py-2">
    {#if filteredThreads.length === 0}
      <div class="px-3 py-8 text-center text-xs text-zinc-600">
        No threads found
      </div>
    {:else}
      {#each Object.entries(GROUP_LABELS) as [key, label]}
        {@const groupThreads = groupedThreads[key as keyof typeof GROUP_LABELS]}
        {#if groupThreads.length > 0}
          <div class="mb-4">
            <h4 class="px-3 py-1 text-[10px] font-bold uppercase tracking-wider text-zinc-500">
              {label}
            </h4>
            <div class="space-y-0.5">
              {#each groupThreads as thread (thread.id)}
                <div class="group relative px-2">
                      <button
                        onclick={() => onThreadSelect(thread.id)}
                        class={cn(
                          "flex w-full flex-col gap-1 rounded-lg p-2 text-left transition-all duration-200",
                          thread.id === currentThreadId
                            ? "bg-zinc-800/80 ring-1 ring-zinc-700"
                            : "hover:bg-zinc-800/40"
                        )}
                      >
                        <div class="flex items-center justify-between gap-2">
                          <div class="flex items-center gap-2 min-w-0">
                            <span class={cn("size-2 flex-shrink-0 rounded-full", STATUS_COLORS[thread.status])}></span>
                            <h3 class="truncate text-sm font-medium text-zinc-200">
                              {thread.title}
                            </h3>
                            {#if thread.status === 'interrupted'}
                              <span class="flex-shrink-0 rounded-full bg-orange-500/10 px-1.5 py-0.5 text-[9px] font-bold uppercase tracking-wider text-orange-500 ring-1 ring-inset ring-orange-500/20">
                                Action
                              </span>
                            {/if}
                          </div>
                          <span class="flex-shrink-0 text-[10px] text-zinc-500">
                            {formatTime(thread.updatedAt)}
                          </span>
                        </div>

                    {#if thread.description}
                      <p class="line-clamp-1 text-xs text-zinc-500 pl-4">
                        {thread.description}
                      </p>
                    {/if}
                  </button>

                  <button
                    onclick={(e) => {
                      e.stopPropagation();
                      onThreadDelete(thread.id);
                    }}
                    class="absolute right-4 top-1/2 -translate-y-1/2 rounded bg-zinc-900/80 p-1.5 text-zinc-500 opacity-0 backdrop-blur-sm transition-all hover:text-red-500 group-hover:opacity-100"
                    title="Delete thread"
                  >
                    <Trash2 class="h-3.5 w-3.5" />
                  </button>
                </div>
              {/each}
            </div>
          </div>
        {/if}
      {/each}
    {/if}
  </div>
</div>

{#if isFilterOpen}
  <div 
    class="fixed inset-0 z-40" 
    onclick={() => isFilterOpen = false}
    onkeydown={(e) => e.key === 'Escape' && (isFilterOpen = false)}
    role="button"
    tabindex="-1"
    aria-label="Close filter menu"
  ></div>
{/if}

