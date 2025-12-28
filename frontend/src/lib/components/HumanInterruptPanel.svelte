<script lang="ts">
  import MessageCircle from '@lucide/svelte/icons/message-circle';
  import Check from '@lucide/svelte/icons/check';
  import X from '@lucide/svelte/icons/x';
  import FileText from '@lucide/svelte/icons/file-text';
  import Search from '@lucide/svelte/icons/search';
  import FolderOpen from '@lucide/svelte/icons/folder-open';
  import Wrench from '@lucide/svelte/icons/wrench';
  import Edit from '@lucide/svelte/icons/edit';
  import FilePlus from '@lucide/svelte/icons/file-plus';
  import { Button } from './ui/index.js';
  import { agentStore } from '$lib/stores/index.js';
  import type { HITLInterrupt, HITLActionRequest, HITLReviewConfig, ClientToolInterrupt } from '$lib/stores/types.js';

  // The current interrupts from the agent store
  // Prioritize clientToolInterrupt as it's the newer pattern for file operations
  const hitlInterrupt = $derived(agentStore.hitlInterrupt);
  const clientToolInterrupt = $derived(agentStore.clientToolInterrupt);
  const awaitingResponse = $derived(agentStore.awaitingHumanResponse);
  
  // Use clientToolInterrupt if available, otherwise fall back to hitlInterrupt
  // clientToolInterrupt is used for file operations that execute on the client
  const interrupt = $derived.by(() => {
    if (clientToolInterrupt) {
      // Convert clientToolInterrupt to HITLInterrupt-like structure for display
      return {
        action_requests: clientToolInterrupt.action_requests || clientToolInterrupt.tool_calls.map(tc => ({
          name: tc.name,
          args: tc.args,
          description: `Execute ${tc.name}`
        })),
        review_configs: clientToolInterrupt.review_configs || [{
          action_name: clientToolInterrupt.tool_calls[0]?.name || '',
          allowed_decisions: ['approve', 'reject']
        }]
      } as HITLInterrupt;
    }
    return hitlInterrupt;
  });
  
  // Track if this is a client tool interrupt (requires local execution)
  const isClientToolInterrupt = $derived(!!clientToolInterrupt);

  // Local state
  let isSubmitting = $state(false);

  // Get tool icon based on action name
  function getToolIcon(name: string) {
    switch (name) {
      case 'list_files':
        return FolderOpen;
      case 'get_file':
        return FileText;
      case 'search_files':
        return Search;
      case 'edit_file':
        return Edit;
      case 'create_file':
        return FilePlus;
      default:
        return Wrench;
    }
  }

  // Derived tool icon for first action
  const ToolIcon = $derived(
    interrupt?.action_requests?.[0] 
      ? getToolIcon(interrupt.action_requests[0].name) 
      : Wrench
  );

  // Get a friendly description of what the agent wants to do
  function getActionDescription(action: HITLActionRequest): string {
    const args = action.args || {};
    
    switch (action.name) {
      case 'list_files':
        return 'List all files in your project';
      case 'get_file':
        return `Read file: "${args.file_id || 'unknown'}"`;
      case 'search_files':
        return `Search files for: "${args.query || 'unknown'}"`;
      case 'edit_file':
        return `Edit file: "${args.file_id || 'unknown'}"`;
      case 'create_file':
        return `Create new file: "${args.title || 'unknown'}"`;
      default:
        return action.description || `Execute: ${action.name}`;
    }
  }

  // Get allowed decisions for an action
  function getAllowedDecisions(actionName: string, reviewConfigs: HITLReviewConfig[]): string[] {
    const config = reviewConfigs.find(c => c.action_name === actionName);
    return config?.allowed_decisions || ['approve', 'reject'];
  }

  // Handle approve all
  async function handleApproveAll() {
    if (!interrupt) return;
    isSubmitting = true;
    
    try {
      if (isClientToolInterrupt) {
        // For client tool interrupts, execute tools locally then resume
        await agentStore.executeApprovedWriteTools();
      } else {
        // For regular HITL, just send approval
        await agentStore.approveAllActions();
      }
    } finally {
      isSubmitting = false;
    }
  }

  // Handle reject all
  async function handleRejectAll() {
    if (!interrupt) return;
    isSubmitting = true;
    
    try {
      if (isClientToolInterrupt) {
        // For client tool interrupts, reject means don't execute
        await agentStore.rejectClientToolInterrupt();
      } else {
        await agentStore.rejectAllActions();
      }
    } finally {
      isSubmitting = false;
    }
  }
