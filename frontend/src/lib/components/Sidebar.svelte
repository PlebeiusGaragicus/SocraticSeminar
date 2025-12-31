<script lang="ts">
  import MessageCircle from '@lucide/svelte/icons/message-circle';
  import Globe from '@lucide/svelte/icons/globe';
  import Plus from '@lucide/svelte/icons/plus';
  import Trash2 from '@lucide/svelte/icons/trash-2';
  import ChevronRight from '@lucide/svelte/icons/chevron-right';
  import ChevronDown from '@lucide/svelte/icons/chevron-down';
  import Tag from '@lucide/svelte/icons/tag';
  import Search from '@lucide/svelte/icons/search';
  import Check from '@lucide/svelte/icons/check';
  import PanelLeftClose from '@lucide/svelte/icons/panel-left-close';
  import PanelLeft from '@lucide/svelte/icons/panel-left';
  import { Popover } from "bits-ui";
  import { artifactStore, threadStore, projectStore, agentStore, workspaceStore, sourceStore } from '$lib/stores/index.js';
  import type { Artifact, Thread, Source, ThreadStatus } from '$lib/stores/types.js';
  import { getFileIcon } from '$lib/icons.js';
  import { cn } from '$lib/utils.js';
  import ThreadList from './ThreadList.svelte';
  import NewFileModal from './NewFileModal.svelte';
  import NewSourcesModal from './NewSourcesModal.svelte';

  interface Props {
    onSelectFile: (artifact: Artifact) => void;
    onSelectThread: (thread: Thread) => void;
    onSelectSource: (source: Source) => void;
    collapsed?: boolean;
    onToggleCollapse?: () => void;
  }

  let { 
    onSelectFile, 
    onSelectThread, 
    onSelectSource,
    collapsed = false,
    onToggleCollapse
  }: Props = $props();

  // File creation state
  let showNewFileModal = $state(false);
  let showNewSourcesModal = $state(false);
  
  // Section expansion state
  let chatsExpanded = $state(true);
  let filesExpanded = $state(false);
  let sourcesExpanded = $state(false);

  // Status filtering state
  type StatusFilter = "all" | ThreadStatus;
  let statusFilter = $state<StatusFilter>("all");
  let isFilterOpen = $state(false);

  // Tag filtering state
  let tagFilter = $state<string>("all");
  let isTagFilterOpen = $state(false);
  let tagFilterSearch = $state("");
  let tagFilterSearchInput = $state<HTMLInputElement | null>(null);

  // Tag selection state (for specific file)
  let tagSelectorFor = $state<string | null>(null);
  let tagSearch = $state("");
  let tagSearchInput = $state<HTMLInputElement | null>(null);

  // Renaming state
  let editingArtifactId = $state<string | null>(null);
  let editingTitle = $state("");
  let editInput = $state<HTMLInputElement | null>(null);

  const STATUS_COLORS: Record<ThreadStatus, string> = {
    idle: "bg-green-500",
    busy: "bg-blue-500",
    interrupted: "bg-orange-500",
    error: "bg-red-600",
  };

  const RANDOM_COLORS = [
    'bg-blue-500',
    'bg-amber-500',
    'bg-indigo-500',
    'bg-orange-500',
    'bg-sky-500',
    'bg-emerald-500',
    'bg-rose-500',
    'bg-slate-500'
  ];
  
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
  let sourceToDelete = $state<string | null>(null);
  let tagToDelete = $state<string | null>(null);

  const currentProjectId = $derived(projectStore.currentProjectId);
  const projectTags = $derived(projectStore.currentProject?.tags || []);

  const allArtifacts = $derived(
    currentProjectId ? artifactStore.getProjectArtifacts(currentProjectId) : []
  );
  const artifacts = $derived(
    tagFilter === "all" 
      ? allArtifacts 
      : allArtifacts.filter(a => a.tags?.includes(tagFilter))
  );
  const allThreads = $derived(
    currentProjectId 
      ? threadStore.getProjectThreads(currentProjectId).sort((a, b) => b.updatedAt - a.updatedAt) 
      : []
  );

  const threads = $derived(
    statusFilter === "all" 
      ? allThreads 
      : allThreads.filter(t => t.status === statusFilter)
  );

  const interruptedCount = $derived(
    allThreads.filter(t => t.status === 'interrupted').length
  );

  const sources = $derived(
    currentProjectId ? sourceStore.getProjectSources(currentProjectId) : []
  );

  // Check if there's already an empty thread (no messages)
  const hasEmptyNewThread = $derived(
    allThreads.some(t => threadStore.getThreadMessageCount(t.id) === 0)
  );

  function handleCreateThread() {
    if (!currentProjectId) return;
    
    // Reset agent state first - this clears any pending interrupts
    // so the new thread starts fresh
    agentStore.resetStream();
    
    // If there's already an empty thread (no messages), select it instead
    const existingEmptyThread = allThreads.find(
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

  function handleStatusChange(status: StatusFilter) {
    statusFilter = status;
    isFilterOpen = false;
  }

  function handleTagFilterChange(tag: string) {
    tagFilter = tag;
    isTagFilterOpen = false;
  }

  function handleToggleTag(artifactId: string, tagName: string) {
    artifactStore.toggleArtifactTag(artifactId, tagName);
  }

  function handleCreateAndToggleTag(artifactId: string, tagName: string) {
    if (!currentProjectId) return;
    
    let color = RANDOM_COLORS[Math.floor(Math.random() * RANDOM_COLORS.length)];
    
    // Use specific colors for default tags if they match by name
    const lowerName = tagName.toLowerCase();
    if (lowerName === 'draft') color = 'bg-red-500';
    else if (lowerName === 'final') color = 'bg-green-500';
    else if (lowerName === 'notes') color = 'bg-purple-500';
    else if (lowerName.includes('human-edit only')) color = 'bg-red-500';

    projectStore.addProjectTag(currentProjectId, { name: tagName, color, deletable: true });
    artifactStore.toggleArtifactTag(artifactId, tagName);
    tagSearch = "";
  }

  function getSortedTags(tags: string[] | undefined): string[] {
    if (!tags) return [];
    const tagOrder = projectTags.map(t => t.name);
    return [...tags].sort((a, b) => {
      const indexA = tagOrder.indexOf(a);
      const indexB = tagOrder.indexOf(b);
      if (indexA === -1 && indexB === -1) return a.localeCompare(b);
      if (indexA === -1) return 1;
      if (indexB === -1) return -1;
      return indexA - indexB;
    });
  }

  function startRenaming(artifact: Artifact) {
    const currentVersion = artifact.versions[artifact.currentVersionIndex];
    editingArtifactId = artifact.id;
    editingTitle = currentVersion?.title || "Untitled";
    
    // Auto-focus the input
    setTimeout(() => {
      editInput?.focus();
      editInput?.select();
    }, 0);
  }

  function handleRename() {
    if (editingArtifactId && editingTitle.trim()) {
      artifactStore.renameArtifact(editingArtifactId, editingTitle.trim());
    }
    editingArtifactId = null;
    editingTitle = "";
  }

  function handleRenameKeyDown(e: KeyboardEvent) {
    if (e.key === "Enter") {
      handleRename();
    } else if (e.key === "Escape") {
      editingArtifactId = null;
      editingTitle = "";
    }
  }

  function handleDeleteArtifact() {
    if (artifactToDelete) {
      artifactStore.deleteArtifact(artifactToDelete);
      workspaceStore.closeItemGlobally(artifactToDelete);
      artifactToDelete = null;
    }
  }

  function handleDeleteThread() {
    if (threadToDelete) {
      threadStore.deleteThread(threadToDelete);
      workspaceStore.closeItemGlobally(threadToDelete);
      threadToDelete = null;
    }
  }

  function handleDeleteSource() {
    if (sourceToDelete) {
      sourceStore.deleteSource(sourceToDelete);
      workspaceStore.closeItemGlobally(sourceToDelete);
      sourceToDelete = null;
    }
  }

  function handleDeleteTag() {
    if (tagToDelete && currentProjectId) {
      artifactStore.removeTagFromAllArtifacts(currentProjectId, tagToDelete);
      projectStore.deleteProjectTag(currentProjectId, tagToDelete);
      if (tagFilter === tagToDelete) {
        tagFilter = "all";
      }
      tagToDelete = null;
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

  function isSourceOpen(sourceId: string): boolean {
    return workspaceStore.leftTabs.some(t => t.id === sourceId) || 
           workspaceStore.rightTabs.some(t => t.id === sourceId);
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
      <span class="text-xs font-semibold uppercase tracking-wider text-zinc-200">
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
          class="flex items-center gap-2 text-zinc-400 transition-colors hover:text-zinc-100"
        >
          <ChevronRight class="h-4 w-4 transition-transform {chatsExpanded ? 'rotate-90' : ''}" />
          <span class="text-xs font-semibold uppercase tracking-wider">Chats</span>
        </button>
        
        <div class="flex items-center gap-1.5">
          {#if chatsExpanded}
            <!-- Status Filter Dropdown -->
            <div class="relative">
              <button
                onclick={() => isFilterOpen = !isFilterOpen}
                class="flex items-center gap-1 rounded border border-zinc-700/50 bg-zinc-900/50 px-1.5 py-0.5 text-[10px] font-medium text-zinc-400 transition-all hover:border-zinc-600 hover:bg-zinc-800 hover:text-zinc-200"
                title="Filter by status"
              >
                <span>{statusFilter === 'all' ? 'All' : statusFilter.charAt(0).toUpperCase() + statusFilter.slice(1)}</span>
                <ChevronDown class="h-2.5 w-2.5" />
              </button>

              {#if isFilterOpen}
                <div class="absolute right-0 top-full z-50 mt-1 w-32 rounded-lg border border-zinc-800 bg-zinc-900 p-1 shadow-xl">
                  <button
                    onclick={() => handleStatusChange('all')}
                    class="flex w-full items-center gap-2 rounded px-2 py-1.5 text-left text-[10px] text-zinc-300 hover:bg-zinc-800"
                  >
                    All Statuses
                  </button>
                  <div class="my-1 border-t border-zinc-800"></div>
                  {#each ['idle', 'busy', 'interrupted', 'error'] as status}
                    <button
                      onclick={() => handleStatusChange(status as ThreadStatus)}
                      class="flex w-full items-center gap-2 rounded px-2 py-1.5 text-left text-[10px] text-zinc-300 hover:bg-zinc-800"
                    >
                      <span class={cn("size-1.5 rounded-full", STATUS_COLORS[status as ThreadStatus])}></span>
                      <span class="capitalize">{status}</span>
                      {#if status === 'interrupted' && interruptedCount > 0}
                        <span class="ml-auto flex size-3.5 items-center justify-center rounded-full bg-red-600 text-[9px] font-bold text-white">
                          {interruptedCount}
                        </span>
                      {/if}
                    </button>
                  {/each}
                </div>

                <!-- Backdrop for closing dropdown -->
                <button 
                  class="fixed inset-0 z-40 h-full w-full cursor-default border-none bg-transparent" 
                  onclick={() => isFilterOpen = false}
                  aria-label="Close filter menu"
                ></button>
              {/if}
            </div>
          {/if}

          <button
            onclick={handleCreateThread}
            class="group/plus rounded p-1 transition-colors hover:bg-zinc-800"
            title="New thread"
          >
            <Plus class="h-4 w-4 text-amber-200/90 transition-all group-hover/plus:text-amber-100 group-hover/plus:brightness-125" strokeWidth={2.5} />
          </button>
        </div>
      </div>

      {#if chatsExpanded}
        <div class="flex-1 overflow-y-auto pb-2">
          <ThreadList
            {threads}
            onThreadSelect={(id) => handleSelectThread(threads.find(t => t.id === id)!)}
            onThreadDelete={(id, immediate) => {
              if (immediate) {
                threadStore.deleteThread(id);
                workspaceStore.closeItemGlobally(id);
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
          class="flex items-center gap-2 text-zinc-400 transition-colors hover:text-zinc-200"
        >
          <ChevronRight class="h-4 w-4 transition-transform {filesExpanded ? 'rotate-90' : ''}" />
          <span class="text-xs font-semibold uppercase tracking-wider">Files</span>
        </button>
        
        <div class="flex items-center gap-1.5">
          {#if filesExpanded}
            <!-- Tag Filter Dropdown -->
            <Popover.Root 
              open={isTagFilterOpen} 
              onOpenChange={(v) => { 
                isTagFilterOpen = v; 
                if (!v) tagFilterSearch = ""; 
                else setTimeout(() => tagFilterSearchInput?.focus(), 0);
              }}
            >
              <Popover.Trigger
                class="flex items-center gap-1 rounded border border-zinc-700/50 bg-zinc-900/50 px-1.5 py-0.5 text-[10px] font-medium text-zinc-400 transition-all hover:border-zinc-600 hover:bg-zinc-800 hover:text-zinc-200"
                title="Filter by tag"
              >
                <span>{tagFilter === 'all' ? 'All' : tagFilter}</span>
                <ChevronDown class="h-2.5 w-2.5" />
              </Popover.Trigger>
              <Popover.Portal>
                <Popover.Content
                  side="bottom"
                  align="end"
                  sideOffset={5}
                  class="z-50 w-48 rounded-lg border border-zinc-800 bg-zinc-900 p-1 shadow-xl focus:outline-none"
                >
                  <div class="mb-1 flex items-center gap-2 border-b border-zinc-800 px-2 py-1.5">
                    <Search class="size-3 text-zinc-500" />
                    <input 
                      bind:this={tagFilterSearchInput}
                      bind:value={tagFilterSearch}
                      placeholder="Search tags..."
                      class="w-full bg-transparent text-[10px] text-zinc-100 outline-none placeholder:text-zinc-600"
                    />
                  </div>

                  <div class="max-h-48 overflow-y-auto">
                    <button
                      onclick={() => handleTagFilterChange('all')}
                      class="flex w-full items-center gap-2 rounded px-2 py-1.5 text-left text-[10px] text-zinc-300 hover:bg-zinc-800"
                    >
                      All Tags
                    </button>
                    <div class="my-1 border-t border-zinc-800"></div>
                    {#each projectTags.filter(t => t.name.toLowerCase().includes(tagFilterSearch.toLowerCase())) as tag}
                      <div class="group/tag relative flex w-full items-center gap-2 rounded px-2 py-1.5 text-left text-[10px] text-zinc-300 hover:bg-zinc-800">
                        <button
                          onclick={() => handleTagFilterChange(tag.name)}
                          class="flex flex-1 items-center gap-2 text-left"
                        >
                          <span class={cn("size-1.5 rounded-full", tag.color)}></span>
                          <span class="capitalize">{tag.name}</span>
                          {#if tagFilter === tag.name}
                            <Check class="ml-auto size-3 text-blue-500" />
                          {/if}
                        </button>
                        {#if tag.deletable !== false}
                          <button
                            onclick={(e) => {
                              e.stopPropagation();
                              tagToDelete = tag.name;
                            }}
                            class="ml-1 opacity-0 group-hover/tag:opacity-100 p-0.5 text-zinc-500 hover:text-red-500 transition-opacity"
                            title="Delete tag"
                          >
                            <Trash2 class="size-3" />
                          </button>
                        {/if}
                      </div>
                    {/each}
                  </div>
                </Popover.Content>
              </Popover.Portal>
            </Popover.Root>
          {/if}

          <button
            onclick={() => (showNewFileModal = true)}
            class="group/plus rounded p-1 transition-colors hover:bg-zinc-800"
            title="New file"
          >
            <Plus class="h-4 w-4 text-amber-200/90 transition-all group-hover/plus:text-amber-100 group-hover/plus:brightness-125" strokeWidth={2.5} />
          </button>
        </div>
      </div>

      {#if filesExpanded}
        <div class="flex flex-1 flex-col overflow-hidden pb-2">
          <!-- File List -->
          <div class="flex-1 overflow-y-auto py-1">
            {#if artifacts.length === 0}
              <div class="px-3 py-4 text-center text-xs text-zinc-600">
                {tagFilter === 'all' ? 'No files yet' : `No files with tag "${tagFilter}"`}
              </div>
            {:else}
              {#each artifacts as artifact (artifact.id)}
                {@const currentVersion = artifact.versions[artifact.currentVersionIndex]}
                {@const title = currentVersion?.title || 'Untitled'}
                {@const Icon = getFileIcon(title)}
                {@const isOpen = isFileOpen(artifact.id)}
                <div class={cn(
                  "group relative px-2",
                  tagSelectorFor === artifact.id ? "z-50" : "z-auto"
                )}
                  role="listitem"
                  draggable="true"
                  ondragstart={(e) => {
                    e.dataTransfer?.setData('application/svelte-tab-id', artifact.id);
                    e.dataTransfer?.setData('application/svelte-tab-type', 'artifact');
                  }}
                >
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
                      
                      {#if editingArtifactId === artifact.id}
                        <input
                          bind:this={editInput}
                          bind:value={editingTitle}
                          onblur={handleRename}
                          onkeydown={handleRenameKeyDown}
                          onclick={(e) => e.stopPropagation()}
                          class="h-6 w-full rounded bg-zinc-900 px-1 text-sm font-medium text-zinc-100 outline-none ring-1 ring-blue-500"
                        />
                      {:else}
                        <span 
                          ondblclick={() => startRenaming(artifact)}
                          title={title}
                          class={cn(
                            "truncate text-sm font-medium transition-colors",
                            isOpen ? "text-zinc-100" : "text-zinc-400 group-hover:text-zinc-300"
                          )}
                        >
                          {title}
                        </span>
                      {/if}
                      
                      <!-- Tag Indicators -->
                      {#if getSortedTags(artifact.tags).length > 0}
                        <div class="flex gap-0.5">
                          {#each getSortedTags(artifact.tags) as tagName}
                            {@const tag = projectTags.find(t => t.name === tagName)}
                            {#if tag}
                              <span 
                                class={cn("size-1.5 flex-shrink-0 rounded-full", tag.color)}
                                title={`Tag: ${tagName}`}
                              ></span>
                            {/if}
                          {/each}
                        </div>
                      {/if}
                    </div>
                  </button>

                  <div class={cn(
                    "absolute right-2 top-1/2 flex -translate-y-1/2 items-center gap-1 transition-opacity",
                    tagSelectorFor === artifact.id ? "opacity-100" : "opacity-0 group-hover:opacity-100"
                  )}>
                    <!-- Tag Selector Trigger -->
                    <Popover.Root 
                      open={tagSelectorFor === artifact.id} 
                      onOpenChange={(v) => { 
                        if (!v) { 
                          tagSelectorFor = null; 
                          tagSearch = ""; 
                        } else {
                          setTimeout(() => tagSearchInput?.focus(), 0);
                        }
                      }}
                    >
                      <Popover.Trigger
                        onclick={(e) => e.stopPropagation()}
                        class="rounded p-1 text-zinc-500 hover:bg-zinc-700 hover:text-zinc-300"
                        title="Edit tags"
                      >
                        <Tag class="h-3.5 w-3.5" />
                      </Popover.Trigger>
                      <Popover.Portal>
                        <Popover.Content
                          side="bottom"
                          align="end"
                          sideOffset={5}
                          class="z-50 w-48 rounded-lg border border-zinc-800 bg-zinc-900 p-1 shadow-xl focus:outline-none"
                        >
                          <div class="mb-1 flex items-center gap-2 border-b border-zinc-800 px-2 py-1.5">
                            <Search class="size-3 text-zinc-500" />
                            <input 
                              bind:this={tagSearchInput}
                              bind:value={tagSearch}
                              placeholder="Search or create tag..."
                              class="w-full bg-transparent text-[10px] text-zinc-100 outline-none placeholder:text-zinc-600"
                              onkeydown={(e) => {
                                if (e.key === 'Enter' && tagSearch.trim()) {
                                  handleCreateAndToggleTag(artifact.id, tagSearch.trim());
                                }
                              }}
                            />
                          </div>

                          <div class="max-h-48 overflow-y-auto">
                            {#each projectTags.filter(t => t.name.toLowerCase().includes(tagSearch.toLowerCase())) as tag}
                              {@const isSelected = artifact.tags?.includes(tag.name)}
                              <button
                                onclick={(e) => {
                                  e.stopPropagation();
                                  handleToggleTag(artifact.id, tag.name);
                                }}
                                class="flex w-full items-center gap-2 rounded px-2 py-1.5 text-left text-[10px] text-zinc-300 hover:bg-zinc-800"
                              >
                                <span class={cn("size-1.5 rounded-full", tag.color)}></span>
                                <span class="flex-1 truncate capitalize">{tag.name}</span>
                                {#if isSelected}
                                  <Check class="size-3 text-blue-500" />
                                {/if}
                              </button>
                            {/each}

                            {#if tagSearch.trim() && !projectTags.some(t => t.name.toLowerCase() === tagSearch.trim().toLowerCase())}
                              <button
                                onclick={(e) => {
                                  e.stopPropagation();
                                  handleCreateAndToggleTag(artifact.id, tagSearch.trim());
                                }}
                                class="flex w-full items-center gap-2 rounded px-2 py-1.5 text-left text-[10px] text-zinc-400 hover:bg-zinc-800 italic"
                              >
                                <Plus class="size-3" />
                                <span>Create "{tagSearch}"</span>
                              </button>
                            {/if}
                          </div>
                        </Popover.Content>
                      </Popover.Portal>
                    </Popover.Root>

                    <button
                      onclick={(e) => {
                        e.stopPropagation();
                        if (e.shiftKey) {
                          artifactStore.deleteArtifact(artifact.id);
                          workspaceStore.closeItemGlobally(artifact.id);
                        } else {
                          artifactToDelete = artifact.id;
                        }
                      }}
                      class="rounded p-1 text-zinc-500 hover:bg-zinc-700 hover:text-red-500"
                      title="Delete file (Shift + click to skip confirmation)"
                    >
                      <Trash2 class="h-3.5 w-3.5" />
                    </button>
                  </div>
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
          class="flex items-center gap-2 text-zinc-400 transition-colors hover:text-zinc-200"
        >
          <ChevronRight class="h-4 w-4 transition-transform {sourcesExpanded ? 'rotate-90' : ''}" />
          <span class="text-xs font-semibold uppercase tracking-wider">Sources</span>
        </button>
        <button
          onclick={() => (showNewSourcesModal = true)}
          class="group/plus rounded p-1 transition-colors hover:bg-zinc-800"
          title="Add sources"
        >
          <Plus class="h-4 w-4 text-amber-200/90 transition-all group-hover/plus:text-amber-100 group-hover/plus:brightness-125" strokeWidth={2.5} />
        </button>
      </div>

      {#if sourcesExpanded}
        <div class="flex-1 overflow-y-auto py-1">
          {#if sources.length === 0}
            <div class="px-3 py-4 text-center text-xs text-zinc-600">
              No sources yet
            </div>
          {:else}
            {#each sources as source (source.id)}
              {@const isOpen = isSourceOpen(source.id)}
              <div 
                class="group relative px-2"
                role="listitem"
                draggable="true"
                ondragstart={(e) => {
                  e.dataTransfer?.setData('application/svelte-tab-id', source.id);
                  e.dataTransfer?.setData('application/svelte-tab-type', 'source');
                }}
              >
                <button
                  onclick={() => onSelectSource(source)}
                  class={cn(
                    "flex w-full items-center gap-2 rounded-lg px-2 py-1.5 text-left transition-all duration-200",
                    isOpen 
                      ? "bg-zinc-800/80 ring-1 ring-zinc-700" 
                      : "hover:bg-zinc-800/40"
                  )}
                >
                  <div class="flex items-center gap-2 min-w-0 flex-1">
                    {#if !source.viewed}
                      <span class="size-1.5 flex-shrink-0 rounded-full bg-blue-500"></span>
                    {/if}
                    <Globe class={cn(
                      "h-4 w-4 flex-shrink-0",
                      isOpen ? "text-blue-400" : (!source.viewed ? "text-blue-500" : "text-zinc-500")
                    )} />
                    <span class={cn(
                      "truncate text-sm font-medium transition-colors",
                      isOpen ? "text-zinc-100" : "text-zinc-400 group-hover:text-zinc-300"
                    )}>
                      {source.title}
                    </span>
                  </div>
                </button>

                <button
                  onclick={(e) => {
                    e.stopPropagation();
                    if (e.shiftKey) {
                      sourceStore.deleteSource(source.id);
                      workspaceStore.closeItemGlobally(source.id);
                    } else {
                      sourceToDelete = source.id;
                    }
                  }}
                  class="absolute right-4 top-1/2 -translate-y-1/2 rounded bg-zinc-900/80 p-1.5 text-zinc-500 opacity-0 backdrop-blur-sm transition-all hover:text-red-500 group-hover:opacity-100"
                  title="Delete source (Shift + click to skip confirmation)"
                >
                  <Trash2 class="h-3.5 w-3.5" />
                </button>
              </div>
            {/each}
          {/if}
        </div>
      {/if}
    </div>

    <!-- Footer -->
    <div class="mt-auto border-t border-zinc-800 px-3 py-2 text-xs text-zinc-600">
      {threads.length} thread{threads.length !== 1 ? 's' : ''} · {artifacts.length} file{artifacts.length !== 1 ? 's' : ''} · {sources.length} source{sources.length !== 1 ? 's' : ''}
    </div>
  </div>
{/if}

{#if showNewFileModal}
  <NewFileModal onClose={() => (showNewFileModal = false)} />
{/if}

{#if showNewSourcesModal}
  <NewSourcesModal onClose={() => (showNewSourcesModal = false)} />
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

<!-- Delete Source Confirmation Modal -->
{#if sourceToDelete}
  <div class="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
    <div class="w-full max-w-sm rounded-xl border border-zinc-800 bg-zinc-900 p-6 shadow-xl">
      <h3 class="text-lg font-semibold text-zinc-100">Delete Source?</h3>
      <p class="mt-2 text-sm text-zinc-400">
        This will remove this source from your project.
      </p>
      <div class="mt-6 flex gap-3">
        <button
          onclick={() => (sourceToDelete = null)}
          class="flex-1 rounded-lg border border-zinc-700 px-4 py-2 text-sm text-zinc-300 transition-colors hover:bg-zinc-800"
        >
          Cancel
        </button>
        <button
          onclick={handleDeleteSource}
          class="flex-1 rounded-lg bg-red-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-red-500"
        >
          Delete
        </button>
      </div>
    </div>
  </div>
{/if}

<!-- Delete Tag Confirmation Modal -->
{#if tagToDelete}
  <div class="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
    <div class="w-full max-w-sm rounded-xl border border-zinc-800 bg-zinc-900 p-6 shadow-xl">
      <h3 class="text-lg font-semibold text-zinc-100">Delete Tag?</h3>
      <p class="mt-2 text-sm text-zinc-400">
        This will remove the tag "{tagToDelete}" from all files in this project.
      </p>
      <div class="mt-6 flex gap-3">
        <button
          onclick={() => (tagToDelete = null)}
          class="flex-1 rounded-lg border border-zinc-700 px-4 py-2 text-sm text-zinc-300 transition-colors hover:bg-zinc-800"
        >
          Cancel
        </button>
        <button
          onclick={handleDeleteTag}
          class="flex-1 rounded-lg bg-red-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-red-500"
        >
          Delete
        </button>
      </div>
    </div>
  </div>
{/if}
