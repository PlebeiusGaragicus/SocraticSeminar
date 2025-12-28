<script lang="ts">
  import FileText from '@lucide/svelte/icons/file-text';
  import MessageCircle from '@lucide/svelte/icons/message-circle';
  import Plus from '@lucide/svelte/icons/plus';
  import Trash2 from '@lucide/svelte/icons/trash-2';
  import ChevronRight from '@lucide/svelte/icons/chevron-right';
  import PanelLeftClose from '@lucide/svelte/icons/panel-left-close';
  import PanelLeft from '@lucide/svelte/icons/panel-left';
  import { artifactStore, threadStore, projectStore, agentStore } from '$lib/stores/index.js';
  import type { Artifact, Thread } from '$lib/stores/types.js';

  interface Props {
    onSelectFile: (artifact: Artifact) => void;
    onSelectThread: (thread: Thread) => void;
    openArtifactIds: string[];
    currentThreadId: string | null;
    collapsed?: boolean;
    onToggleCollapse?: () => void;
  }

  let { 
    onSelectFile, 
    onSelectThread, 
    openArtifactIds = [], 
    currentThreadId = null,
    collapsed = false,
    onToggleCollapse
  }: Props = $props();

  // File creation state
  let isCreatingFile = $state(false);
  let newFileName = $state('');
  
  // Delete confirmation state
  let artifactToDelete = $state<string | null>(null);
  let threadToDelete = $state<string | null>(null);

  // Resizable divider state
  let threadSectionHeight = $state(200);
  let isDraggingDivider = $state(false);
  let dragStartY = $state(0);
  let dragStartHeight = $state(0);
  let containerRef: HTMLDivElement;

  const currentProjectId = $derived(projectStore.currentProjectId);
  const artifacts = $derived(
    currentProjectId ? artifactStore.getProjectArtifacts(currentProjectId) : []
  );
  const threads = $derived(
    currentProjectId ? threadStore.getProjectThreads(currentProjectId) : []
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
    // If there's a pending interrupt on the current thread and we're switching,
    // reset the agent state to prevent UI confusion
    if (agentStore.awaitingHumanResponse && thread.id !== currentThreadId) {
      agentStore.resetStream();
    }
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
    return openArtifactIds.includes(artifactId);
  }

  // Divider drag handlers - use delta to prevent jumping
  function handleDividerMouseDown(e: MouseEvent) {
    e.preventDefault();
    isDraggingDivider = true;
    dragStartY = e.clientY;
    dragStartHeight = threadSectionHeight;
    document.addEventListener('mousemove', handleDividerMouseMove);
    document.addEventListener('mouseup', handleDividerMouseUp);
  }

  function handleDividerMouseMove(e: MouseEvent) {
    if (!isDraggingDivider || !containerRef) return;
    const containerRect = containerRef.getBoundingClientRect();
    const delta = e.clientY - dragStartY;
    const newHeight = dragStartHeight + delta;
    threadSectionHeight = Math.max(80, Math.min(containerRect.height - 150, newHeight));
  }

  function handleDividerMouseUp() {
    isDraggingDivider = false;
    document.removeEventListener('mousemove', handleDividerMouseMove);
    document.removeEventListener('mouseup', handleDividerMouseUp);
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
  <div bind:this={containerRef} class="flex h-full flex-col border-r border-zinc-800 bg-zinc-950">
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

    <!-- Threads Section -->
    <div class="flex flex-col overflow-hidden" style="height: {threadSectionHeight}px">
      <!-- Threads Header -->
      <div class="flex items-center justify-between px-3 py-2">
        <span class="text-xs font-semibold uppercase tracking-wider text-zinc-500">
          Threads
        </span>
        <button
          onclick={handleCreateThread}
          class="rounded p-1 text-zinc-500 transition-colors hover:bg-zinc-800 hover:text-zinc-300"
          title="New thread"
        >
          <Plus class="h-4 w-4" />
        </button>
      </div>

      <!-- Thread List -->
      <div class="flex-1 overflow-y-auto py-1">
        {#if threads.length === 0}
          <div class="px-3 py-2 text-center text-xs text-zinc-600">
            No threads yet
          </div>
        {:else}
          {#each threads as thread (thread.id)}
            <div class="group relative">
              <button
                onclick={() => handleSelectThread(thread)}
                class="flex w-full items-center gap-2 px-3 py-1.5 text-left transition-colors hover:bg-zinc-800/50
                  {thread.id === currentThreadId ? 'bg-zinc-800/70 border-l-2 border-amber-500' : ''}"
              >
                <MessageCircle class="h-4 w-4 flex-shrink-0 text-blue-400" />
                <span class="flex-1 truncate text-sm text-zinc-300">
                  {thread.title}
                </span>
              </button>

              <button
                onclick={() => (threadToDelete = thread.id)}
                class="absolute right-2 top-1/2 -translate-y-1/2 rounded p-1 text-zinc-600 opacity-0 transition-all hover:bg-red-500/10 hover:text-red-500 group-hover:opacity-100"
              >
                <Trash2 class="h-3 w-3" />
              </button>
            </div>
          {/each}
        {/if}
      </div>
    </div>

    <!-- Resizable Divider -->
    <div
      class="h-1 cursor-row-resize bg-zinc-800 hover:bg-amber-500/50 transition-colors {isDraggingDivider ? 'bg-amber-500' : ''}"
      onmousedown={handleDividerMouseDown}
      role="separator"
      aria-orientation="horizontal"
    ></div>

    <!-- Files Section -->
    <div class="flex flex-1 flex-col overflow-hidden">
      <!-- Files Header -->
      <div class="flex items-center justify-between px-3 py-2">
        <span class="text-xs font-semibold uppercase tracking-wider text-zinc-500">
          Files
        </span>
        <button
          onclick={() => (isCreatingFile = true)}
          class="rounded p-1 text-zinc-500 transition-colors hover:bg-zinc-800 hover:text-zinc-300"
          title="New file"
        >
          <Plus class="h-4 w-4" />
        </button>
      </div>

      <!-- New File Form -->
      {#if isCreatingFile}
        <div class="border-b border-zinc-800 px-3 pb-2">
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
            <div class="group relative">
              <button
                onclick={() => onSelectFile(artifact)}
                class="flex w-full items-center gap-2 px-3 py-1.5 text-left transition-colors hover:bg-zinc-800/50
                  {isFileOpen(artifact.id) ? 'bg-zinc-800/70 border-l-2 border-amber-500' : ''}"
              >
                <ChevronRight
                  class="h-3 w-3 text-zinc-600 transition-transform
                    {isFileOpen(artifact.id) ? 'rotate-90' : ''}"
                />
                <FileText class="h-4 w-4 flex-shrink-0 text-amber-400" />
                <span class="flex-1 truncate text-sm text-zinc-300">
                  {currentVersion?.title || 'Untitled'}
                </span>
              </button>

              <button
                onclick={() => (artifactToDelete = artifact.id)}
                class="absolute right-2 top-1/2 -translate-y-1/2 rounded p-1 text-zinc-600 opacity-0 transition-all hover:bg-red-500/10 hover:text-red-500 group-hover:opacity-100"
              >
                <Trash2 class="h-3.5 w-3.5" />
              </button>
            </div>
          {/each}
        {/if}
      </div>

      <!-- Footer -->
      <div class="border-t border-zinc-800 px-3 py-2 text-xs text-zinc-600">
        {threads.length} thread{threads.length !== 1 ? 's' : ''} · {artifacts.length} file{artifacts.length !== 1 ? 's' : ''}
      </div>
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
