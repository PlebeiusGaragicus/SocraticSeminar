<script lang="ts">
  import X from '@lucide/svelte/icons/x';
  import ChevronLeft from '@lucide/svelte/icons/chevron-left';
  import ChevronRight from '@lucide/svelte/icons/chevron-right';
  import Plus from '@lucide/svelte/icons/plus';
  import FilePlus from '@lucide/svelte/icons/file-plus';
  import MessageSquarePlus from '@lucide/svelte/icons/message-square-plus';
  import PanelRightOpen from '@lucide/svelte/icons/panel-right-open';
  import PanelRightClose from '@lucide/svelte/icons/panel-right-close';
  import { artifactStore, threadStore, workspaceStore } from '$lib/stores/index.js';
  import type { TabItem, Artifact, Thread } from '$lib/stores/types.js';
  import { getFileIcon } from '$lib/icons.js';
  import { cn } from '$lib/utils.js';
  import { onMount, onDestroy } from 'svelte';
  import { browser } from '$app/environment';
  import ChatPanel from './ChatPanel.svelte';
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
  let currentEditorArtifactId: string | null = null;
  let saveTimeout: ReturnType<typeof setTimeout> | null = null;
  const AUTOSAVE_DELAY = 500;
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
          if (saveTimeout) { clearTimeout(saveTimeout); saveTimeout = null; }
          if (currentEditorArtifactId) saveToArtifact(currentEditorArtifactId);
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
    artifactStore.setArtifactVersion(activeArtifact.id, activeArtifact.currentVersionIndex - 1);
  }

  function handleNextVersion() {
    if (!activeArtifact || !canGoNext) return;
    artifactStore.setArtifactVersion(activeArtifact.id, activeArtifact.currentVersionIndex + 1);
  }

  function saveToArtifact(artifactId: string) {
    if (!editor) return;
    const artifact = artifactStore.artifacts.find(a => a.id === artifactId);
    if (!artifact) return;
    const editorContent = editor.state.doc.toString();
    const version = artifact.versions[artifact.currentVersionIndex];
    if (version && editorContent !== version.content) {
      artifactStore.updateArtifact(artifactId, version.title || 'Untitled', editorContent);
    }
  }

  function scheduleAutoSave() {
    if (saveTimeout) clearTimeout(saveTimeout);
    saveTimeout = setTimeout(() => {
      if (currentEditorArtifactId) saveToArtifact(currentEditorArtifactId);
    }, AUTOSAVE_DELAY);
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
    if (saveTimeout) { clearTimeout(saveTimeout); if (currentEditorArtifactId) saveToArtifact(currentEditorArtifactId); }
    editor?.destroy();
  });

  $effect(() => {
    if (!browser || !isEditorReady || !cmModules || !containerMounted || !editorContainer || showDiff || activeTab?.type !== 'artifact') return;
    const content = currentContent();
    const artifactChanged = activeTabId !== currentEditorArtifactId;
    if (!editor) {
      const { EditorView, keymap, highlightActiveLine, EditorState, markdown, languages, oneDark, defaultKeymap, history, historyKeymap, livePreview } = cmModules;
      editor = new EditorView({
        state: EditorState.create({
          doc: content?.content || '',
          extensions: [
            highlightActiveLine(), history(), markdown({ codeLanguages: languages }),
            keymap.of([...defaultKeymap, ...historyKeymap]), oneDark,
            createSocraticTheme(EditorView), livePreview, EditorView.lineWrapping,
            EditorView.updateListener.of((update: any) => { if (update.docChanged) scheduleAutoSave(); })
          ]
        }),
        parent: editorContainer
      });
      currentEditorArtifactId = activeTabId;
    } else if (artifactChanged) {
      if (saveTimeout) clearTimeout(saveTimeout);
      if (currentEditorArtifactId) saveToArtifact(currentEditorArtifactId);
      editor.dispatch({ changes: { from: 0, to: editor.state.doc.length, insert: content?.content || '' } });
      currentEditorArtifactId = activeTabId;
    } else {
      const currentValue = editor.state.doc.toString();
      const newValue = content?.content || '';
      if (currentValue !== newValue) {
        editor.dispatch({ changes: { from: 0, to: editor.state.doc.length, insert: newValue } });
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
    } else {
      const thread = threadStore.threads.find(t => t.id === tab.id);
      return thread?.title || 'Untitled Thread';
    }
  }

  function getTabIcon(tab: TabItem) {
    if (tab.type === 'artifact') {
      return getFileIcon(getTabTitle(tab));
    } else {
      return MessageCircle;
    }
  }

  function getArtifact(id: string) {
    return artifactStore.artifacts.find(a => a.id === id);
  }

  function getThread(id: string) {
    return threadStore.threads.find(t => t.id === id);
  }

  let showNewMenu = $state(false);

  function handleCreateFile() {
    workspaceStore.createNewFile(column);
    showNewMenu = false;
  }

  function handleCreateThread() {
    workspaceStore.createNewThread(column);
    showNewMenu = false;
  }
</script>

<div class="flex h-full flex-col bg-zinc-950 relative">
  {#if showNewMenu}
    <div 
      class="fixed inset-0 z-40" 
      onclick={() => showNewMenu = false}
      onkeydown={(e) => e.key === 'Escape' && (showNewMenu = false)}
      role="presentation"
    ></div>
    <div class="absolute left-10 top-10 z-50 w-48 rounded-lg border border-zinc-800 bg-zinc-900 p-1 shadow-xl">
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
    </div>
  {/if}

  {#if tabs.length === 0}
    <div class="flex h-full items-center justify-center text-zinc-600">
      <div class="text-center">
        <p class="text-lg">No tabs open</p>
        <p class="mt-1 text-sm">Select an item from the sidebar</p>
      </div>
    </div>
  {:else}
    <div class="flex items-center border-b border-zinc-800 bg-zinc-900/50">
      <div class="flex flex-1 overflow-x-auto">
        {#each tabs as tab (tab.id)}
          {@const isActive = tab.id === activeTabId}
          {@const title = getTabTitle(tab)}
          {@const Icon = getTabIcon(tab)}
          {@const art = tab.type === 'artifact' ? getArtifact(tab.id) : null}
          {@const thread = tab.type === 'thread' ? getThread(tab.id) : null}
          {@const isUnviewed = (art && !art.viewed) || (thread && !thread.viewed)}
          
          <div
            class={cn(
              "group flex items-center gap-2 border-r border-zinc-800 px-3 py-2 text-sm transition-colors cursor-pointer min-w-[100px]",
              isActive
                ? "bg-zinc-950 text-zinc-100"
                : "bg-zinc-900 text-zinc-400 hover:bg-zinc-800 hover:text-zinc-300"
            )}
            onclick={() => onTabSelect(tab.id)}
            onkeydown={(e) => e.key === 'Enter' && onTabSelect(tab.id)}
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
      {#if activeTab?.type === 'thread'}
        <div class="absolute inset-0">
          <ChatPanel threadId={activeTabId} />
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
                <Button variant="ghost" size="sm" onclick={() => artifactStore.rejectPendingChanges()}>Reject</Button>
                <Button size="sm" class="bg-amber-600" onclick={() => artifactStore.acceptPendingChanges()}>Accept</Button>
              </div>
            </div>
            <div use:setDiffContainer class="flex-1 overflow-auto"></div>
          </div>
        {:else}
          <div use:setEditorContainer class="absolute inset-0 bg-zinc-950"></div>
        {/if}
      {/if}
    </div>
  {/if}
</div>

<style>
  :global(.cm-editor) { height: 100%; background-color: #0a0a0a; }
  :global(.cm-scroller) { font-family: 'Inter', sans-serif; }
  :global(.cm-merge-view) { height: 100%; }
</style>