</script>

{#if interrupt && awaitingResponse}
  <div class="mx-4 mb-4 overflow-hidden rounded-xl border border-amber-500/30 bg-gradient-to-br from-amber-900/20 to-zinc-900/80 shadow-lg">
    <!-- Header -->
    <div class="flex items-center gap-3 border-b border-amber-500/20 bg-amber-900/30 px-4 py-3">
      <div class="flex h-8 w-8 items-center justify-center rounded-lg bg-amber-500/20">
        <MessageCircle class="h-4 w-4 text-amber-400" />
      </div>
      <div>
        <h3 class="text-sm font-semibold text-amber-200">Agent Needs Approval</h3>
        <p class="text-xs text-amber-300/70">
          {interrupt.action_requests.length === 1 
            ? 'Review and approve the requested action' 
            : `Review ${interrupt.action_requests.length} actions`}
        </p>
      </div>
    </div>

    <!-- Content -->
    <div class="p-4 space-y-3">
      <!-- Action Requests -->
      {#each interrupt.action_requests as action, index}
        {@const allowedDecisions = getAllowedDecisions(action.name, interrupt.review_configs)}
        {@const ActionIcon = getToolIcon(action.name)}
        
        <div class="flex items-start gap-3 rounded-lg bg-zinc-800/50 p-3">
          <div class="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-zinc-700/50">
            <svelte:component this={ActionIcon} class="h-5 w-5 text-zinc-300" />
          </div>
          <div class="flex-1 min-w-0">
            <p class="text-sm font-medium text-zinc-200">
              {action.name}
            </p>
            <p class="text-xs text-zinc-400 mt-1">
              {getActionDescription(action)}
            </p>
            {#if Object.keys(action.args || {}).length > 0}
              <div class="mt-2 text-xs space-y-0.5">
                {#each Object.entries(action.args || {}) as [key, value]}
                  <div class="flex gap-2 text-zinc-500">
                    <span class="font-mono">{key}:</span>
                    <span class="text-zinc-400 truncate max-w-[200px]">
                      {typeof value === 'string' ? value : JSON.stringify(value)}
                    </span>
                  </div>
                {/each}
              </div>
            {/if}
            <!-- Allowed decisions badge -->
            <div class="mt-2 flex gap-1">
              {#each allowedDecisions as decision}
                <span class="px-1.5 py-0.5 text-[10px] rounded bg-zinc-700/50 text-zinc-400">
                  {decision}
                </span>
              {/each}
            </div>
          </div>
        </div>
      {/each}

      <!-- Action Buttons -->
      <div class="flex items-center justify-between gap-3 pt-2">
        <Button
          onclick={handleRejectAll}
          disabled={isSubmitting}
          variant="ghost"
          size="sm"
          class="text-zinc-400 hover:text-red-400 hover:bg-red-500/10"
        >
          <X class="h-4 w-4 mr-1" />
          Reject
        </Button>
        
        <Button
          onclick={handleApproveAll}
          disabled={isSubmitting}
          size="sm"
          class="bg-emerald-600 hover:bg-emerald-500 text-white"
        >
          <Check class="h-4 w-4 mr-1" />
          {interrupt.action_requests.length === 1 ? 'Approve' : 'Approve All'}
        </Button>
      </div>
    </div>
  </div>
{/if}
