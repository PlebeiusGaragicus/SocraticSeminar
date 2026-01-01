<script lang="ts">
  import X from '@lucide/svelte/icons/x';
  import ChevronLeft from '@lucide/svelte/icons/chevron-left';
  import ChevronRight from '@lucide/svelte/icons/chevron-right';
  import Globe from '@lucide/svelte/icons/globe';
  import Plus from '@lucide/svelte/icons/plus';
  import FilePlus from '@lucide/svelte/icons/file-plus';
  import MessageSquarePlus from '@lucide/svelte/icons/message-square-plus';
  import Globe2 from '@lucide/svelte/icons/globe-2';
  import Search from '@lucide/svelte/icons/search';
  import Command from '@lucide/svelte/icons/command';
  import ExternalLink from '@lucide/svelte/icons/external-link';
  import PanelRightOpen from '@lucide/svelte/icons/panel-right-open';
  import PanelRightClose from '@lucide/svelte/icons/panel-right-close';
  import { artifactStore, threadStore, workspaceStore, projectStore, sourceStore, agentStore } from '$lib/stores/index.js';
  import type { TabItem, Artifact, Thread, Source } from '$lib/stores/types.js';
  import { getFileIcon } from '$lib/icons.js';
  import { cn } from '$lib/utils.js';
  import { onMount, onDestroy } from 'svelte';
  import { browser } from '$app/environment';
  import ChatPanel from './ChatPanel.svelte';
  import NewFileModal from './NewFileModal.svelte';
  import NewSourcesModal from './NewSourcesModal.svelte';
  import { Button } from './ui/index.js';
  import MessageCircle from '@lucide/svelte/icons/message-circle';

  // CodeMirror imports (dynamically loaded on client)
  type EditorView = import('@codemirror/view').EditorView;

  interface Props {
    column: 'left' | 'right';
    tabs: TabItem[];
    activeTabId: string | null;
    onTabSelect: (id: string) => void;
    onTabClose: (id: string) => void;
    showClosePanel?: boolean;
    onClosePanel?: () => void;
  }

  let {
    column,
    tabs,
    activeTabId,
    onTabSelect,
    onTabClose,
    showClosePanel = false,
    onClosePanel
  }: Props = $props();

  // Panel state for Editor
  let editorContainer: HTMLDivElement | null = null;
  let diffContainer: HTMLDivElement | null = null;
  let containerMounted = $state(false);
  let editor: EditorView | null = null;
  let isEditorReady = $state(false);
  let currentEditorArtifactId = $state<string | null>(null);
  
  // Per-tab autosave timers
  const saveTimeouts = new Map<string, ReturnType<typeof setTimeout>>();
  const AUTOSAVE_DELAY = 2000;
  
  let cmModules = $state<any>(null);

  const activeTab = $derived(tabs.find(t => t.id === activeTabId) ?? null);
  
  // Artifact specific derivations
  const activeArtifact = $derived(
    activeTab?.type === 'artifact' ? artifactStore.artifacts.find(a => a.id === activeTabId) : null
  );
  const currentContent = $derived(() => {
    if (!activeArtifact) return null;
    return activeArtifact.versions[activeArtifact.currentVersionIndex] ?? null;
  });
  const canGoPrev = $derived(activeArtifact && activeArtifact.currentVersionIndex > 0);
  const canGoNext = $derived(activeArtifact && activeArtifact.currentVersionIndex < activeArtifact.versions.length - 1);
  const pendingChanges = $derived(artifactStore.pendingChanges);
  const showDiff = $derived(pendingChanges && pendingChanges.artifactId === activeTabId);

  // Thread specific derivations
  const activeThread = $derived(
    activeTab?.type === 'thread' ? threadStore.threads.find(t => t.id === activeTabId) : null
  );

  // Source specific derivations
  const activeSource = $derived(
    activeTab?.type === 'source' ? sourceStore.sources.find(s => s.id === activeTabId) : null
  );

  const clientToolInterrupt = $derived(agentStore.clientToolInterrupt);

  const STATUS_COLORS = {
    idle: "bg-green-500",
    busy: "bg-blue-500",
    interrupted: "bg-orange-500",
    error: "bg-red-600",
  };

  function setEditorContainer(node: HTMLDivElement) {
    editorContainer = node;
    containerMounted = true;
    return {
      destroy() {
        if (editor) {
          if (currentEditorArtifactId) {
            saveToArtifact(currentEditorArtifactId, true);
          }
          editor.destroy();
          editor = null;
          currentEditorArtifactId = null;
        }
        editorContainer = null;
        containerMounted = false;
      }
    };
  }

  function setDiffContainer(node: HTMLDivElement) {
    diffContainer = node;
    return { destroy() { diffContainer = null; } };
  }

  function handlePrevVersion() {
    if (!activeArtifact || !canGoPrev) return;
    const targetIndex = activeArtifact.currentVersionIndex - 1;
    if (currentEditorArtifactId) {
      saveToArtifact(currentEditorArtifactId, true);
    }
    artifactStore.setArtifactVersion(activeArtifact.id, targetIndex);
  }

  function handleNextVersion() {
    if (!activeArtifact || !canGoNext) return;
    const targetIndex = activeArtifact.currentVersionIndex + 1;
    if (currentEditorArtifactId) {
      saveToArtifact(currentEditorArtifactId, true);
    }
    artifactStore.setArtifactVersion(activeArtifact.id, targetIndex);
  }

  function saveToArtifact(artifactId: string, createNewVersion: boolean = false) {
    if (!editor) return;
    const artifact = artifactStore.artifacts.find(a => a.id === artifactId);
    if (!artifact) return;
    
    // Normalize content comparison to avoid redundant saves from whitespace/line-endings
    const editorContent = editor.state.doc.toString().trim();
    const version = artifact.versions[artifact.currentVersionIndex];
    const versionContent = (version?.content || '').trim();
    
    if (version && editorContent !== versionContent) {
      artifactStore.updateArtifact(artifactId, version.title || 'Untitled', editor.state.doc.toString(), createNewVersion);
    }

    // Clear the timeout for this artifact as we've just saved it
    const timeout = saveTimeouts.get(artifactId);
    if (timeout) {
      clearTimeout(timeout);
      saveTimeouts.delete(artifactId);
    }
  }

  function scheduleAutoSave(artifactId: string) {
    const existing = saveTimeouts.get(artifactId);
    if (existing) clearTimeout(existing);
    
    const timeout = setTimeout(() => {
      // For autosave while typing, we update the current version in place
      // to avoid creating hundreds of versions.
      saveToArtifact(artifactId, false);
    }, AUTOSAVE_DELAY);
    
    saveTimeouts.set(artifactId, timeout);
  }

  function createSocraticTheme(EditorView: any) {
    return EditorView.theme({
      '&': { height: '100%', fontSize: '16px', fontFamily: "'Inter', sans-serif" },
      '.cm-content': { paddingTop: '8px', paddingBottom: '16px', paddingLeft: '16px', paddingRight: '16px', caretColor: '#f59e0b' },
      '.cm-cursor': { borderLeftColor: '#f59e0b', borderLeftWidth: '2px' },
      '.cm-activeLine': { backgroundColor: '#18181b' },
      '.cm-line': { lineHeight: '1.75', padding: '0 8px' },
      '.cm-scroller': { overflow: 'auto' }
    }, { dark: true });
  }

  onMount(async () => {
    if (!browser) return;
    const [view, state, markdown, langData, theme, commands, livePreview, merge] = await Promise.all([
      import('@codemirror/view'), import('@codemirror/state'), import('@codemirror/lang-markdown'),
      import('@codemirror/language-data'), import('@codemirror/theme-one-dark'), import('@codemirror/commands'),
      import('$lib/codemirror/livePreview.js'), import('@codemirror/merge')
    ]);
    cmModules = {
      EditorView: view.EditorView, keymap: view.keymap, highlightActiveLine: view.highlightActiveLine,
      EditorState: state.EditorState, markdown: markdown.markdown, languages: langData.languages,
      oneDark: theme.oneDark, defaultKeymap: commands.defaultKeymap, history: commands.history,
      historyKeymap: commands.historyKeymap, cursorLineUp: commands.cursorLineUp,
      cursorLineDown: commands.cursorLineDown, livePreview: livePreview.livePreview, MergeView: merge.MergeView
    };
    isEditorReady = true;
  });

  onDestroy(() => {
    saveTimeouts.forEach((timeout, id) => {
      clearTimeout(timeout);
      saveToArtifact(id, true);
    });
    saveTimeouts.clear();
    editor?.destroy();
  });

  $effect(() => {
    if (!browser || !isEditorReady || !cmModules || !containerMounted || !editorContainer) return;

    const isShowingArtifact = activeTab?.type === 'artifact' && !showDiff;
    const artifactId = activeTabId;
    
    // 1. Handle artifact switch or panel closing (Saving)
    const idToSave = currentEditorArtifactId;
    if (idToSave && (!isShowingArtifact || artifactId !== idToSave)) {
      // Save as a new version when switching away or closing
      saveToArtifact(idToSave, true);
      currentEditorArtifactId = null;
    }

    if (!isShowingArtifact) return;

    // 2. Initialize or Update Editor
    const content = currentContent();
    const newValue = content?.content || '';

    if (!editor) {
      const { EditorView, keymap, highlightActiveLine, EditorState, markdown, languages, oneDark, defaultKeymap, history, historyKeymap, livePreview } = cmModules;
      editor = new EditorView({
        state: EditorState.create({
          doc: newValue,
          extensions: [
            highlightActiveLine(), history(), markdown({ codeLanguages: languages }),
            keymap.of([...defaultKeymap, ...historyKeymap]), oneDark,
            createSocraticTheme(EditorView), livePreview, EditorView.lineWrapping,
            EditorView.updateListener.of((update: any) => { 
              if (update.docChanged && currentEditorArtifactId) {
                scheduleAutoSave(currentEditorArtifactId); 
              } 
            }),
            EditorView.domEventHandlers({
              blur: () => {
                // Only trigger a save on blur if there are actually pending changes
                // This prevents redundant versions when just clicking around or navigating
                if (currentEditorArtifactId && saveTimeouts.has(currentEditorArtifactId)) {
                  saveToArtifact(currentEditorArtifactId, true);
                }
              }
            })
          ]
        }),
        parent: editorContainer
      });
      currentEditorArtifactId = artifactId;
    } else if (artifactId !== currentEditorArtifactId) {
      // Switched to a new artifact (already saved old one above)
      editor.dispatch({ changes: { from: 0, to: editor.state.doc.length, insert: newValue } });
      currentEditorArtifactId = artifactId;
    } else {
      // Same artifact, might be a version change or external update
      const currentValue = editor.state.doc.toString();
      
      // Use the same normalization as saveToArtifact for comparison
      const normalizedCurrent = currentValue.trim();
      const normalizedNew = newValue.trim();

      if (normalizedCurrent !== normalizedNew) {
        // If we have unsaved local changes (pending autosave), 
        // we must commit them before accepting the external update.
        // This prevents the "reversion" bug where user typing is lost
        // when an agent update or external state change occurs.
        const activeId = currentEditorArtifactId;
        if (activeId && saveTimeouts.has(activeId)) {
          saveToArtifact(activeId, true);
          // The next effect cycle will handle syncing with the updated store
          return;
        }

        // Only overwrite if the content is actually different, 
        // not just whitespace or if the user is currently typing
        if (!saveTimeouts.has(artifactId as string)) {
          editor.dispatch({ changes: { from: 0, to: editor.state.doc.length, insert: newValue } });
        }
      }
    }
  });

  $effect(() => {
    if (!browser || !isEditorReady || !cmModules || !diffContainer || !showDiff || !pendingChanges) return;
    const { MergeView, EditorState, oneDark, markdown, languages } = cmModules;
    diffContainer.innerHTML = '';
    new MergeView({
      a: { doc: pendingChanges.oldContent, extensions: [oneDark, markdown({ codeLanguages: languages }), EditorState.readOnly.of(true)] },
      b: { doc: pendingChanges.newContent, extensions: [oneDark, markdown({ codeLanguages: languages }), EditorState.readOnly.of(true)] },
      parent: diffContainer
    });
  });

  function getTabTitle(tab: TabItem) {
    if (tab.type === 'artifact') {
      const art = artifactStore.artifacts.find(a => a.id === tab.id);
      return art?.versions[art.currentVersionIndex]?.title || 'Untitled';
    } else if (tab.type === 'thread') {
      const thread = threadStore.threads.find(t => t.id === tab.id);
      return thread?.title || 'Untitled Thread';
    } else {
      const source = sourceStore.sources.find(s => s.id === tab.id);
      return source?.title || 'Untitled Source';
    }
  }

  function getTabIcon(tab: TabItem) {
    if (tab.type === 'artifact') {
      return getFileIcon(getTabTitle(tab));
    } else if (tab.type === 'thread') {
      return MessageCircle;
    } else {
      return Globe;
    }
  }

  function getArtifact(id: string) {
    return artifactStore.artifacts.find(a => a.id === id);
  }

  function getThread(id: string) {
    return threadStore.threads.find(t => t.id === id);
  }

  function getSource(id: string) {
    return sourceStore.sources.find(s => s.id === id);
  }

  let showNewMenu = $state(false);
  let showNewFileModal = $state(false);
  let showNewSourcesModal = $state(false);

  function handleCreateFile() {
    showNewFileModal = true;
    showNewMenu = false;
  }

  function handleCreateThread() {
    workspaceStore.createNewThread(column);
    showNewMenu = false;
  }

  function handleAddSources() {
    showNewSourcesModal = true;
    showNewMenu = false;
  }

  let searchTerm = $state('');
  let isSearching = $state(false);

  const searchResults = $derived.by(() => {
    const term = searchTerm.toLowerCase().trim();
    const projectId = projectStore.currentProjectId || '';
    
    const projectFiles = artifactStore.getProjectArtifacts(projectId);
    const projectThreads = threadStore.getProjectThreads(projectId);
    const projectSources = sourceStore.getProjectSources(projectId);
    
    const filteredFiles = projectFiles.filter(f => {
      const title = f.versions[f.currentVersionIndex]?.title?.toLowerCase() || '';
      return title.includes(term);
    }).map(f => ({ 
      id: f.id, 
      type: 'artifact' as const, 
      title: f.versions[f.currentVersionIndex]?.title || 'Untitled',
      icon: getFileIcon(f.versions[f.currentVersionIndex]?.title || '')
    }));
    
    const filteredThreads = projectThreads.filter(t => {
      return t.title.toLowerCase().includes(term);
    }).map(t => ({ 
      id: t.id, 
      type: 'thread' as const, 
      title: t.title,
      icon: MessageCircle
    }));

    const filteredSources = projectSources.filter(s => {
      return s.title.toLowerCase().includes(term) || s.url.toLowerCase().includes(term);
    }).map(s => ({
      id: s.id,
      type: 'source' as const,
      title: s.title,
      icon: Globe
    }));
    
    return [...filteredFiles, ...filteredThreads, ...filteredSources];
  });

  function handleOpenItem(id: string, type: 'artifact' | 'thread' | 'source') {
    workspaceStore.openItem(id, type, column);
    showNewMenu = false;
    isSearching = false;
    searchTerm = '';
  }

  function toggleSearch() {
    isSearching = !isSearching;
    if (isSearching) {
      searchTerm = '';
    }
  }

  // Drag and drop state
  let isDraggingOver = $state(false);
  let isDraggingRightEdge = $state(false);

  function handleDragStart(e: DragEvent, tabId: string, tabType: string) {
    if (tabType === 'artifact' && tabId === currentEditorArtifactId) {
      saveToArtifact(tabId, true);
    }
    
    if (e.dataTransfer) {
      e.dataTransfer.setData('application/svelte-tab-id', tabId);
      e.dataTransfer.setData('application/svelte-tab-type', tabType);
      e.dataTransfer.setData('application/svelte-tab-source-column', column);
      // Set drag image or ghost effect
      e.dataTransfer.effectAllowed = 'move';
    }
  }

  function handleDrop(e: DragEvent) {
    e.preventDefault();
    const wasDraggingRightEdge = isDraggingRightEdge;
    isDraggingOver = false;
    isDraggingRightEdge = false;
    
    const id = e.dataTransfer?.getData('application/svelte-tab-id');
    const type = e.dataTransfer?.getData('application/svelte-tab-type');
    const sourceColumn = e.dataTransfer?.getData('application/svelte-tab-source-column');

    if (!id || !type) return;

    // Determine target column
    let targetColumn: 'left' | 'right' = column;
    if (column === 'left' && workspaceStore.rightPanelCollapsed && wasDraggingRightEdge) {
      targetColumn = 'right';
    }

    if (sourceColumn && (sourceColumn === 'left' || sourceColumn === 'right')) {
      if (sourceColumn !== targetColumn) {
        workspaceStore.moveTab(id, sourceColumn as 'left' | 'right', targetColumn);
      }
    } else {
      // Sidebar drag or unknown source
      workspaceStore.openItem(id, type as any, targetColumn);
    }
  }

  function handleDragOver(e: DragEvent) {
    e.preventDefault();
    if (e.dataTransfer) {
      e.dataTransfer.dropEffect = 'move';
    }
    isDraggingOver = true;

    if (column === 'left' && workspaceStore.rightPanelCollapsed) {
      const rect = (e.currentTarget as HTMLElement).getBoundingClientRect();
      const x = e.clientX - rect.left;
      isDraggingRightEdge = x > rect.width * 0.8; // Right 20%
    } else {
      isDraggingRightEdge = false;
    }
  }

  function handleDragLeave() {
    isDraggingOver = false;
    isDraggingRightEdge = false;
  }
