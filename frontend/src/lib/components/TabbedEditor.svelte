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

  // CodeMirror imports (dynamically loaded on client)
  type EditorView = import('@codemirror/view').EditorView;

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

  let editorContainer = $state<HTMLDivElement | null>(null);
  let diffContainer = $state<HTMLDivElement | null>(null);
  let editor: EditorView | null = null;
  let isEditing = $state(false);
  let hasUnsavedChanges = $state(false);
  let isEditorReady = $state(false);
  let currentEditorArtifactId: string | null = null;

  // Store CodeMirror modules after dynamic import
  let cmModules: {
    EditorView: typeof import('@codemirror/view').EditorView;
    keymap: typeof import('@codemirror/view').keymap;
    lineNumbers: typeof import('@codemirror/view').lineNumbers;
    highlightActiveLine: typeof import('@codemirror/view').highlightActiveLine;
    highlightActiveLineGutter: typeof import('@codemirror/view').highlightActiveLineGutter;
    EditorState: typeof import('@codemirror/state').EditorState;
    markdown: typeof import('@codemirror/lang-markdown').markdown;
    languages: typeof import('@codemirror/language-data').languages;
    oneDark: typeof import('@codemirror/theme-one-dark').oneDark;
    defaultKeymap: typeof import('@codemirror/commands').defaultKeymap;
    history: typeof import('@codemirror/commands').history;
    historyKeymap: typeof import('@codemirror/commands').historyKeymap;
    livePreview: typeof import('$lib/codemirror/livePreview.js').livePreview;
    MergeView: typeof import('@codemirror/merge').MergeView;
  } | null = null;

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

    const content = editor.state.doc.toString();
    const currentVersion = currentContent();
    
    artifactStore.updateArtifact(
      activeArtifact.id,
      currentVersion?.title || 'Untitled',
      content
    );
    
    hasUnsavedChanges = false;
    isEditing = false;
  }

  function handleRevert() {
    if (!editor || !activeArtifact || !cmModules) return;
    const content = currentContent();
    if (content) {
      editor.dispatch({
        changes: {
          from: 0,
          to: editor.state.doc.length,
          insert: content.content
        }
      });
      hasUnsavedChanges = false;
    }
  }

  // Custom theme that matches the existing socratic-dark aesthetic
  function createSocraticTheme(EditorView: typeof import('@codemirror/view').EditorView) {
    return EditorView.theme({
      '&': {
        height: '100%',
        fontSize: '15px',
        fontFamily: "'JetBrains Mono', 'Fira Code', 'SF Mono', monospace"
      },
      '.cm-content': {
        padding: '16px 0',
        caretColor: '#f59e0b'
      },
      '.cm-cursor': {
        borderLeftColor: '#f59e0b'
      },
      '&.cm-focused .cm-cursor': {
        borderLeftColor: '#f59e0b'
      },
      '.cm-gutters': {
        backgroundColor: '#0a0a0a',
        color: '#52525b',
        border: 'none'
      },
      '.cm-activeLineGutter': {
        backgroundColor: '#18181b',
        color: '#a1a1aa'
      },
      '.cm-activeLine': {
        backgroundColor: '#18181b'
      },
      '&.cm-focused .cm-selectionBackground, .cm-selectionBackground, .cm-content ::selection': {
        backgroundColor: '#f59e0b33'
      },
      '.cm-line': {
        lineHeight: '1.6'
      },
      '.cm-scroller': {
        overflow: 'auto'
      }
    }, { dark: true });
  }

  onMount(async () => {
    if (!browser) return;

    // Dynamically import CodeMirror modules
    const [
      viewModule,
      stateModule,
      markdownModule,
      langDataModule,
      themeModule,
      commandsModule,
      livePreviewModule,
      mergeModule
    ] = await Promise.all([
      import('@codemirror/view'),
      import('@codemirror/state'),
      import('@codemirror/lang-markdown'),
      import('@codemirror/language-data'),
      import('@codemirror/theme-one-dark'),
      import('@codemirror/commands'),
      import('$lib/codemirror/livePreview.js'),
      import('@codemirror/merge')
    ]);

    cmModules = {
      EditorView: viewModule.EditorView,
      keymap: viewModule.keymap,
      lineNumbers: viewModule.lineNumbers,
      highlightActiveLine: viewModule.highlightActiveLine,
      highlightActiveLineGutter: viewModule.highlightActiveLineGutter,
      EditorState: stateModule.EditorState,
      markdown: markdownModule.markdown,
      languages: langDataModule.languages,
      oneDark: themeModule.oneDark,
      defaultKeymap: commandsModule.defaultKeymap,
      history: commandsModule.history,
      historyKeymap: commandsModule.historyKeymap,
      livePreview: livePreviewModule.livePreview,
      MergeView: mergeModule.MergeView
    };

    isEditorReady = true;
  });

  onDestroy(() => {
    editor?.destroy();
  });

  // Create/update editor when active artifact changes
  $effect(() => {
    // Wait for all dependencies to be ready
    if (!browser || !isEditorReady || !cmModules || !editorContainer || showDiff) return;
    
    // Also check we have artifacts to display
    if (openArtifacts.length === 0 || !activeArtifactId) return;

    const content = currentContent();
    const artifactChanged = activeArtifactId !== currentEditorArtifactId;

    if (!editor) {
      // Create editor for the first time
      const {
        EditorView,
        keymap,
        lineNumbers,
        highlightActiveLine,
        highlightActiveLineGutter,
        EditorState,
        markdown,
        languages,
        oneDark,
        defaultKeymap,
        history,
        historyKeymap,
        livePreview
      } = cmModules;

      // Save command
      const saveKeymap = keymap.of([{
        key: 'Mod-s',
        run: () => {
          handleSave();
          return true;
        }
      }]);

      editor = new EditorView({
        state: EditorState.create({
          doc: content?.content || '',
          extensions: [
            lineNumbers(),
            highlightActiveLine(),
            highlightActiveLineGutter(),
            history(),
            markdown({ codeLanguages: languages }),
            keymap.of([...defaultKeymap, ...historyKeymap]),
            saveKeymap,
            oneDark,
            createSocraticTheme(EditorView),
            livePreview,
            EditorView.lineWrapping,
            EditorView.updateListener.of((update) => {
              if (update.docChanged) {
                hasUnsavedChanges = true;
                isEditing = true;
              }
            })
          ]
        }),
        parent: editorContainer
      });
      
      currentEditorArtifactId = activeArtifactId;
    } else if (artifactChanged) {
      // Tab switched - update editor content for new artifact
      const newValue = content?.content || '';
      editor.dispatch({
        changes: {
          from: 0,
          to: editor.state.doc.length,
          insert: newValue
        }
      });
      hasUnsavedChanges = false;
      isEditing = false;
      currentEditorArtifactId = activeArtifactId;
    } else {
      // Same artifact - only update if no unsaved changes (e.g., version navigation)
      const currentValue = editor.state.doc.toString();
      const newValue = content?.content || '';
      
      if (currentValue !== newValue && !hasUnsavedChanges) {
        editor.dispatch({
          changes: {
            from: 0,
            to: editor.state.doc.length,
            insert: newValue
          }
        });
      }
    }
  });

  // Create diff view when showing pending changes
  $effect(() => {
    if (!browser || !isEditorReady || !cmModules || !diffContainer || !showDiff || !pendingChanges) return;

    const { MergeView, EditorState, oneDark, markdown, languages } = cmModules;

    // Clear previous content
    diffContainer.innerHTML = '';

    new MergeView({
      a: {
        doc: pendingChanges.oldContent,
        extensions: [
          oneDark,
          markdown({ codeLanguages: languages }),
          EditorState.readOnly.of(true)
        ]
      },
      b: {
        doc: pendingChanges.newContent,
        extensions: [
          oneDark,
          markdown({ codeLanguages: languages }),
          EditorState.readOnly.of(true)
        ]
      },
      parent: diffContainer
    });
  });
</script>

<div class="flex h-full flex-col bg-zinc-950">
  {#if openArtifacts.length === 0}
    <!-- Empty state -->
    <div class="flex h-full items-center justify-center text-zinc-600">
      <div class="text-center">
        <p class="text-lg">No files open</p>
        <p class="mt-1 text-sm">Select a file from the explorer to start editing</p>
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
      {#if !isEditorReady}
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
          <div bind:this={diffContainer} class="flex-1 overflow-auto"></div>
        </div>
      {:else}
        <!-- Regular editor -->
        <div bind:this={editorContainer} class="absolute inset-0"></div>
      {/if}
    </div>
  {/if}
</div>

<style>
  /* CodeMirror container styling */
  :global(.cm-editor) {
    height: 100%;
    background-color: #0a0a0a;
  }

  :global(.cm-scroller) {
    font-family: 'JetBrains Mono', 'Fira Code', 'SF Mono', monospace;
  }

  /* Merge view styling */
  :global(.cm-merge-view) {
    height: 100%;
  }

  :global(.cm-merge-view .cm-editor) {
    height: 100%;
  }
</style>
