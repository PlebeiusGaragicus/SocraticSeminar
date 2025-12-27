<script lang="ts">
  import { Navbar, ProjectDashboard, WorkspaceLayout } from '$lib/components/index.js';
  import { projectStore, artifactStore } from '$lib/stores/index.js';
  import { cyphertap } from 'cyphertap';
  import type { Project } from '$lib/stores/types.js';
  import { onMount } from 'svelte';

  // Application state
  let currentView = $state<'dashboard' | 'workspace'>('dashboard');

  // Reactive CypherTap state
  const isLoggedIn = $derived(cyphertap.isLoggedIn);
  const isReady = $derived(cyphertap.isReady);
  const userNpub = $derived(cyphertap.npub);

  // Current project
  const currentProject = $derived(projectStore.currentProject);

  // Initialize stores when user is ready
  $effect(() => {
    if (isReady && userNpub) {
      projectStore.init(userNpub);
    }
  });

  // Reset stores on logout
  $effect(() => {
    if (!isLoggedIn) {
      projectStore.reset();
      artifactStore.reset();
      currentView = 'dashboard';
    }
  });

  function handleProjectSelect(project: Project) {
    projectStore.selectProject(project.id);
    currentView = 'workspace';
  }

  function handleBackToProjects() {
    projectStore.selectProject(null);
    currentView = 'dashboard';
  }
</script>

<div class="flex h-screen flex-col bg-zinc-950">
  <!-- Navbar -->
  <Navbar
    projectTitle={currentView === 'workspace' ? currentProject?.title : null}
    onBackToProjects={currentView === 'workspace' ? handleBackToProjects : undefined}
  />

  <!-- Main Content -->
  {#if isReady}
    {#if currentView === 'workspace' && currentProject}
      <WorkspaceLayout userNpub={userNpub} />
    {:else}
      <ProjectDashboard
        userNpub={userNpub || ''}
        onProjectSelect={handleProjectSelect}
      />
    {/if}
  {:else if isLoggedIn}
    <!-- Loading state while wallet initializes -->
    <div class="flex flex-1 items-center justify-center">
      <div class="text-center">
        <div class="mb-4 inline-block h-8 w-8 animate-spin rounded-full border-4 border-amber-500 border-t-transparent"></div>
        <p class="text-zinc-400">Initializing wallet...</p>
      </div>
    </div>
  {:else}
    <!-- Login Screen -->
    <div class="flex flex-1 items-center justify-center">
      <div class="max-w-md text-center">
        <div class="mx-auto mb-6 flex h-16 w-16 items-center justify-center rounded-2xl bg-gradient-to-br from-amber-500 to-orange-600">
          <svg
            xmlns="http://www.w3.org/2000/svg"
            width="32"
            height="32"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            stroke-width="2"
            stroke-linecap="round"
            stroke-linejoin="round"
            class="text-white"
          >
            <path d="M2 3h6a4 4 0 0 1 4 4v14a3 3 0 0 0-3-3H2z" />
            <path d="M22 3h-6a4 4 0 0 0-4 4v14a3 3 0 0 1 3-3h7z" />
          </svg>
        </div>

        <h1 class="text-3xl font-bold tracking-tight text-zinc-100">
          Socratic Seminar
        </h1>
        <p class="mt-3 text-zinc-400">
          Project-based agentic document editor
        </p>
        <p class="mt-1 text-sm text-zinc-600">
          Powered by Nostr, Bitcoin eCash, and LangGraph
        </p>

        <div class="mt-8 flex flex-col items-center gap-4">
          <p class="text-sm text-zinc-500">
            Click above to login with Nostr
          </p>
        </div>

        <div class="mt-12 grid grid-cols-3 gap-6 text-center">
          <div class="rounded-lg border border-zinc-800 bg-zinc-900/50 p-4">
            <div class="mb-2 text-2xl">📝</div>
            <h3 class="text-sm font-medium text-zinc-300">Structured Writing</h3>
            <p class="mt-1 text-xs text-zinc-500">Socratic argument format</p>
          </div>
          <div class="rounded-lg border border-zinc-800 bg-zinc-900/50 p-4">
            <div class="mb-2 text-2xl">🤖</div>
            <h3 class="text-sm font-medium text-zinc-300">AI Assistance</h3>
            <p class="mt-1 text-xs text-zinc-500">LangGraph agents</p>
          </div>
          <div class="rounded-lg border border-zinc-800 bg-zinc-900/50 p-4">
            <div class="mb-2 text-2xl">⚡</div>
            <h3 class="text-sm font-medium text-zinc-300">Pay Per Query</h3>
            <p class="mt-1 text-xs text-zinc-500">Bitcoin eCash</p>
          </div>
        </div>
      </div>
    </div>
  {/if}
</div>
