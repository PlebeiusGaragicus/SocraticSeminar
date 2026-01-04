<script lang="ts">
  import Settings from '@lucide/svelte/icons/settings';
  import Cpu from '@lucide/svelte/icons/cpu';
  import Layers from '@lucide/svelte/icons/layers';
  import Brain from '@lucide/svelte/icons/brain';
  import RotateCcw from '@lucide/svelte/icons/rotate-ccw';
  import { threadStore, assistantStore } from '$lib/stores/index.js';
  import { DEFAULT_AGENT_SETTINGS, type AgentSettings, type LLMModel } from '$lib/stores/types.js';
  import { onMount } from 'svelte';

  interface Props {
    threadId?: string | null;
  }

  let { threadId = null }: Props = $props();

  let isOpen = $state(false);
  let popoverRef: HTMLDivElement;
  let popoverPosition = $state({ top: 0, left: 0 });

  function updatePosition() {
    if (!popoverRef) return;
    const rect = popoverRef.getBoundingClientRect();
    const screenWidth = window.innerWidth;
    const popoverWidth = 288; // w-72
    
    // Calculate horizontal position
    let left = rect.left;
    if (left + popoverWidth > screenWidth - 16) {
      left = screenWidth - popoverWidth - 16;
    }
    if (left < 16) {
      left = 16;
    }
    
    // Calculate vertical position (try below, fallback to above if needed)
    let top = rect.bottom + 4;
    // We don't have the popover height yet, but we can estimate or just bound it
    // For now, staying below the button is usually preferred in this layout.
    
    popoverPosition = { top, left };
  }

  function toggleOpen() {
    if (!isOpen) {
      updatePosition();
    }
    isOpen = !isOpen;
  }

  // Get current thread's settings
  const currentThread = $derived(
    threadId ? threadStore.threads.find(t => t.id === threadId) : null
  );

  // Get the current assistant for this thread
  const currentAssistant = $derived.by(() => {
    const assistantId = currentThread?.assistantId || assistantStore.selectedAssistantId;
    return assistantStore.assistants.find(a => a.assistant_id === assistantId) || null;
  });

  // Determine agent type from graph_id
  const agentType = $derived.by((): 'deepresearch' | 'deeptutor' | 'unknown' => {
    if (!currentAssistant) return 'unknown';
    const graphId = currentAssistant.graph_id;
    if (graphId === 'deepresearch') return 'deepresearch';
    if (graphId === 'deeptutor') return 'deeptutor';
    return 'unknown';
  });

  // Merge with defaults
  const settings = $derived<AgentSettings>({
    ...DEFAULT_AGENT_SETTINGS,
    ...(currentThread?.agentSettings || {})
  });

  // LLM options
  const llmOptions: { value: LLMModel; label: string; description: string }[] = [
    { 
      value: 'qwen3-coder-30b-a3b-instruct-mlx', 
      label: 'Qwen3 Coder', 
      description: 'Local 30B model, fast & private'
    },
    { 
      value: 'grok-4-1-fast-non-reasoning', 
      label: 'Grok 4 Fast', 
      description: 'XAI cloud model, very capable'
    },
  ];

  function updateSetting<K extends keyof AgentSettings>(key: K, value: AgentSettings[K]) {
    if (!threadId) return;
    
    const newSettings: AgentSettings = {
      ...settings,
      [key]: value
    };
    
    threadStore.updateThread(threadId, { agentSettings: newSettings });
  }

  function resetToDefaults() {
    if (!threadId) return;
    threadStore.updateThread(threadId, { agentSettings: DEFAULT_AGENT_SETTINGS });
  }

  function handleClickOutside(event: MouseEvent) {
    if (isOpen && popoverRef && !popoverRef.contains(event.target as Node)) {
      isOpen = false;
    }
  }

  onMount(() => {
    const handleResize = () => {
      if (isOpen) updatePosition();
    };
    window.addEventListener('resize', handleResize);
    document.addEventListener('click', handleClickOutside);
    return () => {
      window.removeEventListener('resize', handleResize);
      document.removeEventListener('click', handleClickOutside);
    };
  });
</script>

