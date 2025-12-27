<script lang="ts">
  import Plus from '@lucide/svelte/icons/plus';
  import FileText from '@lucide/svelte/icons/file-text';
  import MessageSquare from '@lucide/svelte/icons/message-square';
  import { Button } from './ui/index.js';
  import { projectStore, threadStore, artifactStore } from '$lib/stores/index.js';

  interface Props {
    userNpub?: string | null;
  }

  let { userNpub = null }: Props = $props();

  let newProjectTitle = $state('');
  let showNewProject = $state(false);

  function handleCreateProject() {
    if (!newProjectTitle.trim() || !userNpub) return;
    projectStore.createProject(newProjectTitle.trim(), userNpub);
    newProjectTitle = '';
    showNewProject = false;
  }

  function handleSelectProject(id: string) {
    projectStore.selectProject(id);
    // Clear thread selection when switching projects
    threadStore.selectThread(null);
    artifactStore.selectArtifact(null);
  }

  // Get threads and artifacts for current project
  const currentProjectId = $derived(projectStore.currentProjectId);
  const projectThreads = $derived(
    currentProjectId ? threadStore.getProjectThreads(currentProjectId) : []
  );
  const projectArtifacts = $derived(
    currentProjectId ? artifactStore.getProjectArtifacts(currentProjectId) : []
  );
</script>

<aside class="flex h-full w-64 flex-col border-r border-border bg-sidebar">
  <!-- Header -->
  <div class="flex items-center justify-between border-b border-sidebar-border p-4">
    <h2 class="text-lg font-semibold text-sidebar-foreground">Projects</h2>
    <Button 
      variant="ghost" 
      size="icon" 
      onclick={() => showNewProject = !showNewProject}
    >
      <Plus class="h-4 w-4" />
    </Button>
  </div>

  <!-- New Project Form -->
  {#if showNewProject}
    <div class="border-b border-sidebar-border p-4">
      <input
        type="text"
        placeholder="Project name..."
        bind:value={newProjectTitle}
        onkeydown={(e) => e.key === 'Enter' && handleCreateProject()}
        class="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
      />
      <div class="mt-2 flex gap-2">
        <Button size="sm" onclick={handleCreateProject}>Create</Button>
        <Button size="sm" variant="ghost" onclick={() => showNewProject = false}>Cancel</Button>
      </div>
    </div>
  {/if}

  <!-- Project List -->
  <div class="flex-1 overflow-y-auto p-2">
    {#each projectStore.sortedProjects as project}
      <button
        onclick={() => handleSelectProject(project.id)}
        class="mb-1 w-full rounded-md p-2 text-left transition-colors
          {project.id === projectStore.currentProjectId 
            ? 'bg-sidebar-accent text-sidebar-accent-foreground' 
            : 'text-sidebar-foreground hover:bg-sidebar-accent/50'}"
      >
        <div class="font-medium">{project.title}</div>
        <div class="text-xs text-muted-foreground">
          {new Date(project.updatedAt).toLocaleDateString()}
        </div>
      </button>
    {/each}

    {#if projectStore.projects.length === 0}
      <p class="p-4 text-center text-sm text-muted-foreground">
        No projects yet. Create one to get started.
      </p>
    {/if}
  </div>

  <!-- Current Project Contents -->
  {#if projectStore.currentProject}
    <div class="border-t border-sidebar-border">
      <!-- Threads -->
      <div class="p-2">
        <div class="mb-2 flex items-center justify-between px-2">
          <span class="text-xs font-medium text-muted-foreground">THREADS</span>
          <button 
            onclick={() => projectStore.currentProjectId && threadStore.createThread(projectStore.currentProjectId)}
            class="text-muted-foreground hover:text-foreground"
          >
            <Plus class="h-3 w-3" />
          </button>
        </div>
        {#each projectThreads as thread}
          <button
            onclick={() => threadStore.selectThread(thread.id)}
            class="mb-1 flex w-full items-center gap-2 rounded-md p-2 text-left text-sm
              {thread.id === threadStore.currentThreadId
                ? 'bg-sidebar-accent text-sidebar-accent-foreground'
                : 'text-sidebar-foreground hover:bg-sidebar-accent/50'}"
          >
            <MessageSquare class="h-3 w-3" />
            <span class="truncate">{thread.title}</span>
          </button>
        {/each}
      </div>

      <!-- Artifacts -->
      <div class="p-2">
        <div class="mb-2 flex items-center justify-between px-2">
          <span class="text-xs font-medium text-muted-foreground">ARTIFACTS</span>
        </div>
        {#each projectArtifacts as artifact}
          <button
            onclick={() => artifactStore.selectArtifact(artifact.id)}
            class="mb-1 flex w-full items-center gap-2 rounded-md p-2 text-left text-sm
              {artifact.id === artifactStore.currentArtifactId
                ? 'bg-sidebar-accent text-sidebar-accent-foreground'
                : 'text-sidebar-foreground hover:bg-sidebar-accent/50'}"
          >
            <FileText class="h-3 w-3" />
            <span class="truncate">
              {artifact.versions[artifact.currentVersionIndex]?.title ?? 'Untitled'}
            </span>
          </button>
        {/each}
      </div>
    </div>
  {/if}
</aside>

