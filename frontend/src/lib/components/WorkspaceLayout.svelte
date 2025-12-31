<script lang="ts">
  import Sidebar from './Sidebar.svelte';
  import TabbedPanel from './TabbedPanel.svelte';
  import { artifactStore, threadStore, projectStore, agentStore, workspaceStore } from '$lib/stores/index.js';
  import type { Artifact, Thread } from '$lib/stores/types.js';
  import { onMount } from 'svelte';

  interface Props {
    userNpub?: string | null;
  }

  let { userNpub = null }: Props = $props();

  // Panel state
  let sidebarCollapsed = $state(false);
  let sidebarWidth = $state(240);
  let leftColumnWidth = $state(0); // Will be set on mount
  let isDraggingSidebar = $state(false);
  let isDraggingDivider = $state(false);

  const currentProjectId = $derived(projectStore.currentProjectId);

  function handleSelectFile(artifact: Artifact) {
    workspaceStore.openItem(artifact.id, 'artifact');
  }

  function handleSelectThread(thread: Thread) {
    workspaceStore.openItem(thread.id, 'thread');
  }

  function handleTabSelect(id: string, column: 'left' | 'right') {
    workspaceStore.selectTab(id, column);
  }

  function handleTabClose(id: string, column: 'left' | 'right') {
    workspaceStore.closeTab(id, column);
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

  // Handle middle divider resize
  function handleDividerMouseDown(e: MouseEvent) {
    if (workspaceStore.rightPanelCollapsed) return;
    e.preventDefault();
    isDraggingDivider = true;
    document.addEventListener('mousemove', handleDividerMouseMove);
    document.addEventListener('mouseup', handleDividerMouseUp);
  }

  function handleDividerMouseMove(e: MouseEvent) {
    if (!isDraggingDivider) return;
    const offset = sidebarCollapsed ? 48 : sidebarWidth;
    const availableWidth = window.innerWidth - offset;
    const newWidth = Math.max(300, Math.min(availableWidth - 300, e.clientX - offset));
    leftColumnWidth = newWidth;
  }

  function handleDividerMouseUp() {
    isDraggingDivider = false;
    document.removeEventListener('mousemove', handleDividerMouseMove);
    document.removeEventListener('mouseup', handleDividerMouseUp);
  }

  // Track previous project ID to detect project changes
  let previousProjectId: string | null = null;

  // Initial proportions
  onMount(() => {
    const offset = sidebarCollapsed ? 48 : sidebarWidth;
    leftColumnWidth = (window.innerWidth - offset) / 2;

    if (currentProjectId) {
      artifactStore.loadProjectArtifacts(currentProjectId);
      threadStore.loadProjectThreads(currentProjectId);
      previousProjectId = currentProjectId;
    }
  });

  $effect(() => {
    if (currentProjectId) {
      if (previousProjectId && previousProjectId !== currentProjectId) {
        artifactStore.clearProjectState();
        threadStore.clearProjectState();
        workspaceStore.clearProjectState();
        agentStore.clearProjectState();
      }
      
      artifactStore.loadProjectArtifacts(currentProjectId);
      threadStore.loadProjectThreads(currentProjectId);
      previousProjectId = currentProjectId;
    }
  });
</script>

<div class="flex h-[calc(100vh-3.5rem)] w-full overflow-hidden bg-zinc-950">
  <!-- Sidebar -->
  <div class="flex-shrink-0" style="width: {sidebarCollapsed ? '48px' : sidebarWidth + 'px'}">
    <Sidebar
      onSelectFile={handleSelectFile}
      onSelectThread={handleSelectThread}
      collapsed={sidebarCollapsed}
      onToggleCollapse={handleToggleSidebar}
    />
  </div>

  <!-- Sidebar resize handle -->
  {#if !sidebarCollapsed}
    <div
      class="w-1 cursor-col-resize bg-zinc-800 hover:bg-amber-500/50 transition-colors {isDraggingSidebar ? 'bg-amber-500' : ''}"
      onmousedown={handleSidebarMouseDown}
      role="separator"
      aria-orientation="vertical"
    ></div>
  {/if}

  <!-- Main Workspace Area -->
  <div class="flex flex-1 overflow-hidden">
    <!-- Left Column -->
    <div class="flex flex-col overflow-hidden" style="width: {workspaceStore.rightPanelCollapsed ? '100%' : leftColumnWidth + 'px'}">
      <TabbedPanel
        column="left"
        tabs={workspaceStore.leftTabs}
        activeTabId={workspaceStore.activeLeftTabId}
        onTabSelect={(id) => handleTabSelect(id, 'left')}
        onTabClose={(id) => handleTabClose(id, 'left')}
      />
    </div>

    <!-- Middle Divider (only when right panel is open) -->
    {#if !workspaceStore.rightPanelCollapsed}
      <div
        class="w-1 cursor-col-resize bg-zinc-800 hover:bg-amber-500/50 transition-colors {isDraggingDivider ? 'bg-amber-500' : ''}"
        onmousedown={handleDividerMouseDown}
        role="separator"
        aria-orientation="vertical"
      ></div>

      <!-- Right Column -->
      <div class="flex flex-1 flex-col overflow-hidden">
        <TabbedPanel
          column="right"
          tabs={workspaceStore.rightTabs}
          activeTabId={workspaceStore.activeRightTabId}
          onTabSelect={(id) => handleTabSelect(id, 'right')}
          onTabClose={(id) => handleTabClose(id, 'right')}
          showClosePanel={true}
          onClosePanel={() => workspaceStore.collapseRightPanel()}
        />
      </div>
    {/if}
  </div>
</div>