<div bind:this={popoverRef} class="relative" role="presentation">
  <button
    onclick={toggleOpen}
    disabled={!threadId}
    class="flex items-center justify-center h-8 w-8 rounded-lg border border-zinc-700 bg-zinc-800 text-zinc-400 transition-colors hover:bg-zinc-700 hover:border-zinc-600 hover:text-zinc-200 disabled:opacity-30 disabled:cursor-not-allowed"
    title="Agent Settings"
  >
    <Settings class="h-4 w-4" />
  </button>

  {#if isOpen && threadId}
    <div 
      class="fixed z-[100] w-72 rounded-lg border border-zinc-700 bg-zinc-800 shadow-xl"
      style="top: {popoverPosition.top}px; left: {popoverPosition.left}px;"
      role="presentation"
    >
      <!-- Header -->
      <div class="flex items-center justify-between border-b border-zinc-700 px-4 py-3">
        <div class="flex items-center gap-2">
          <Settings class="h-4 w-4 text-amber-500" />
          <span class="text-sm font-semibold text-zinc-200">Agent Settings</span>
        </div>
        <button
          onclick={resetToDefaults}
          class="rounded p-1 text-zinc-500 transition-colors hover:bg-zinc-700 hover:text-zinc-300"
          title="Reset to defaults"
        >
          <RotateCcw class="h-3.5 w-3.5" />
        </button>
      </div>

      <div class="p-4 space-y-5">
        <!-- LLM Selection -->
        <div>
          <label class="flex items-center gap-2 text-xs font-medium text-zinc-400 uppercase tracking-wider mb-2">
            <Cpu class="h-3.5 w-3.5" />
            Language Model
          </label>
          <div class="space-y-1.5">
            {#each llmOptions as option}
              {@const isSelected = settings.llm_model === option.value}
              <button
                onclick={() => updateSetting('llm_model', option.value)}
                class="w-full flex items-start gap-3 p-2.5 rounded-lg border transition-colors text-left
                  {isSelected 
                    ? 'border-amber-500/50 bg-amber-500/10' 
                    : 'border-zinc-700 bg-zinc-800/50 hover:border-zinc-600 hover:bg-zinc-700/50'}"
              >
                <div class="mt-0.5 flex h-4 w-4 items-center justify-center rounded-full border-2 shrink-0
                  {isSelected ? 'border-amber-500' : 'border-zinc-600'}">
                  {#if isSelected}
                    <div class="h-2 w-2 rounded-full bg-amber-500"></div>
                  {/if}
                </div>
                <div class="flex-1 min-w-0">
                  <span class="block text-sm font-medium {isSelected ? 'text-amber-200' : 'text-zinc-200'}">
                    {option.label}
                  </span>
                  <span class="block text-xs text-zinc-500 mt-0.5">
                    {option.description}
                  </span>
                </div>
              </button>
            {/each}
          </div>
        </div>

        <!-- Agent-specific Settings -->
        {#if agentType === 'deepresearch'}
          <!-- Research Settings (deepresearch only) -->
          <div>
            <label class="flex items-center gap-2 text-xs font-medium text-zinc-400 uppercase tracking-wider mb-3">
              <Layers class="h-3.5 w-3.5" />
              Research Settings
            </label>
            
            <!-- Concurrent Research Units -->
            <div class="mb-4">
              <div class="flex items-center justify-between mb-1.5">
                <span class="text-xs text-zinc-400">Parallel Tasks</span>
                <span class="text-xs font-mono text-amber-400 bg-zinc-900 px-1.5 py-0.5 rounded">
                  {settings.max_concurrent_research_units}
                </span>
              </div>
              <input
                type="range"
                min="1"
                max="10"
                value={settings.max_concurrent_research_units}
                oninput={(e) => updateSetting('max_concurrent_research_units', parseInt(e.currentTarget.value))}
                class="w-full h-1.5 bg-zinc-700 rounded-lg appearance-none cursor-pointer accent-amber-500"
              />
              <div class="flex justify-between text-[10px] text-zinc-600 mt-1">
                <span>1</span>
                <span>5</span>
                <span>10</span>
              </div>
            </div>

            <!-- Max Iterations -->
            <div>
              <div class="flex items-center justify-between mb-1.5">
                <span class="text-xs text-zinc-400">Max Iterations</span>
                <span class="text-xs font-mono text-amber-400 bg-zinc-900 px-1.5 py-0.5 rounded">
                  {settings.max_researcher_iterations}
                </span>
              </div>
              <input
                type="range"
                min="1"
                max="10"
                value={settings.max_researcher_iterations}
                oninput={(e) => updateSetting('max_researcher_iterations', parseInt(e.currentTarget.value))}
                class="w-full h-1.5 bg-zinc-700 rounded-lg appearance-none cursor-pointer accent-amber-500"
              />
              <div class="flex justify-between text-[10px] text-zinc-600 mt-1">
                <span>1</span>
                <span>5</span>
                <span>10</span>
              </div>
            </div>
          </div>
        {:else if agentType === 'deeptutor'}
          <!-- Tutor Settings (deeptutor only) -->
          <div>
            <label class="flex items-center gap-2 text-xs font-medium text-zinc-400 uppercase tracking-wider mb-3">
              <Brain class="h-3.5 w-3.5" />
              Tutor Settings
            </label>
            
            <!-- Enable Thinking Tool -->
            <button
              onclick={() => updateSetting('enable_thinking_tool', !settings.enable_thinking_tool)}
              class="w-full flex items-center justify-between p-3 rounded-lg border transition-colors
                {settings.enable_thinking_tool 
                  ? 'border-amber-500/50 bg-amber-500/10' 
                  : 'border-zinc-700 bg-zinc-800/50 hover:border-zinc-600'}"
            >
              <div class="flex-1 text-left">
                <span class="block text-sm font-medium {settings.enable_thinking_tool ? 'text-amber-200' : 'text-zinc-200'}">
                  Thinking Tool
                </span>
                <span class="block text-xs text-zinc-500 mt-0.5">
                  Enable strategic reflection during dialogue
                </span>
              </div>
              <div class="relative ml-3 h-5 w-9 rounded-full transition-colors
                {settings.enable_thinking_tool ? 'bg-amber-500' : 'bg-zinc-600'}">
                <div class="absolute top-0.5 h-4 w-4 rounded-full bg-white shadow-sm transition-transform
                  {settings.enable_thinking_tool ? 'translate-x-4' : 'translate-x-0.5'}"></div>
              </div>
            </button>
          </div>
        {/if}

        <!-- Info -->
        <p class="text-[10px] text-zinc-600 leading-relaxed">
          Settings apply to this thread only.
        </p>
      </div>
    </div>
  {/if}
</div>

