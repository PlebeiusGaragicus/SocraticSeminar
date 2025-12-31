<script lang="ts">
  import Sidebar from './Sidebar.svelte';
  import ChatPanel from './ChatPanel.svelte';
  import TabbedEditor from './TabbedEditor.svelte';
  import { artifactStore, threadStore, projectStore, agentStore } from '$lib/stores/index.js';
  import type { Artifact, Thread } from '$lib/stores/types.js';
  import { onMount } from 'svelte';

  interface Props {
    userNpub?: string | null;
  }

  let { userNpub = null }: Props = $props();

  // Panel state
  let sidebarCollapsed = $state(false);
  let sidebarWidth = $state(240);
  let chatWidth = $state(0); // Will be set on mount
  let isDraggingSidebar = $state(false);
  let isDraggingChat = $state(false);

  const openArtifacts = $derived(artifactStore.openArtifacts);
  const activeArtifactId = $derived(artifactStore.currentArtifactId);
  const pendingChanges = $derived(artifactStore.pendingChanges);
  const currentProjectId = $derived(projectStore.currentProjectId);
  const currentThreadId = $derived(threadStore.currentThreadId);

  function handleSelectFile(artifact: Artifact) {
    artifactStore.selectArtifact(artifact.id);
  }

  function handleSelectThread(thread: Thread) {
    threadStore.selectThread(thread.id);
  }

  function handleTabSelect(id: string) {
    artifactStore.selectArtifact(id);
  }

  function handleTabClose(id: string) {
    artifactStore.closeArtifact(id);
  }

  function handleAcceptChanges() {
    artifactStore.acceptPendingChanges();
  }

  function handleRejectChanges() {
    artifactStore.rejectPendingChanges();
  }

  function handleToggleSidebar() {
    sidebarCollapsed = !sidebarCollapsed;
  }

  // Handle sidebar resize
  function handleSidebarMouseDown(e: MouseEvent) {
    if (sidebarCollapsed) return;
    e.preventDefault();
    isDraggingSidebar = true;
    document.addEventListener('mousemove', handleSidebarMouseMove);
    document.addEventListener('mouseup', handleSidebarMouseUp);
  }

  function handleSidebarMouseMove(e: MouseEvent) {
    if (!isDraggingSidebar) return;
    const newWidth = Math.max(180, Math.min(400, e.clientX));
    sidebarWidth = newWidth;
  }

  function handleSidebarMouseUp() {
    isDraggingSidebar = false;
    document.removeEventListener('mousemove', handleSidebarMouseMove);
    document.removeEventListener('mouseup', handleSidebarMouseUp);
  }

  // Handle chat resize
  function handleChatMouseDown(e: MouseEvent) {
    e.preventDefault();
    isDraggingChat = true;
    document.addEventListener('mousemove', handleChatMouseMove);
    document.addEventListener('mouseup', handleChatMouseUp);
  }

  function handleChatMouseMove(e: MouseEvent) {
    if (!isDraggingChat) return;
    const offset = sidebarCollapsed ? 48 : sidebarWidth;
    const availableWidth = window.innerWidth - offset;
    const newWidth = Math.max(300, Math.min(availableWidth - 100, e.clientX - offset));
    chatWidth = newWidth;
  }

  function handleChatMouseUp() {
    isDraggingChat = false;
    document.removeEventListener('mousemove', handleChatMouseMove);
    document.removeEventListener('mouseup', handleChatMouseUp);
  }

  // Track previous project ID to detect project changes
  let previousProjectId: string | null = null;

  // Initial proportions
  onMount(() => {
    // Set initial chat width to 50% of available space
    const offset = sidebarCollapsed ? 48 : sidebarWidth;
    chatWidth = (window.innerWidth - offset) / 2;

    if (currentProjectId) {
      artifactStore.loadProjectArtifacts(currentProjectId);
      threadStore.loadProjectThreads(currentProjectId);
      previousProjectId = currentProjectId;
    }
  });

  $effect(() => {
    if (currentProjectId) {
      // If project changed, clear project-scoped state first
      if (previousProjectId && previousProjectId !== currentProjectId) {
        artifactStore.clearProjectState();
        threadStore.clearProjectState();
        agentStore.clearProjectState();
      }
      
      artifactStore.loadProjectArtifacts(currentProjectId);
      threadStore.loadProjectThreads(currentProjectId);
      previousProjectId = currentProjectId;
    }
  });
</script>

<div class="flex h-[calc(100vh-3.5rem)] w-full overflow-hidden bg-zinc-950">
  <!-- Sidebar: Threads + Files picker -->
  <div class="flex-shrink-0" style="width: {sidebarCollapsed ? '48px' : sidebarWidth + 'px'}">
    <Sidebar
      onSelectFile={handleSelectFile}
      onSelectThread={handleSelectThread}
      openArtifactIds={artifactStore.openArtifactIds}
      {currentThreadId}
      collapsed={sidebarCollapsed}
      onToggleCollapse={handleToggleSidebar}
    />
  </div>

  <!-- Sidebar resize handle (only when not collapsed) -->
  {#if !sidebarCollapsed}
    <div
      class="w-1 cursor-col-resize bg-zinc-800 hover:bg-amber-500/50 transition-colors {isDraggingSidebar ? 'bg-amber-500' : ''}"
      onmousedown={handleSidebarMouseDown}
      role="separator"
      aria-orientation="vertical"
    ></div>
  {/if}

  <!-- Main Content Area: Chat + Editor side by side -->
  <div class="flex flex-1 overflow-hidden">
    <!-- Chat Panel -->
    <div class="flex-shrink-0 overflow-hidden" style="width: {chatWidth}px">
      <ChatPanel />
    </div>

    <!-- Chat resize handle -->
    <div
      class="w-1 cursor-col-resize bg-zinc-800 hover:bg-amber-500/50 transition-colors {isDraggingChat ? 'bg-amber-500' : ''}"
      onmousedown={handleChatMouseDown}
      role="separator"
      aria-orientation="vertical"
    ></div>

    <!-- Editor Panel -->
    <div class="flex flex-1 flex-col overflow-hidden">
      <TabbedEditor
        {openArtifacts}
        {activeArtifactId}
        onTabSelect={handleTabSelect}
        onTabClose={handleTabClose}
        {pendingChanges}
        onAcceptChanges={handleAcceptChanges}
        onRejectChanges={handleRejectChanges}
      />
    </div>
  </div>
</div>
