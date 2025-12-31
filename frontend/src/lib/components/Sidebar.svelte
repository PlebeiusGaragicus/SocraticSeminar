<script lang="ts">
  import MessageCircle from '@lucide/svelte/icons/message-circle';
  import Plus from '@lucide/svelte/icons/plus';
  import Trash2 from '@lucide/svelte/icons/trash-2';
  import ChevronRight from '@lucide/svelte/icons/chevron-right';
  import PanelLeftClose from '@lucide/svelte/icons/panel-left-close';
  import PanelLeft from '@lucide/svelte/icons/panel-left';
  import { artifactStore, threadStore, projectStore, agentStore, workspaceStore } from '$lib/stores/index.js';
  import type { Artifact, Thread } from '$lib/stores/types.js';
  import { getFileIcon } from '$lib/icons.js';
  import { cn } from '$lib/utils.js';
  import ThreadList from './ThreadList.svelte';

  interface Props {
    onSelectFile: (artifact: Artifact) => void;
    onSelectThread: (thread: Thread) => void;
    collapsed?: boolean;
    onToggleCollapse?: () => void;
  }

  let { 
    onSelectFile, 
    onSelectThread, 
    collapsed = false,
    onToggleCollapse
  }: Props = $props();

  // File creation state
  let isCreatingFile = $state(false);
  let newFileName = $state('');
  
  // Section expansion state
  let chatsExpanded = $state(true);
  let filesExpanded = $state(false);
  let sourcesExpanded = $state(false);
  
  // Auto-manage expansion state based on content and project selection
  let lastProjectId = $state<string | null>(null);
  $effect(() => {
    if (currentProjectId !== lastProjectId) {
      // Reset when project changes
      filesExpanded = false;
      sourcesExpanded = false;
      lastProjectId = currentProjectId;
    }

    // Auto-expand Files if artifacts are loaded
    if (artifacts.length > 0) {
      filesExpanded = true;
    }
  });
  
  // Delete confirmation state
  let artifactToDelete = $state<string | null>(null);
  let threadToDelete = $state<string | null>(null);

  const currentProjectId = $derived(projectStore.currentProjectId);
  const artifacts = $derived(
    currentProjectId ? artifactStore.getProjectArtifacts(currentProjectId) : []
  );
  const threads = $derived(
    currentProjectId 
      ? threadStore.getProjectThreads(currentProjectId).sort((a, b) => b.updatedAt - a.updatedAt) 
      : []
  );

  // Check if there's already an empty thread (no messages)
  const hasEmptyNewThread = $derived(
    threads.some(t => threadStore.getThreadMessageCount(t.id) === 0)
  );

  function handleCreateFile() {
    if (!newFileName.trim() || !currentProjectId) return;
    
    let fileName = newFileName.trim();
    if (!fileName.endsWith('.md')) {
      fileName += '.md';
    }
    
    const artifact = artifactStore.createArtifact(currentProjectId, fileName, '');
    newFileName = '';
    isCreatingFile = false;
    onSelectFile(artifact);
  }

  function handleCreateThread() {
    if (!currentProjectId) return;
    
    // Reset agent state first - this clears any pending interrupts
    // so the new thread starts fresh
    agentStore.resetStream();
    
    // If there's already an empty thread (no messages), select it instead
    const existingEmptyThread = threads.find(
      t => threadStore.getThreadMessageCount(t.id) === 0
    );
    
    if (existingEmptyThread) {
      onSelectThread(existingEmptyThread);
      return;
    }
    
    // Create with a temporary title - it will be updated on first message
    const thread = threadStore.createThread(currentProjectId, 'New Chat');
    onSelectThread(thread);
  }
  
  function handleSelectThread(thread: Thread) {
    // REMOVED: agentStore.resetStream() - allow background runs to continue
    onSelectThread(thread);
  }

  function handleDeleteArtifact() {
    if (artifactToDelete) {
      artifactStore.deleteArtifact(artifactToDelete);
      artifactToDelete = null;
    }
  }

  function handleDeleteThread() {
    if (threadToDelete) {
      threadStore.deleteThread(threadToDelete);
      threadToDelete = null;
    }
  }

  function handleFileKeydown(e: KeyboardEvent) {
    if (e.key === 'Enter') {
      handleCreateFile();
    } else if (e.key === 'Escape') {
      isCreatingFile = false;
      newFileName = '';
    }
  }

  function isFileOpen(artifactId: string): boolean {
    return workspaceStore.leftTabs.some(t => t.id === artifactId) || 
           workspaceStore.rightTabs.some(t => t.id === artifactId);
  }

  function isThreadOpen(threadId: string): boolean {
    return workspaceStore.leftTabs.some(t => t.id === threadId) || 
           workspaceStore.rightTabs.some(t => t.id === threadId);
  }
</script>

