<script lang="ts">
  import { Cyphertap } from 'cyphertap';

  interface Props {
    projectTitle?: string | null;
    onBackToProjects?: () => void;
  }

  let { projectTitle = null, onBackToProjects }: Props = $props();
</script>

<nav class="flex h-14 items-center justify-between border-b border-zinc-800 bg-zinc-950 px-6">
  <div class="flex items-center gap-4">
    {#if projectTitle && onBackToProjects}
      <button
        onclick={onBackToProjects}
        class="flex items-center gap-2 text-zinc-400 transition-colors hover:text-zinc-100"
      >
        <svg
          xmlns="http://www.w3.org/2000/svg"
          width="20"
          height="20"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          stroke-width="2"
          stroke-linecap="round"
          stroke-linejoin="round"
        >
          <path d="m15 18-6-6 6-6" />
        </svg>
        <span class="text-sm">Projects</span>
      </button>
      <span class="text-zinc-600">/</span>
      <span class="font-medium text-zinc-100">{projectTitle}</span>
    {:else}
      <div class="flex items-center gap-3">
        <div class="flex h-8 w-8 items-center justify-center rounded-lg bg-gradient-to-br from-amber-500 to-orange-600">
          <svg
            xmlns="http://www.w3.org/2000/svg"
            width="18"
            height="18"
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
        <h1 class="text-lg font-bold tracking-tight text-zinc-100">
          Socratic Seminar
        </h1>
      </div>
    {/if}
  </div>

  <div class="flex items-center gap-4">
    <Cyphertap />
  </div>
</nav>

