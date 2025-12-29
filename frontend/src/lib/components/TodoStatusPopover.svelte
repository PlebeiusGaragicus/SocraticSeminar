<script lang="ts">
  import ListTodo from '@lucide/svelte/icons/list-todo';
  import CircleDot from '@lucide/svelte/icons/circle-dot';
  import CheckCircle2 from '@lucide/svelte/icons/check-circle-2';
  import Circle from '@lucide/svelte/icons/circle';
  import XCircle from '@lucide/svelte/icons/x-circle';
  import ChevronDown from '@lucide/svelte/icons/chevron-down';
  import { agentStore } from '$lib/stores/index.js';

  // Local state
  let isOpen = $state(false);

  // Derived state
  const todos = $derived(agentStore.todos);
  const hasTodos = $derived(todos.length > 0);
  
  const stats = $derived({
    total: todos.length,
    pending: todos.filter(t => t.status === 'pending').length,
    inProgress: todos.filter(t => t.status === 'in_progress').length,
    completed: todos.filter(t => t.status === 'completed').length,
    cancelled: todos.filter(t => t.status === 'cancelled').length,
  });

  const activeTasks = $derived(stats.pending + stats.inProgress);
  const progress = $derived(
    stats.total > 0 
      ? Math.round((stats.completed / stats.total) * 100) 
      : 0
  );

  function toggleOpen() {
    isOpen = !isOpen;
  }

  function handleClickOutside(event: MouseEvent) {
    const target = event.target as HTMLElement;
    if (!target.closest('.todo-popover')) {
      isOpen = false;
    }
  }

  function getStatusIcon(status: string) {
    switch (status) {
      case 'pending': return Circle;
      case 'in_progress': return CircleDot;
      case 'completed': return CheckCircle2;
      case 'cancelled': return XCircle;
      default: return Circle;
    }
  }

  function getStatusColor(status: string): string {
    switch (status) {
      case 'pending': return 'text-zinc-400';
      case 'in_progress': return 'text-amber-400';
      case 'completed': return 'text-emerald-400';
      case 'cancelled': return 'text-red-400';
      default: return 'text-zinc-400';
    }
  }

  $effect(() => {
    if (isOpen) {
      document.addEventListener('click', handleClickOutside);
      return () => document.removeEventListener('click', handleClickOutside);
    }
  });
</script>

{#if hasTodos}
  <div class="relative todo-popover">
    <!-- Trigger Button -->
    <button
      type="button"
      onclick={toggleOpen}
      class="flex items-center gap-2 px-2.5 py-1.5 rounded-lg text-xs font-medium 
        transition-all hover:bg-zinc-800/70
        {activeTasks > 0 ? 'bg-amber-500/10 text-amber-400 border border-amber-500/30' : 'bg-zinc-800/50 text-zinc-400 border border-zinc-700/50'}"
    >
      <ListTodo class="h-3.5 w-3.5" />
      <span>{stats.completed}/{stats.total}</span>
      {#if activeTasks > 0}
        <span class="flex h-4 w-4 items-center justify-center rounded-full bg-amber-500/20 text-[10px]">
          {activeTasks}
        </span>
      {/if}
      <ChevronDown class="h-3 w-3 ml-0.5 {isOpen ? 'rotate-180' : ''} transition-transform" />
    </button>

    <!-- Popover -->
    {#if isOpen}
      <div 
        class="absolute right-0 top-full mt-2 w-72 rounded-xl border border-zinc-700 bg-zinc-900 shadow-xl z-50 overflow-hidden"
      >
        <!-- Header with Progress -->
        <div class="border-b border-zinc-800 bg-zinc-800/50 px-4 py-3">
          <div class="flex items-center justify-between mb-2">
            <span class="text-sm font-medium text-zinc-200">Agent Tasks</span>
            <span class="text-xs text-zinc-400">{progress}% complete</span>
          </div>
          <!-- Progress Bar -->
          <div class="h-1.5 w-full bg-zinc-700 rounded-full overflow-hidden">
            <div 
              class="h-full bg-gradient-to-r from-amber-500 to-emerald-500 transition-all duration-300"
              style="width: {progress}%"
            ></div>
          </div>
        </div>

        <!-- Todo List -->
        <div class="max-h-64 overflow-y-auto p-2">
          {#each todos as todo, index (todo.id ?? `todo-${index}`)}
            {@const StatusIcon = getStatusIcon(todo.status)}
            <div class="flex items-start gap-2 px-2 py-2 rounded-lg hover:bg-zinc-800/50 transition-colors">
              <svelte:component 
                this={StatusIcon} 
                class="h-4 w-4 mt-0.5 flex-shrink-0 {getStatusColor(todo.status)}" 
              />
              <span class="text-xs text-zinc-300 leading-relaxed {todo.status === 'completed' || todo.status === 'cancelled' ? 'line-through opacity-60' : ''}">
                {todo.content}
              </span>
            </div>
          {/each}
        </div>

        <!-- Stats Footer -->
        <div class="border-t border-zinc-800 bg-zinc-800/30 px-4 py-2 flex items-center justify-between text-[10px] text-zinc-500">
          <div class="flex items-center gap-3">
            {#if stats.inProgress > 0}
              <span class="flex items-center gap-1">
                <CircleDot class="h-3 w-3 text-amber-400" />
                {stats.inProgress} active
              </span>
            {/if}
            {#if stats.pending > 0}
              <span class="flex items-center gap-1">
                <Circle class="h-3 w-3 text-zinc-400" />
                {stats.pending} pending
              </span>
            {/if}
          </div>
          {#if stats.completed > 0}
            <span class="flex items-center gap-1 text-emerald-400">
              <CheckCircle2 class="h-3 w-3" />
              {stats.completed} done
            </span>
          {/if}
        </div>
      </div>
    {/if}
  </div>
{/if}

