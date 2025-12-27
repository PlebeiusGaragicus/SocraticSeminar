<script lang="ts">
  /**
   * ToolCallDisplay Component
   * 
   * Displays tool calls and their results in the chat.
   * Adapted from fullstack-chat-client's tool-calls.tsx
   * 
   * Features:
   * - Shows tool name and arguments
   * - Expandable result display
   * - Status indicators (pending, executing, completed, error)
   */
  import ChevronDown from '@lucide/svelte/icons/chevron-down';
  import ChevronUp from '@lucide/svelte/icons/chevron-up';
  import Loader2 from '@lucide/svelte/icons/loader-2';
  import Check from '@lucide/svelte/icons/check';
  import X from '@lucide/svelte/icons/x';
  import Wrench from '@lucide/svelte/icons/wrench';
  import type { ToolCallWithStatus } from '$lib/stores/types.js';

  interface Props {
    toolCalls: ToolCallWithStatus[];
  }

  let { toolCalls }: Props = $props();
  
  // Track expanded state for each tool call
  let expandedIds = $state<Set<string>>(new Set());

  function toggleExpand(id: string) {
    const newSet = new Set(expandedIds);
    if (newSet.has(id)) {
      newSet.delete(id);
    } else {
      newSet.add(id);
    }
    expandedIds = newSet;
  }

  function formatValue(value: unknown): string {
    if (typeof value === 'string' || typeof value === 'number' || typeof value === 'boolean') {
      return String(value);
    }
    try {
      return JSON.stringify(value, null, 2);
    } catch {
      return String(value);
    }
  }

  function isComplexValue(value: unknown): boolean {
    return Array.isArray(value) || (typeof value === 'object' && value !== null);
  }

  function getStatusIcon(status: ToolCallWithStatus['status']) {
    switch (status) {
      case 'pending':
        return { icon: Loader2, class: 'text-zinc-400', animate: false };
      case 'executing':
        return { icon: Loader2, class: 'text-amber-400', animate: true };
      case 'completed':
        return { icon: Check, class: 'text-green-400', animate: false };
      case 'error':
        return { icon: X, class: 'text-red-400', animate: false };
    }
  }

  function truncateContent(content: string, maxLength: number = 200): { text: string; truncated: boolean } {
    if (content.length <= maxLength) {
      return { text: content, truncated: false };
    }
    return { text: content.slice(0, maxLength) + '...', truncated: true };
  }
</script>

<div class="flex flex-col gap-2">
  {#each toolCalls as toolCall (toolCall.id)}
    {@const status = getStatusIcon(toolCall.status)}
    {@const isExpanded = expandedIds.has(toolCall.id)}
    {@const hasArgs = Object.keys(toolCall.args || {}).length > 0}
    {@const hasResult = toolCall.result?.content}
    
    <div class="overflow-hidden rounded-lg border border-zinc-700 bg-zinc-800/50">
      <!-- Header -->
      <div class="flex items-center justify-between border-b border-zinc-700 bg-zinc-800 px-3 py-2">
        <div class="flex items-center gap-2">
          <Wrench class="h-4 w-4 text-zinc-400" />
          <span class="font-medium text-zinc-200">{toolCall.name}</span>
          {#if toolCall.id}
            <code class="rounded bg-zinc-700 px-1.5 py-0.5 text-xs text-zinc-400">
              {toolCall.id.slice(0, 8)}
            </code>
          {/if}
        </div>
        <div class="flex items-center gap-2">
          <svelte:component 
            this={status.icon} 
            class="h-4 w-4 {status.class} {status.animate ? 'animate-spin' : ''}" 
          />
          {#if hasResult || hasArgs}
            <button 
              onclick={() => toggleExpand(toolCall.id)}
              class="p-1 hover:bg-zinc-700 rounded transition-colors"
            >
              {#if isExpanded}
                <ChevronUp class="h-4 w-4 text-zinc-400" />
              {:else}
                <ChevronDown class="h-4 w-4 text-zinc-400" />
              {/if}
            </button>
          {/if}
        </div>
      </div>

      <!-- Arguments (collapsed by default, show preview) -->
      {#if hasArgs}
        <div class="border-b border-zinc-700/50 bg-zinc-900/30 px-3 py-2">
          <div class="text-xs text-zinc-500 mb-1">Arguments</div>
          {#if isExpanded}
            <table class="w-full">
              <tbody>
                {#each Object.entries(toolCall.args) as [key, value]}
                  <tr class="border-t border-zinc-700/30 first:border-0">
                    <td class="py-1 pr-3 text-sm font-medium text-zinc-300 whitespace-nowrap align-top">
                      {key}
                    </td>
                    <td class="py-1 text-sm text-zinc-400">
                      {#if isComplexValue(value)}
                        <pre class="whitespace-pre-wrap break-all text-xs bg-zinc-800 rounded p-1">{formatValue(value)}</pre>
                      {:else}
                        <span class="break-all">{formatValue(value)}</span>
                      {/if}
                    </td>
                  </tr>
                {/each}
              </tbody>
            </table>
          {:else}
            <div class="text-sm text-zinc-400 truncate">
              {Object.entries(toolCall.args).map(([k, v]) => `${k}: ${formatValue(v)}`).join(', ')}
            </div>
          {/if}
        </div>
      {/if}

      <!-- Result -->
      {#if toolCall.result}
        {@const resultContent = toolCall.result.error || toolCall.result.content}
        {@const isError = !!toolCall.result.error}
        {@const preview = truncateContent(resultContent)}
        
        <div class="px-3 py-2 {isError ? 'bg-red-900/10' : 'bg-zinc-900/20'}">
          <div class="text-xs {isError ? 'text-red-400' : 'text-zinc-500'} mb-1">
            {isError ? 'Error' : 'Result'}
          </div>
          
          {#if isExpanded}
            <pre class="whitespace-pre-wrap break-all text-sm {isError ? 'text-red-300' : 'text-zinc-300'} max-h-64 overflow-y-auto">{resultContent}</pre>
          {:else}
            <div class="text-sm {isError ? 'text-red-300' : 'text-zinc-400'} truncate">
              {preview.text}
            </div>
          {/if}
        </div>
      {:else if toolCall.status === 'executing'}
        <div class="px-3 py-2 bg-zinc-900/20">
          <div class="flex items-center gap-2 text-sm text-zinc-500">
            <Loader2 class="h-3 w-3 animate-spin" />
            <span>Executing...</span>
          </div>
        </div>
      {/if}
    </div>
  {/each}
</div>

