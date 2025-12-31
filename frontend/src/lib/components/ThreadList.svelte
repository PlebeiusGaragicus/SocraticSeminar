<script lang="ts">
  import { format, isYesterday, isToday, isThisWeek } from "date-fns";
  import Trash2 from '@lucide/svelte/icons/trash-2';
  import { workspaceStore } from '$lib/stores/index.js';
  import type { Thread, ThreadStatus } from '$lib/stores/types.js';
  import { cn } from '$lib/utils.js';

  interface Props {
    threads: Thread[];
    onThreadSelect: (threadId: string) => void;
    onThreadDelete: (threadId: string, immediate?: boolean) => void;
  }

  let { threads, onThreadSelect, onThreadDelete }: Props = $props();

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

  const groupedThreads = $derived.by(() => {
    const groups: Record<keyof typeof GROUP_LABELS, Thread[]> = {
      today: [],
      yesterday: [],
      week: [],
      older: [],
    };

    threads.forEach((thread) => {
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
</script>

<div class="flex h-full flex-col">
  <!-- Scrollable List -->
  <div class="flex-1 overflow-y-auto py-2">
    {#if threads.length === 0}
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
                  {@const isOpen = workspaceStore.leftTabs.some(t => t.id === thread.id) || workspaceStore.rightTabs.some(t => t.id === thread.id)}
                  <div class="group relative px-2">
                      <button
                        onclick={() => onThreadSelect(thread.id)}
                        class={cn(
                          "flex w-full flex-col gap-1 rounded-lg p-2 text-left transition-all duration-200",
                          isOpen
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
                      onThreadDelete(thread.id, e.shiftKey);
                    }}
                    class="absolute right-4 top-1/2 -translate-y-1/2 rounded bg-zinc-900/80 p-1.5 text-zinc-500 opacity-0 backdrop-blur-sm transition-all hover:text-red-500 group-hover:opacity-100"
                    title="Delete thread (Shift + click to skip confirmation)"
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
