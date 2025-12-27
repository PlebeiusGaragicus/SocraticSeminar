<script lang="ts">
  import ProjectSidebar from './ProjectSidebar.svelte';
  import ThreadPanel from './ThreadPanel.svelte';
  import ArtifactPanel from './ArtifactPanel.svelte';
  import { artifactStore } from '$lib/stores';

  interface Props {
    userNpub?: string | null;
  }

  let { userNpub = null }: Props = $props();

  const hasArtifact = $derived(artifactStore.currentArtifact !== null);
</script>

<div class="flex h-screen w-full">
  <!-- Sidebar -->
  <ProjectSidebar {userNpub} />

  <!-- Main content area -->
  <div class="flex flex-1">
    <!-- Thread Panel -->
    <div class="flex-1 border-r border-border {hasArtifact ? 'w-1/2' : 'w-full'}">
      <ThreadPanel />
    </div>

    <!-- Artifact Panel (conditional) -->
    {#if hasArtifact}
      <div class="w-1/2">
        <ArtifactPanel />
      </div>
    {/if}
  </div>
</div>

