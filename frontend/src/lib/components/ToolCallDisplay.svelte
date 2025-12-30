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
  import ListTodo from '@lucide/svelte/icons/list-todo';
  import Brain from '@lucide/svelte/icons/brain';
  import Search from '@lucide/svelte/icons/search';
  import HelpCircle from '@lucide/svelte/icons/help-circle';
  import MessageCircle from '@lucide/svelte/icons/message-circle';
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

  function parseChoicesResponse(content: string, options: any[] = []) {
    try {
      const data = JSON.parse(content);
      const selected = data.selected || [];
      const freeform = data.freeform;
      
      const labels = selected.map((id: string) => {
        const option = options.find(o => o.id === id);
        return option ? option.label : id;
      });
      
      return { labels, freeform };
    } catch {
      return { labels: [], freeform: content };
    }
  }
</script>

<div class="flex flex-col gap-2">
  {#each toolCalls as toolCall (toolCall.id)}
    {#if toolCall.name === 'write_todos'}
      <div class="flex items-center gap-2 px-1 py-1.5 text-sm text-zinc-400 font-medium">
        <ListTodo class="h-4 w-4 text-amber-500/50" />
        <span>{toolCall.status === 'completed' ? 'Updated todos' : 'Updating todos...'}</span>
        {#if toolCall.status === 'executing'}
          <Loader2 class="h-3.5 w-3.5 animate-spin text-amber-500/50" />
        {/if}
      </div>
    {:else if toolCall.name === 'think_tool'}
      {@const isExpanded = expandedIds.has(toolCall.id)}
      {@const reflection = toolCall.args.reflection}
      <div class="flex flex-col gap-1">
        <button 
          onclick={() => toggleExpand(toolCall.id)}
          class="flex items-center gap-2 px-1 py-1.5 text-sm text-zinc-400 font-medium hover:text-zinc-300 transition-colors group"
        >
          <Brain class="h-4 w-4 text-purple-500/50 group-hover:text-purple-400/70" />
          <span>{toolCall.status === 'completed' ? 'Reflected on progress' : 'Thinking...'}</span>
          {#if toolCall.status === 'executing'}
            <Loader2 class="h-3.5 w-3.5 animate-spin text-purple-500/50" />
          {/if}
          <div class="flex-1"></div>
          {#if reflection}
            {#if isExpanded}
              <ChevronUp class="h-3.5 w-3.5 opacity-50" />
            {:else}
              <ChevronDown class="h-3.5 w-3.5 opacity-50" />
            {/if}
          {/if}
        </button>
        
        {#if isExpanded && reflection}
          <div class="ml-6 p-3 rounded-xl bg-purple-500/5 border border-purple-500/10 text-sm text-zinc-400 leading-relaxed italic">
            {reflection}
          </div>
        {/if}
      </div>
    {:else if toolCall.name === 'tavily_search'}
      <div class="flex items-center gap-2 px-1 py-1.5 text-sm text-zinc-400 font-medium">
        <Search class="h-4 w-4 text-blue-500/50" />
        <span>{toolCall.status === 'completed' ? 'Searched for:' : 'Searching for:'} <span class="text-zinc-300 font-semibold italic">"{toolCall.args.query}"</span></span>
        {#if toolCall.status === 'executing'}
          <Loader2 class="h-3.5 w-3.5 animate-spin text-blue-500/50" />
        {/if}
      </div>
    {:else if toolCall.name === 'ask_user' || toolCall.name === 'ask_choices'}
      {@const isChoices = toolCall.name === 'ask_choices'}
      {@const question = toolCall.args.question}
      {@const response = toolCall.result?.content}
      <div class="my-2 flex flex-col gap-2 rounded-xl border border-blue-500/20 bg-blue-500/5 p-3 overflow-hidden">
        <!-- Question -->
        <div class="flex items-start gap-2.5">
          <div class="mt-0.5 rounded-full bg-blue-500/10 p-1 text-blue-400">
            <HelpCircle class="h-3.5 w-3.5" />
          </div>
          <div class="flex-1 min-w-0">
            <p class="text-[10px] font-semibold uppercase tracking-wider text-blue-400/70 mb-0.5">Clarification Request</p>
            <p class="text-sm text-zinc-200 leading-relaxed font-medium">{question}</p>
          </div>
        </div>
        
        <!-- Answer -->
        {#if response}
          <div class="flex items-start gap-2.5 ml-1 border-l-2 border-blue-500/20 pl-4 py-1 mt-1">
            <div class="mt-0.5 text-blue-400/50">
              <MessageCircle class="h-3.5 w-3.5" />
            </div>
            <div class="flex-1 min-w-0">
              {#if isChoices}
                {@const { labels, freeform } = parseChoicesResponse(response, toolCall.args.options as any[])}
                <div class="flex flex-wrap gap-1.5 mb-1">
                  {#each labels as label}
                    <span class="rounded-md bg-blue-500/20 px-2 py-0.5 text-xs font-medium text-blue-200 border border-blue-500/30">
                      {label}
                    </span>
                  {/each}
                </div>
                {#if freeform}
                  <p class="text-sm text-zinc-300 italic">{freeform}</p>
                {/if}
              {:else}
                <p class="text-sm text-zinc-300 italic">"{response}"</p>
              {/if}
            </div>
          </div>
        {:else if toolCall.status === 'executing'}
          <div class="flex items-center gap-2 ml-7 mt-1 text-xs text-blue-400/60 italic">
            <Loader2 class="h-3 w-3 animate-spin" />
            <span>Awaiting user response...</span>
          </div>
        {/if}
      </div>
    {:else}
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
          <status.icon 
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
    {/if}
  {/each}
</div>

