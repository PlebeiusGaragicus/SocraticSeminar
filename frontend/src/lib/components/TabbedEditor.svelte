<script lang="ts">
  import X from '@lucide/svelte/icons/x';
  import ChevronLeft from '@lucide/svelte/icons/chevron-left';
  import ChevronRight from '@lucide/svelte/icons/chevron-right';
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

  // Use regular variables for container refs with manual trigger
  let editorContainer: HTMLDivElement | null = null;
  let diffContainer: HTMLDivElement | null = null;
  let containerMounted = $state(false);
  
  let editor: EditorView | null = null;
  let isEditorReady = $state(false);
  let currentEditorArtifactId: string | null = null;
  
  // Auto-save debounce timer
  let saveTimeout: ReturnType<typeof setTimeout> | null = null;
  const AUTOSAVE_DELAY = 500; // ms
  
  // Svelte action to set container ref and trigger reactivity
  function setEditorContainer(node: HTMLDivElement) {
    editorContainer = node;
    containerMounted = true;
    
    return {
      destroy() {
        editorContainer = null;
        containerMounted = false;
      }
    };
  }
  
  function setDiffContainer(node: HTMLDivElement) {
    diffContainer = node;
    
    return {
      destroy() {
        diffContainer = null;
      }
    };
  }

  // Store CodeMirror modules after dynamic import (needs to be $state to trigger effect)
  let cmModules = $state<{
    EditorView: typeof import('@codemirror/view').EditorView;
    keymap: typeof import('@codemirror/view').keymap;
    highlightActiveLine: typeof import('@codemirror/view').highlightActiveLine;
    EditorState: typeof import('@codemirror/state').EditorState;
    markdown: typeof import('@codemirror/lang-markdown').markdown;
    languages: typeof import('@codemirror/language-data').languages;
    oneDark: typeof import('@codemirror/theme-one-dark').oneDark;
    defaultKeymap: typeof import('@codemirror/commands').defaultKeymap;
    history: typeof import('@codemirror/commands').history;
    historyKeymap: typeof import('@codemirror/commands').historyKeymap;
    cursorLineUp: typeof import('@codemirror/commands').cursorLineUp;
    cursorLineDown: typeof import('@codemirror/commands').cursorLineDown;
    livePreview: typeof import('$lib/codemirror/livePreview.js').livePreview;
    MergeView: typeof import('@codemirror/merge').MergeView;
  } | null>(null);

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

  // Save function that saves to a specific artifact (to avoid race conditions on tab switch)
  function saveToArtifact(artifactId: string) {
    if (!editor) return;
    
    const artifact = openArtifacts.find(a => a.id === artifactId);
    if (!artifact) return;
    
    const editorContent = editor.state.doc.toString();
    const version = artifact.versions[artifact.currentVersionIndex];
    
    // Only save if content actually changed
    if (version && editorContent !== version.content) {
      artifactStore.updateArtifact(
        artifactId,
        version.title || 'Untitled',
        editorContent
      );
    }
  }
  
  // Auto-save function with debouncing - saves to the current editor's artifact
  function autoSave() {
    if (!currentEditorArtifactId) return;
    saveToArtifact(currentEditorArtifactId);
  }
  
  function scheduleAutoSave() {
    // Clear any pending save
    if (saveTimeout) {
      clearTimeout(saveTimeout);
    }
    // Schedule new save
    saveTimeout = setTimeout(autoSave, AUTOSAVE_DELAY);
  }

  // Custom theme that matches the existing socratic-dark aesthetic
  // Uses a clean sans-serif for markdown, monospace only for code
  function createSocraticTheme(EditorView: typeof import('@codemirror/view').EditorView) {
    return EditorView.theme({
      '&': {
        height: '100%',
        fontSize: '16px',
        fontFamily: "'Inter', 'SF Pro Display', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif"
      },
      '.cm-content': {
        paddingTop: '8px',
        paddingBottom: '16px',
        paddingLeft: '16px',
        paddingRight: '16px',
        caretColor: '#f59e0b'
      },
      '.cm-cursor': {
        borderLeftColor: '#f59e0b',
        borderLeftWidth: '2px'
      },
      '&.cm-focused .cm-cursor': {
        borderLeftColor: '#f59e0b'
      },
      '.cm-activeLine': {
        backgroundColor: '#18181b'
      },
      '&.cm-focused .cm-selectionBackground, .cm-selectionBackground, .cm-content ::selection': {
        backgroundColor: '#f59e0b33'
      },
      '.cm-line': {
        lineHeight: '1.75',
        padding: '0 8px'
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
      highlightActiveLine: viewModule.highlightActiveLine,
      EditorState: stateModule.EditorState,
      markdown: markdownModule.markdown,
      languages: langDataModule.languages,
      oneDark: themeModule.oneDark,
      defaultKeymap: commandsModule.defaultKeymap,
      history: commandsModule.history,
      historyKeymap: commandsModule.historyKeymap,
      cursorLineUp: commandsModule.cursorLineUp,
      cursorLineDown: commandsModule.cursorLineDown,
      livePreview: livePreviewModule.livePreview,
      MergeView: mergeModule.MergeView
    };

    isEditorReady = true;
  });

  onDestroy(() => {
    // Clear any pending auto-save
    if (saveTimeout) {
      clearTimeout(saveTimeout);
      // Save immediately on unmount
      autoSave();
    }
    editor?.destroy();
  });

  // Create/update editor when active artifact changes
  $effect(() => {
    // Wait for all dependencies to be ready
    if (!browser || !isEditorReady || !cmModules || !containerMounted || !editorContainer || showDiff) {
      return;
    }
    
    // Also check we have artifacts to display
    if (openArtifacts.length === 0 || !activeArtifactId) {
      return;
    }

    const content = currentContent();
    const artifactChanged = activeArtifactId !== currentEditorArtifactId;

    if (!editor) {
      // Create editor for the first time
      const {
        EditorView,
        keymap,
        highlightActiveLine,
        EditorState,
        markdown,
        languages,
        oneDark,
        defaultKeymap,
        history,
        historyKeymap,
        cursorLineUp,
        cursorLineDown,
        livePreview
      } = cmModules;

      // Custom commands for logical line movement (bypasses visual line calculation issues)
      const moveToLogicalLineUp = (view: EditorView) => {
        const state = view.state;
        const selection = state.selection.main;
        const currentLine = state.doc.lineAt(selection.head);
        
        if (currentLine.number <= 1) return true; // Already at first line
        
        const prevLine = state.doc.line(currentLine.number - 1);
        const offsetInLine = selection.head - currentLine.from;
        const newPos = Math.min(prevLine.from + offsetInLine, prevLine.to);
        
        view.dispatch({
          selection: { anchor: newPos },
          scrollIntoView: true
        });
        return true;
      };
      
      const moveToLogicalLineDown = (view: EditorView) => {
        const state = view.state;
        const selection = state.selection.main;
        const currentLine = state.doc.lineAt(selection.head);
        
        if (currentLine.number >= state.doc.lines) return true; // Already at last line
        
        const nextLine = state.doc.line(currentLine.number + 1);
        const offsetInLine = selection.head - currentLine.from;
        const newPos = Math.min(nextLine.from + offsetInLine, nextLine.to);
        
        view.dispatch({
          selection: { anchor: newPos },
          scrollIntoView: true
        });
        return true;
      };
      
      // Custom keymap to ensure proper line-by-line navigation
      const lineNavKeymap = [
        { key: 'ArrowUp', run: moveToLogicalLineUp },
        { key: 'ArrowDown', run: moveToLogicalLineDown }
      ];

      editor = new EditorView({
        state: EditorState.create({
          doc: content?.content || '',
          extensions: [
            highlightActiveLine(),
            history(),
            markdown({ codeLanguages: languages }),
            keymap.of([...lineNavKeymap, ...defaultKeymap, ...historyKeymap]),
            oneDark,
            createSocraticTheme(EditorView),
            livePreview,
            EditorView.lineWrapping,
            EditorView.updateListener.of((update) => {
              if (update.docChanged) {
                // Auto-save on any change
                scheduleAutoSave();
              }
            })
          ]
        }),
        parent: editorContainer
      });
      
      currentEditorArtifactId = activeArtifactId;
    } else if (artifactChanged) {
      // Tab switched - save to the OLD artifact first, then switch to new content
      if (saveTimeout) {
        clearTimeout(saveTimeout);
      }
      // Save to the previous artifact (currentEditorArtifactId still holds the old ID)
      if (currentEditorArtifactId) {
        saveToArtifact(currentEditorArtifactId);
      }
      
      // Now load the new artifact's content
      const newValue = content?.content || '';
      editor.dispatch({
        changes: {
          from: 0,
          to: editor.state.doc.length,
          insert: newValue
        }
      });
      // Update to track the new artifact
      currentEditorArtifactId = activeArtifactId;
    } else {
      // Same artifact - update for version navigation
      const currentValue = editor.state.doc.toString();
      const newValue = content?.content || '';
      
      if (currentValue !== newValue) {
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
          <div use:setDiffContainer class="flex-1 overflow-auto"></div>
        </div>
      {:else}
        <!-- Regular editor -->
        <div use:setEditorContainer class="absolute inset-0 bg-zinc-950"></div>
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
    font-family: 'Inter', 'SF Pro Display', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
  }
  
  /* Monospace font only for code elements */
  :global(.cm-editor .cm-inline-code),
  :global(.cm-editor .cm-codeblock-line) {
    font-family: 'JetBrains Mono', 'Fira Code', 'SF Mono', ui-monospace, monospace !important;
    font-size: 0.9em;
  }

  /* Merge view styling */
  :global(.cm-merge-view) {
    height: 100%;
  }

  :global(.cm-merge-view .cm-editor) {
    height: 100%;
  }
</style>
