<script lang="ts">
  import FileExplorer from './FileExplorer.svelte';
  import ThreadPanel from './ThreadPanel.svelte';
  import TabbedEditor from './TabbedEditor.svelte';
  import AgentPicker from './AgentPicker.svelte';
  import { artifactStore, projectStore } from '$lib/stores/index.js';
  import type { Artifact } from '$lib/stores/types.js';
  import { onMount } from 'svelte';

  interface Props {
    userNpub?: string | null;
  }

  let { userNpub = null }: Props = $props();

  let chatCollapsed = $state(false);
  let fileExplorerWidth = $state(220);

  const openArtifacts = $derived(artifactStore.openArtifacts);
  const activeArtifactId = $derived(artifactStore.currentArtifactId);
  const pendingChanges = $derived(artifactStore.pendingChanges);
  const currentProjectId = $derived(projectStore.currentProjectId);

  function handleArtifactSelect(artifact: Artifact) {
    artifactStore.selectArtifact(artifact.id);
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

  // Load artifacts when project changes
  onMount(() => {
    if (currentProjectId) {
      artifactStore.loadProjectArtifacts(currentProjectId);
    }
  });

  $effect(() => {
    if (currentProjectId) {
      artifactStore.loadProjectArtifacts(currentProjectId);
    }
  });
</script>

<div class="flex h-[calc(100vh-3.5rem)] w-full bg-zinc-950">
  <!-- Chat Panel (collapsible) -->
  <div
    class="flex-shrink-0 transition-all duration-300"
    style="width: {chatCollapsed ? '48px' : '320px'}"
  >
    <ThreadPanel collapsed={chatCollapsed} onToggleCollapse={() => (chatCollapsed = !chatCollapsed)} />
  </div>

  <!-- File Explorer -->
  <div class="flex-shrink-0" style="width: {fileExplorerWidth}px">
    <FileExplorer
      onArtifactSelect={handleArtifactSelect}
      openArtifactIds={artifactStore.openArtifactIds}
    />
  </div>

  <!-- Main Editor Area -->
  <div class="flex flex-1 flex-col overflow-hidden">
    <!-- Editor Toolbar -->
    <div class="flex items-center justify-between border-b border-zinc-800 bg-zinc-900/30 px-4 py-2">
      <div class="text-sm text-zinc-400">
        {#if activeArtifactId}
          {@const artifact = openArtifacts.find(a => a.id === activeArtifactId)}
          {#if artifact}
            {@const version = artifact.versions[artifact.currentVersionIndex]}
            <span class="text-zinc-200">{version?.title || 'Untitled'}</span>
            <span class="mx-2 text-zinc-600">|</span>
            <span>{artifact.type}</span>
            {#if version?.language}
              <span class="mx-1 text-zinc-600">·</span>
              <span>{version.language}</span>
            {/if}
          {/if}
        {:else}
          <span>No file selected</span>
        {/if}
      </div>
      
      <AgentPicker />
    </div>

    <!-- Tabbed Editor -->
    <div class="flex-1 overflow-hidden">
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
