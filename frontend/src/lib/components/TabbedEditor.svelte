<script lang="ts">
  import X from '@lucide/svelte/icons/x';
  import ChevronLeft from '@lucide/svelte/icons/chevron-left';
  import ChevronRight from '@lucide/svelte/icons/chevron-right';
  import Save from '@lucide/svelte/icons/save';
  import RotateCcw from '@lucide/svelte/icons/rotate-ccw';
  import { artifactStore } from '$lib/stores/index.js';
  import type { Artifact } from '$lib/stores/types.js';
  import { onMount, onDestroy } from 'svelte';
  import { browser } from '$app/environment';

  // Monaco types - dynamically loaded
  type Monaco = typeof import('monaco-editor');
  type IStandaloneCodeEditor = import('monaco-editor').editor.IStandaloneCodeEditor;
  type IStandaloneDiffEditor = import('monaco-editor').editor.IStandaloneDiffEditor;

  interface Props {
    openArtifacts: Artifact[];
    activeArtifactId: string | null;
    onTabSelect: (id: string) => void;
    onTabClose: (id: string) => void;
    pendingChanges?: { artifactId: string; newContent: string; oldContent: string } | null;
    onAcceptChanges?: () => void;
    onRejectChanges?: () => void;
  }

  let {
    openArtifacts,
    activeArtifactId,
    onTabSelect,
    onTabClose,
    pendingChanges = null,
    onAcceptChanges,
    onRejectChanges
  }: Props = $props();

  let editorContainer: HTMLDivElement;
  let diffContainer: HTMLDivElement;
  let editor: IStandaloneCodeEditor | null = null;
  let diffEditor: IStandaloneDiffEditor | null = null;
  let monaco: Monaco | null = null;
  let isEditing = $state(false);
  let hasUnsavedChanges = $state(false);
  let isMonacoReady = $state(false);

  const activeArtifact = $derived(
    openArtifacts.find((a) => a.id === activeArtifactId) ?? null
  );

  const currentContent = $derived(() => {
    if (!activeArtifact) return null;
    return activeArtifact.versions[activeArtifact.currentVersionIndex] ?? null;
  });

  const canGoPrev = $derived(
    activeArtifact && activeArtifact.currentVersionIndex > 0
  );

  const canGoNext = $derived(
    activeArtifact &&
      activeArtifact.currentVersionIndex < activeArtifact.versions.length - 1
  );

  const showDiff = $derived(
    pendingChanges && pendingChanges.artifactId === activeArtifactId
  );

  function getLanguage(artifact: Artifact | null): string {
    if (!artifact) return 'plaintext';
    if (artifact.type === 'code') {
      const version = artifact.versions[artifact.currentVersionIndex];
      return version?.language?.toLowerCase() || 'typescript';
    }
    if (artifact.type === 'socratic') return 'markdown';
    return 'markdown';
  }

  function handlePrevVersion() {
    if (!activeArtifact || !canGoPrev) return;
    artifactStore.setArtifactVersion(
      activeArtifact.id,
      activeArtifact.currentVersionIndex - 1
    );
  }

  function handleNextVersion() {
    if (!activeArtifact || !canGoNext) return;
    artifactStore.setArtifactVersion(
      activeArtifact.id,
      activeArtifact.currentVersionIndex + 1
    );
  }

  function handleSave() {
    if (!activeArtifact || !editor) return;

    const content = editor.getValue();
    const currentVersion = currentContent();
    
    artifactStore.updateArtifact(
      activeArtifact.id,
      currentVersion?.title || 'Untitled',
      content,
      currentVersion?.language
    );
    
    hasUnsavedChanges = false;
    isEditing = false;
  }

  function handleRevert() {
    if (!editor || !activeArtifact) return;
    const content = currentContent();
    if (content) {
      editor.setValue(content.content);
      hasUnsavedChanges = false;
    }
  }

  onMount(async () => {
    if (!browser) return;

    // Dynamically import Monaco on client only
    monaco = await import('monaco-editor');

    // Configure Monaco theme
    monaco.editor.defineTheme('socratic-dark', {
      base: 'vs-dark',
      inherit: true,
      rules: [],
      colors: {
        'editor.background': '#0a0a0a',
        'editor.foreground': '#e4e4e7',
        'editorLineNumber.foreground': '#52525b',
        'editorLineNumber.activeForeground': '#a1a1aa',
        'editor.selectionBackground': '#f59e0b33',
        'editor.lineHighlightBackground': '#18181b',
        'editorCursor.foreground': '#f59e0b'
      }
    });

    monaco.editor.setTheme('socratic-dark');
    isMonacoReady = true;
  });

  onDestroy(() => {
    editor?.dispose();
    diffEditor?.dispose();
  });

  // Create/update editor when active artifact changes
  $effect(() => {
    if (!browser || !isMonacoReady || !monaco || !editorContainer || showDiff) return;

    const content = currentContent();
    const lang = getLanguage(activeArtifact);

    if (!editor) {
      editor = monaco.editor.create(editorContainer, {
        value: content?.content || '',
        language: lang,
        theme: 'socratic-dark',
        fontSize: 14,
        fontFamily: "'JetBrains Mono', 'Fira Code', monospace",
        minimap: { enabled: false },
        lineNumbers: 'on',
        scrollBeyondLastLine: false,
        automaticLayout: true,
        padding: { top: 16 },
        wordWrap: activeArtifact?.type !== 'code' ? 'on' : 'off'
      });

      editor.onDidChangeModelContent(() => {
        hasUnsavedChanges = true;
        isEditing = true;
      });
    } else {
      const currentValue = editor.getValue();
      const newValue = content?.content || '';
      
      if (currentValue !== newValue && !hasUnsavedChanges) {
        editor.setValue(newValue);
      }
      
      monaco.editor.setModelLanguage(editor.getModel()!, lang);
    }
  });

  // Create diff editor when showing pending changes
  $effect(() => {
    if (!browser || !isMonacoReady || !monaco || !diffContainer || !showDiff || !pendingChanges) return;

    diffEditor?.dispose();

    const originalModel = monaco.editor.createModel(
      pendingChanges.oldContent,
      getLanguage(activeArtifact)
    );
    const modifiedModel = monaco.editor.createModel(
      pendingChanges.newContent,
      getLanguage(activeArtifact)
    );

    diffEditor = monaco.editor.createDiffEditor(diffContainer, {
      theme: 'socratic-dark',
      fontSize: 14,
      fontFamily: "'JetBrains Mono', 'Fira Code', monospace",
      minimap: { enabled: false },
      automaticLayout: true,
      readOnly: true,
      renderSideBySide: true
    });

    diffEditor.setModel({
      original: originalModel,
      modified: modifiedModel
    });
  });