</script>

<div 
  class="flex h-full flex-col bg-zinc-950 relative"
  role="region"
  aria-label="Tabbed workspace panel"
  ondragover={handleDragOver}
  ondragleave={handleDragLeave}
  ondrop={handleDrop}
>
  <!-- Drag over overlay -->
  {#if isDraggingOver}
    <div class={cn(
      "absolute inset-0 z-50 pointer-events-none border-2 border-amber-500/30 transition-all",
      isDraggingRightEdge ? "bg-gradient-to-l from-amber-500/10 to-transparent border-r-4 border-r-amber-500/50" : "bg-amber-500/5"
    )}>
      {#if isDraggingRightEdge}
        <div class="absolute right-4 top-1/2 -translate-y-1/2 rounded bg-amber-500 px-2 py-1 text-[10px] font-bold text-black uppercase tracking-wider shadow-lg">
          Split Right
        </div>
      {/if}
    </div>
  {/if}

  {#if showNewMenu}
    <div 
      class="fixed inset-0 z-40" 
      onclick={() => { showNewMenu = false; isSearching = false; }}
      onkeydown={(e) => e.key === 'Escape' && (showNewMenu = false)}
      role="presentation"
    ></div>
    <div class="absolute left-10 top-10 z-50 w-64 rounded-lg border border-zinc-800 bg-zinc-900 p-1 shadow-xl">
      {#if !isSearching}
        <button
          onclick={handleCreateFile}
          class="flex w-full items-center gap-2 rounded px-3 py-2 text-sm text-zinc-300 hover:bg-zinc-800"
        >
          <FilePlus class="h-4 w-4" />
          New File
        </button>
        <button
          onclick={handleCreateThread}
          class="flex w-full items-center gap-2 rounded px-3 py-2 text-sm text-zinc-300 hover:bg-zinc-800"
        >
          <MessageSquarePlus class="h-4 w-4" />
          New Chat
        </button>
        <button
          onclick={handleAddSources}
          class="flex w-full items-center gap-2 rounded px-3 py-2 text-sm text-zinc-300 hover:bg-zinc-800"
        >
          <Globe2 class="h-4 w-4" />
          Add Sources
        </button>
        <div class="my-1 border-t border-zinc-800"></div>
        <button
          onclick={toggleSearch}
          class="flex w-full items-center justify-between rounded px-3 py-2 text-sm text-zinc-300 hover:bg-zinc-800"
        >
          <div class="flex items-center gap-2">
            <Search class="h-4 w-4" />
            Open...
          </div>
          <Command class="h-3 w-3 opacity-50" />
        </button>
      {:else}
        <div class="p-2">
          <div class="relative">
            <Search class="absolute left-2 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-zinc-500" />
            <input
              type="text"
              bind:value={searchTerm}
              placeholder="Search files & chats..."
              class="w-full rounded bg-zinc-800 py-1.5 pl-8 pr-3 text-xs text-zinc-200 outline-none focus:ring-1 focus:ring-amber-500/50"
              autofocus
            />
          </div>
        </div>
        <div class="max-h-[300px] overflow-y-auto py-1">
          {#each searchResults as result}
            <button
              onclick={() => handleOpenItem(result.id, result.type)}
              class="flex w-full items-center gap-2 px-3 py-2 text-left text-sm text-zinc-400 hover:bg-zinc-800 hover:text-zinc-200"
            >
              <result.icon class="h-3.5 w-3.5 flex-shrink-0" />
              <span class="truncate">{result.title}</span>
            </button>
          {:else}
            <div class="px-3 py-4 text-center text-xs text-zinc-600">
              No results found
            </div>
          {/each}
        </div>
      {/if}
    </div>
  {/if}

  <div class="flex items-center border-b border-zinc-800 bg-zinc-900/50">
    <div class="flex flex-1 overflow-x-auto">
      {#each tabs as tab (tab.id)}
        {@const isActive = tab.id === activeTabId}
        {@const title = getTabTitle(tab)}
        {@const Icon = getTabIcon(tab)}
        {@const art = tab.type === 'artifact' ? getArtifact(tab.id) : null}
        {@const thread = tab.type === 'thread' ? getThread(tab.id) : null}
        {@const source = tab.type === 'source' ? getSource(tab.id) : null}
        {@const isUnviewed = (art && !art.viewed) || (thread && !thread.viewed) || (source && !source.viewed)}
        
        <div
          class={cn(
            "group flex items-center gap-2 border-r border-zinc-800 px-3 py-2 text-sm transition-colors cursor-pointer min-w-[100px]",
            isActive
              ? "bg-zinc-950 text-zinc-100"
              : "bg-zinc-900 text-zinc-400 hover:bg-zinc-800 hover:text-zinc-300"
          )}
          onclick={() => onTabSelect(tab.id)}
          onkeydown={(e) => e.key === 'Enter' && onTabSelect(tab.id)}
          draggable="true"
          ondragstart={(e) => handleDragStart(e, tab.id, tab.type)}
          role="tab"
          tabindex="0"
        >
          {#if isUnviewed}
            <span class="size-1.5 flex-shrink-0 rounded-full bg-blue-500"></span>
          {/if}
          {#if thread}
            <span class={cn("size-2 flex-shrink-0 rounded-full", STATUS_COLORS[thread.status])}></span>
          {/if}
          <Icon class={cn(
            "h-3.5 w-3.5 flex-shrink-0",
            isActive ? "text-zinc-100" : (isUnviewed ? "text-blue-500" : "text-zinc-500")
          )} />
          <span class="max-w-[120px] truncate">{title}</span>
          <button
            onclick={(e) => { e.stopPropagation(); onTabClose(tab.id); }}
            class="rounded p-0.5 text-zinc-500 opacity-0 transition-all hover:bg-zinc-700 hover:text-zinc-300 group-hover:opacity-100 {isActive ? 'opacity-100' : ''}"
          >
            <X class="h-3.5 w-3.5" />
          </button>
        </div>
      {/each}

      <button
        onclick={() => showNewMenu = !showNewMenu}
        class="flex items-center justify-center px-3 py-2 text-zinc-500 hover:text-zinc-300 hover:bg-zinc-800 transition-colors border-r border-zinc-800"
        title="New tab"
      >
        <Plus class="h-4 w-4" />
      </button>
    </div>

    {#if activeArtifact}
      <div class="flex items-center gap-2 px-3 border-r border-zinc-800 h-full">
        <button onclick={handlePrevVersion} disabled={!canGoPrev} class="rounded p-1 text-zinc-500 hover:bg-zinc-800 disabled:opacity-30">
          <ChevronLeft class="h-4 w-4" />
        </button>
        <span class="text-xs text-zinc-500">v{activeArtifact.currentVersionIndex + 1}/{activeArtifact.versions.length}</span>
        <button onclick={handleNextVersion} disabled={!canGoNext} class="rounded p-1 text-zinc-500 hover:bg-zinc-800 disabled:opacity-30">
          <ChevronRight class="h-4 w-4" />
        </button>
      </div>
    {/if}

    {#if column === 'left' && workspaceStore.rightPanelCollapsed}
      <button
        onclick={() => workspaceStore.toggleRightPanel()}
        class="px-3 py-2 text-zinc-500 hover:text-zinc-300 hover:bg-zinc-800 transition-colors border-l border-zinc-800 h-full"
        title="Open right panel"
      >
        <PanelRightOpen class="h-4 w-4" />
      </button>
    {/if}

    {#if showClosePanel}
      <button
        onclick={onClosePanel}
        class="px-3 py-2 text-zinc-500 hover:text-zinc-300 hover:bg-zinc-800 transition-colors border-l border-zinc-800 h-full"
        title="Close panel and move tabs to left"
      >
        <PanelRightClose class="h-4 w-4" />
      </button>
    {/if}
  </div>

  <div class="relative flex-1 overflow-hidden">
    {#if tabs.length === 0}
      <div class="flex h-full items-center justify-center text-zinc-600">
        <div class="text-center">
          <p class="text-lg">No tabs open</p>
          <p class="mt-1 text-sm">Select an item from the sidebar</p>
        </div>
      </div>
    {:else if activeTab?.type === 'thread'}
      <div class="absolute inset-0">
        <ChatPanel threadId={activeTabId} />
      </div>
    {:else if activeTab?.type === 'source'}
      <div class="absolute inset-0 flex flex-col bg-zinc-950 overflow-hidden">
        {#if activeSource}
          <div class="flex items-center justify-between border-b border-zinc-800 bg-zinc-900/30 px-4 py-2">
            <div class="flex items-center gap-2 min-w-0">
              <Globe class="h-4 w-4 text-blue-500" />
              <span class="text-sm font-medium text-zinc-300 truncate">{activeSource.title}</span>
            </div>
            <a 
              href={activeSource.url} 
              target="_blank" 
              rel="noopener noreferrer"
              class="flex items-center gap-1.5 rounded-md bg-zinc-800 px-2.5 py-1 text-xs font-medium text-zinc-400 hover:bg-zinc-700 hover:text-zinc-200 transition-colors"
            >
              <span>View Original</span>
              <ExternalLink class="h-3 w-3" />
            </a>
          </div>
          <div class="flex-1 overflow-y-auto p-8 prose prose-invert max-w-none prose-pre:bg-zinc-900 prose-pre:border prose-pre:border-zinc-800">
            <!-- Simple markdown-like rendering for source content -->
            <div class="text-zinc-300 leading-relaxed whitespace-pre-wrap font-sans">
              {activeSource.content}
            </div>
          </div>
        {/if}
      </div>
    {:else if activeTab?.type === 'artifact'}
      {#if !isEditorReady}
        <div class="absolute inset-0 flex items-center justify-center text-zinc-500">
          <div class="text-center">
            <div class="mb-2 h-6 w-6 animate-spin rounded-full border-2 border-zinc-600 border-t-amber-500 mx-auto"></div>
            <p class="text-sm">Loading editor...</p>
          </div>
        </div>
      {:else if showDiff}
        <div class="absolute inset-0 flex flex-col">
          <div class="flex items-center justify-between border-b border-amber-500/30 bg-amber-500/10 px-4 py-2">
            <span class="text-sm font-medium text-amber-400">Agent proposed changes</span>
            <div class="flex gap-2">
              <Button 
                variant="ghost" 
                size="sm" 
                onclick={() => {
                  if (clientToolInterrupt) {
                    agentStore.rejectClientToolInterrupt();
                  } else {
                    artifactStore.rejectPendingChanges();
                  }
                }}
              >Reject</Button>
              <Button 
                size="sm" 
                class="bg-amber-600" 
                onclick={() => {
                  if (clientToolInterrupt) {
                    agentStore.executeApprovedWriteTools();
                  } else {
                    artifactStore.acceptPendingChanges();
                  }
                }}
              >Accept</Button>
            </div>
          </div>
          <div use:setDiffContainer class="flex-1 overflow-auto"></div>
        </div>
      {:else}
        <div use:setEditorContainer class="absolute inset-0 bg-zinc-950"></div>
      {/if}
    {/if}
  </div>
</div>

{#if showNewFileModal}
  <NewFileModal {column} onClose={() => (showNewFileModal = false)} />
{/if}

{#if showNewSourcesModal}
  <NewSourcesModal {column} onClose={() => (showNewSourcesModal = false)} />
{/if}

<style>
  :global(.cm-editor) { height: 100%; background-color: #0a0a0a; }
  :global(.cm-scroller) { font-family: 'Inter', sans-serif; }
  :global(.cm-merge-view) { height: 100%; }
</style>