{#if collapsed}
  <!-- Collapsed state -->
  <div class="flex h-full flex-col items-center border-r border-zinc-800 bg-zinc-950 py-2">
    <button
      onclick={onToggleCollapse}
      class="rounded p-2 text-zinc-500 transition-colors hover:bg-zinc-800 hover:text-zinc-300"
      title="Expand sidebar"
    >
      <PanelLeft class="h-5 w-5" />
    </button>
  </div>
{:else}
  <div class="flex h-full flex-col border-r border-zinc-800 bg-zinc-950">
    <!-- Header with collapse button -->
    <div class="flex items-center justify-between border-b border-zinc-800 px-3 py-2">
      <span class="text-xs font-semibold uppercase tracking-wider text-zinc-500">
        Project
      </span>
      <button
        onclick={onToggleCollapse}
        class="rounded p-1 text-zinc-500 transition-colors hover:bg-zinc-800 hover:text-zinc-300"
        title="Collapse sidebar"
      >
        <PanelLeftClose class="h-4 w-4" />
      </button>
    </div>

    <!-- Chats Section -->
    <div class="flex flex-col border-b border-zinc-800 {chatsExpanded ? 'flex-1 min-h-0' : 'flex-shrink-0'}">
      <div class="flex w-full items-center justify-between px-3 py-2">
        <button 
          onclick={() => chatsExpanded = !chatsExpanded}
          class="flex items-center gap-2 text-zinc-500 transition-colors hover:text-zinc-300"
        >
          <ChevronRight class="h-4 w-4 transition-transform {chatsExpanded ? 'rotate-90' : ''}" />
          <span class="text-xs font-semibold uppercase tracking-wider">Chats</span>
        </button>
        <button
          onclick={handleCreateThread}
          class="rounded p-1 text-zinc-500 transition-colors hover:bg-zinc-800 hover:text-zinc-300"
          title="New thread"
        >
          <Plus class="h-4 w-4" />
        </button>
      </div>

      {#if chatsExpanded}
        <div class="flex-1 overflow-y-auto pb-2">
          <ThreadList
            {threads}
            onThreadSelect={(id) => handleSelectThread(threads.find(t => t.id === id)!)}
            onThreadDelete={(id, immediate) => {
              if (immediate) {
                threadStore.deleteThread(id);
              } else {
                threadToDelete = id;
              }
            }}
          />
        </div>
      {/if}
    </div>

    <!-- Files Section -->
    <div class="flex flex-col border-b border-zinc-800 {filesExpanded ? 'flex-1 min-h-0' : 'flex-shrink-0'}">
      <div class="flex w-full items-center justify-between px-3 py-2">
        <button 
          onclick={() => filesExpanded = !filesExpanded}
          class="flex items-center gap-2 text-zinc-500 transition-colors hover:text-zinc-300"
        >
          <ChevronRight class="h-4 w-4 transition-transform {filesExpanded ? 'rotate-90' : ''}" />
          <span class="text-xs font-semibold uppercase tracking-wider">Files</span>
        </button>
        <button
          onclick={() => (isCreatingFile = true)}
          class="rounded p-1 text-zinc-500 transition-colors hover:bg-zinc-800 hover:text-zinc-300"
          title="New file"
        >
          <Plus class="h-4 w-4" />
        </button>
      </div>

      {#if filesExpanded}
        <div class="flex flex-1 flex-col overflow-hidden pb-2">
          <!-- New File Form -->
          {#if isCreatingFile}
            <div class="px-3 pb-2">
              <input
                type="text"
                bind:value={newFileName}
                onkeydown={handleFileKeydown}
                placeholder="document.md"
                class="mb-2 w-full rounded border border-zinc-700 bg-zinc-900 px-2 py-1.5 text-sm text-zinc-100 placeholder-zinc-600 focus:border-amber-500 focus:outline-none"
              />
              <div class="flex gap-2">
                <button
                  onclick={handleCreateFile}
                  disabled={!newFileName.trim()}
                  class="flex-1 rounded bg-amber-600 px-2 py-1 text-xs font-medium text-white transition-colors hover:bg-amber-500 disabled:opacity-50"
                >
                  Create
                </button>
                <button
                  onclick={() => {
                    isCreatingFile = false;
                    newFileName = '';
                  }}
                  class="rounded border border-zinc-700 px-2 py-1 text-xs text-zinc-400 transition-colors hover:bg-zinc-800"
                >
                  Cancel
                </button>
              </div>
            </div>
          {/if}

          <!-- File List -->
          <div class="flex-1 overflow-y-auto py-1">
            {#if artifacts.length === 0 && !isCreatingFile}
              <div class="px-3 py-4 text-center text-xs text-zinc-600">
                No files yet
              </div>
            {:else}
              {#each artifacts as artifact (artifact.id)}
                {@const currentVersion = artifact.versions[artifact.currentVersionIndex]}
                {@const title = currentVersion?.title || 'Untitled'}
                {@const Icon = getFileIcon(title)}
                {@const isOpen = isFileOpen(artifact.id)}
                <div class="group relative px-2">
                  <button
                    onclick={() => onSelectFile(artifact)}
                    class={cn(
                      "flex w-full items-center gap-2 rounded-lg px-2 py-1.5 text-left transition-all duration-200",
                      isOpen 
                        ? "bg-zinc-800/80 ring-1 ring-zinc-700" 
                        : "hover:bg-zinc-800/40"
                    )}
                  >
                    <div class="flex items-center gap-2 min-w-0 flex-1">
                      {#if !artifact.viewed}
                        <span class="size-1.5 flex-shrink-0 rounded-full bg-blue-500"></span>
                      {/if}
                      <Icon class={cn(
                        "h-4 w-4 flex-shrink-0",
                        isOpen ? "text-amber-400" : (!artifact.viewed ? "text-blue-500" : "text-zinc-500")
                      )} />
                      <span class={cn(
                        "truncate text-sm font-medium transition-colors",
                        isOpen ? "text-zinc-100" : "text-zinc-400 group-hover:text-zinc-300"
                      )}>
                        {title}
                      </span>
                    </div>
                  </button>

                  <button
                    onclick={() => (artifactToDelete = artifact.id)}
                    class="absolute right-4 top-1/2 -translate-y-1/2 rounded bg-zinc-900/80 p-1.5 text-zinc-500 opacity-0 backdrop-blur-sm transition-all hover:text-red-500 group-hover:opacity-100"
                  >
                    <Trash2 class="h-3.5 w-3.5" />
                  </button>
                </div>
              {/each}
            {/if}
          </div>
        </div>
      {/if}
    </div>

    <!-- Sources Section -->
    <div class="flex flex-col border-b border-zinc-800 {sourcesExpanded ? 'flex-1 min-h-0' : 'flex-shrink-0'}">
      <div class="flex w-full items-center justify-between px-3 py-2">
        <button 
          onclick={() => sourcesExpanded = !sourcesExpanded}
          class="flex items-center gap-2 text-zinc-500 transition-colors hover:text-zinc-300"
        >
          <ChevronRight class="h-4 w-4 transition-transform {sourcesExpanded ? 'rotate-90' : ''}" />
          <span class="text-xs font-semibold uppercase tracking-wider">Sources</span>
        </button>
      </div>

      {#if sourcesExpanded}
        <div class="flex-1 overflow-y-auto px-3 py-4 text-center text-xs text-zinc-600">
          No sources yet
        </div>
      {/if}
    </div>

    <!-- Footer -->
    <div class="mt-auto border-t border-zinc-800 px-3 py-2 text-xs text-zinc-600">
      {threads.length} thread{threads.length !== 1 ? 's' : ''} · {artifacts.length} file{artifacts.length !== 1 ? 's' : ''}
    </div>
  </div>
{/if}

<!-- Delete File Confirmation Modal -->
{#if artifactToDelete}
  <div class="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
    <div class="w-full max-w-sm rounded-xl border border-zinc-800 bg-zinc-900 p-6 shadow-xl">
      <h3 class="text-lg font-semibold text-zinc-100">Delete File?</h3>
      <p class="mt-2 text-sm text-zinc-400">
        This will permanently delete this file and all its version history.
      </p>
      <div class="mt-6 flex gap-3">
        <button
          onclick={() => (artifactToDelete = null)}
          class="flex-1 rounded-lg border border-zinc-700 px-4 py-2 text-sm text-zinc-300 transition-colors hover:bg-zinc-800"
        >
          Cancel
        </button>
        <button
          onclick={handleDeleteArtifact}
          class="flex-1 rounded-lg bg-red-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-red-500"
        >
          Delete
        </button>
      </div>
    </div>
  </div>
{/if}

<!-- Delete Thread Confirmation Modal -->
{#if threadToDelete}
  <div class="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
    <div class="w-full max-w-sm rounded-xl border border-zinc-800 bg-zinc-900 p-6 shadow-xl">
      <h3 class="text-lg font-semibold text-zinc-100">Delete Thread?</h3>
      <p class="mt-2 text-sm text-zinc-400">
        This will permanently delete this conversation.
      </p>
      <div class="mt-6 flex gap-3">
        <button
          onclick={() => (threadToDelete = null)}
          class="flex-1 rounded-lg border border-zinc-700 px-4 py-2 text-sm text-zinc-300 transition-colors hover:bg-zinc-800"
        >
          Cancel
        </button>
        <button
          onclick={handleDeleteThread}
          class="flex-1 rounded-lg bg-red-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-red-500"
        >
          Delete
        </button>
      </div>
    </div>
  </div>
{/if}
