<script lang="ts">
  import HelpCircle from '@lucide/svelte/icons/help-circle';
  import Send from '@lucide/svelte/icons/send';
  import Check from '@lucide/svelte/icons/check';
  import { Button } from './ui/index.js';
  import { agentStore } from '$lib/stores/index.js';
  import type { ClarificationInterrupt, ClarificationResponse } from '$lib/stores/types.js';

  // Get clarification interrupt from agent store
  const clarificationInterrupt = $derived(agentStore.clarificationInterrupt);
  const awaitingResponse = $derived(agentStore.awaitingHumanResponse);
  
  // Local state
  let isSubmitting = $state(false);
  let freeformResponse = $state('');
  let selectedOptions = $state<string[]>([]);

  // Reset state when interrupt changes
  $effect(() => {
    if (clarificationInterrupt) {
      freeformResponse = '';
      selectedOptions = [];
    }
  });

  // Handle option selection
  function toggleOption(optionId: string) {
    if (!clarificationInterrupt) return;
    
    if (clarificationInterrupt.allow_multiple) {
      // Multi-select: toggle in/out
      if (selectedOptions.includes(optionId)) {
        selectedOptions = selectedOptions.filter(id => id !== optionId);
      } else {
        selectedOptions = [...selectedOptions, optionId];
      }
    } else {
      // Single-select: replace
      selectedOptions = [optionId];
    }
  }

  // Handle submit for ask_user
  async function handleFreeformSubmit() {
    if (!clarificationInterrupt || !freeformResponse.trim()) return;
    isSubmitting = true;
    
    try {
      const response: ClarificationResponse = {
        response: freeformResponse.trim()
      };
      await agentStore.resumeWithClarificationResponse(response);
    } finally {
      isSubmitting = false;
      freeformResponse = '';
    }
  }

  // Handle submit for ask_choices
  async function handleChoicesSubmit() {
    if (!clarificationInterrupt) return;
    
    // Need at least one selection, or freeform if allowed
    if (selectedOptions.length === 0 && !freeformResponse.trim()) return;
    
    isSubmitting = true;
    
    try {
      const response: ClarificationResponse = {
        selected: selectedOptions.length > 0 ? selectedOptions : undefined,
        freeform: freeformResponse.trim() || undefined
      };
      await agentStore.resumeWithClarificationResponse(response);
    } finally {
      isSubmitting = false;
      selectedOptions = [];
      freeformResponse = '';
    }
  }

  // Check if submit should be enabled
  const canSubmitChoices = $derived(() => {
    if (!clarificationInterrupt) return false;
    return selectedOptions.length > 0 || (clarificationInterrupt.allow_freeform && freeformResponse.trim());
  });

  // Handle keyboard submit
  function handleKeydown(event: KeyboardEvent) {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault();
      if (clarificationInterrupt?.tool === 'ask_user') {
        handleFreeformSubmit();
      } else {
        handleChoicesSubmit();
      }
    }
  }
</script>

{#if clarificationInterrupt && awaitingResponse}
  <div class="mx-4 mb-4 overflow-hidden rounded-xl border border-blue-500/30 bg-gradient-to-br from-blue-900/20 to-zinc-900/80 shadow-lg">
    <!-- Header -->
    <div class="flex items-center gap-3 border-b border-blue-500/20 bg-blue-900/30 px-4 py-3">
      <div class="flex h-8 w-8 items-center justify-center rounded-lg bg-blue-500/20">
        <HelpCircle class="h-4 w-4 text-blue-400" />
      </div>
      <div>
        <h3 class="text-sm font-semibold text-blue-200">Agent Needs Clarification</h3>
        <p class="text-xs text-blue-300/70">Please answer the question below</p>
      </div>
    </div>

    <!-- Content -->
    <div class="p-4 space-y-4">
      <!-- Question -->
      <p class="text-sm text-zinc-200 leading-relaxed">
        {clarificationInterrupt.question}
      </p>

      {#if clarificationInterrupt.tool === 'ask_user'}
        <!-- Free-form text input -->
        <div class="space-y-3">
          <textarea
            bind:value={freeformResponse}
            onkeydown={handleKeydown}
            placeholder="Type your response..."
            rows="3"
            disabled={isSubmitting}
            class="w-full rounded-lg border border-zinc-600 bg-zinc-800/50 px-3 py-2 text-sm text-zinc-200 placeholder:text-zinc-500 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 resize-none"
          ></textarea>
          
          <div class="flex justify-end">
            <Button
              onclick={handleFreeformSubmit}
              disabled={isSubmitting || !freeformResponse.trim()}
              size="sm"
              class="bg-blue-600 hover:bg-blue-500 text-white"
            >
              <Send class="h-4 w-4 mr-1" />
              Send
            </Button>
          </div>
        </div>
      {:else}
        <!-- Choices -->
        <div class="space-y-2">
          {#each clarificationInterrupt.options || [] as option}
            <button
              type="button"
              onclick={() => toggleOption(option.id)}
              disabled={isSubmitting}
              class="w-full flex items-center gap-3 rounded-lg border px-3 py-2.5 text-left transition-colors
                {selectedOptions.includes(option.id)
                  ? 'border-blue-500 bg-blue-500/20 text-blue-200'
                  : 'border-zinc-600 bg-zinc-800/50 text-zinc-300 hover:border-zinc-500 hover:bg-zinc-700/50'}"
            >
              <div class="flex h-5 w-5 shrink-0 items-center justify-center rounded border
                {selectedOptions.includes(option.id)
                  ? 'border-blue-500 bg-blue-500'
                  : 'border-zinc-500'}">
                {#if selectedOptions.includes(option.id)}
                  <Check class="h-3 w-3 text-white" />
                {/if}
              </div>
              <span class="text-sm">{option.label}</span>
            </button>
          {/each}
        </div>

        {#if clarificationInterrupt.allow_freeform}
          <!-- Optional freeform with choices -->
          <div class="pt-2">
            <input
              type="text"
              bind:value={freeformResponse}
              onkeydown={handleKeydown}
              placeholder="Or type your own response..."
              disabled={isSubmitting}
              class="w-full rounded-lg border border-zinc-600 bg-zinc-800/50 px-3 py-2 text-sm text-zinc-200 placeholder:text-zinc-500 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
            />
          </div>
        {/if}

        <div class="flex justify-end pt-2">
          <Button
            onclick={handleChoicesSubmit}
            disabled={isSubmitting || !canSubmitChoices()}
            size="sm"
            class="bg-blue-600 hover:bg-blue-500 text-white"
          >
            <Send class="h-4 w-4 mr-1" />
            Submit
          </Button>
        </div>
      {/if}
    </div>
  </div>
{/if}