</script>

<div class="flex h-full flex-col bg-zinc-950">
  {#if openArtifacts.length === 0}
    <!-- Empty state -->
    <div class="flex h-full items-center justify-center text-zinc-600">
      <div class="text-center">
        <p class="text-lg">No files open</p>
        <p class="mt-1 text-sm">Select a file from the explorer to edit</p>
      </div>
    </div>
  {:else}
    <!-- Tab bar -->
    <div class="flex items-center border-b border-zinc-800 bg-zinc-900/50">
      <div class="flex flex-1 overflow-x-auto">
        {#each openArtifacts as artifact (artifact.id)}
          {@const version = artifact.versions[artifact.currentVersionIndex]}
          {@const isActive = artifact.id === activeArtifactId}
          <div
            class="group flex items-center gap-2 border-r border-zinc-800 px-3 py-2 text-sm transition-colors cursor-pointer
              {isActive
                ? 'bg-zinc-950 text-zinc-100'
                : 'bg-zinc-900 text-zinc-400 hover:bg-zinc-800 hover:text-zinc-300'}"
            onclick={() => onTabSelect(artifact.id)}
            onkeydown={(e) => e.key === 'Enter' && onTabSelect(artifact.id)}
            role="tab"
            tabindex="0"
          >
            <span class="max-w-[120px] truncate">{version?.title || 'Untitled'}</span>
            {#if artifact.id === activeArtifactId && hasUnsavedChanges}
              <span class="h-2 w-2 rounded-full bg-amber-500"></span>
            {/if}
            <button
              onclick={(e) => {
                e.stopPropagation();
                onTabClose(artifact.id);
              }}
              class="rounded p-0.5 text-zinc-500 opacity-0 transition-all hover:bg-zinc-700 hover:text-zinc-300 group-hover:opacity-100
                {isActive ? 'opacity-100' : ''}"
            >
              <X class="h-3.5 w-3.5" />
            </button>
          </div>
        {/each}
      </div>

      <!-- Version navigation & save -->
      {#if activeArtifact}
        <div class="flex items-center gap-2 px-3">
          <button
            onclick={handlePrevVersion}
            disabled={!canGoPrev}
            class="rounded p-1 text-zinc-500 transition-colors hover:bg-zinc-800 hover:text-zinc-300 disabled:opacity-30"
            title="Previous version"
          >
            <ChevronLeft class="h-4 w-4" />
          </button>
          <span class="text-xs text-zinc-500">
            v{activeArtifact.currentVersionIndex + 1}/{activeArtifact.versions.length}
          </span>
          <button
            onclick={handleNextVersion}
            disabled={!canGoNext}
            class="rounded p-1 text-zinc-500 transition-colors hover:bg-zinc-800 hover:text-zinc-300 disabled:opacity-30"
            title="Next version"
          >
            <ChevronRight class="h-4 w-4" />
          </button>

          {#if hasUnsavedChanges}
            <div class="ml-2 flex items-center gap-1">
              <button
                onclick={handleRevert}
                class="rounded p-1 text-zinc-500 transition-colors hover:bg-zinc-800 hover:text-zinc-300"
                title="Revert changes"
              >
                <RotateCcw class="h-4 w-4" />
              </button>
              <button
                onclick={handleSave}
                class="flex items-center gap-1 rounded bg-amber-600 px-2 py-1 text-xs font-medium text-white transition-colors hover:bg-amber-500"
              >
                <Save class="h-3.5 w-3.5" />
                Save
              </button>
            </div>
          {/if}
        </div>
      {/if}
    </div>

    <!-- Editor area -->
    <div class="relative flex-1">
      {#if !isMonacoReady}
        <!-- Loading state -->
        <div class="absolute inset-0 flex items-center justify-center text-zinc-500">
          <div class="text-center">
            <div class="mb-2 h-6 w-6 animate-spin rounded-full border-2 border-zinc-600 border-t-amber-500 mx-auto"></div>
            <p class="text-sm">Loading editor...</p>
          </div>
        </div>
      {:else if showDiff}
        <!-- Diff view for pending changes -->
        <div class="absolute inset-0 flex flex-col">
          <div class="flex items-center justify-between border-b border-amber-500/30 bg-amber-500/10 px-4 py-2">
            <span class="text-sm font-medium text-amber-400">
              Agent proposed changes - Review and accept or reject
            </span>
            <div class="flex gap-2">
              <button
                onclick={onRejectChanges}
                class="rounded border border-zinc-600 px-3 py-1 text-sm text-zinc-300 transition-colors hover:bg-zinc-800"
              >
                Reject
              </button>
              <button
                onclick={onAcceptChanges}
                class="rounded bg-amber-600 px-3 py-1 text-sm font-medium text-white transition-colors hover:bg-amber-500"
              >
                Accept Changes
              </button>
            </div>
          </div>
          <div bind:this={diffContainer} class="flex-1"></div>
        </div>
      {:else}
        <!-- Regular editor -->
        <div bind:this={editorContainer} class="absolute inset-0"></div>
      {/if}
    </div>
  {/if}
</div>
