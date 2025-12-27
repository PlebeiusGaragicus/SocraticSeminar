<script lang="ts">
  import File from '@lucide/svelte/icons/file';
  import FileCode from '@lucide/svelte/icons/file-code';
  import FileText from '@lucide/svelte/icons/file-text';
  import Plus from '@lucide/svelte/icons/plus';
  import Trash2 from '@lucide/svelte/icons/trash-2';
  import ChevronRight from '@lucide/svelte/icons/chevron-right';
  import { artifactStore, projectStore } from '$lib/stores/index.js';
  import type { Artifact, ArtifactType } from '$lib/stores/types.js';

  interface Props {
    onArtifactSelect: (artifact: Artifact) => void;
    openArtifactIds: string[];
  }

  let { onArtifactSelect, openArtifactIds = [] }: Props = $props();

  let isCreating = $state(false);
  let newFileName = $state('');
  let newFileType = $state<ArtifactType>('text');
  let artifactToDelete = $state<string | null>(null);

  const currentProjectId = $derived(projectStore.currentProjectId);
  const artifacts = $derived(
    currentProjectId ? artifactStore.getProjectArtifacts(currentProjectId) : []
  );

  function getFileIcon(type: ArtifactType) {
    switch (type) {
      case 'code':
        return FileCode;
      case 'socratic':
        return FileText;
      default:
        return File;
    }
  }

  function getFileExtension(type: ArtifactType, language?: string): string {
    if (type === 'code' && language) {
      const langMap: Record<string, string> = {
        javascript: '.js',
        typescript: '.ts',
        python: '.py',
        rust: '.rs',
        go: '.go',
        java: '.java',
        cpp: '.cpp',
        c: '.c'
      };
      return langMap[language.toLowerCase()] || `.${language}`;
    }
    if (type === 'socratic') return '.sem';
    return '.md';
  }

  function handleCreateFile() {
    if (!newFileName.trim() || !currentProjectId) return;
    
    const artifact = artifactStore.createArtifact(
      currentProjectId,
      newFileType,
      newFileName.trim(),
      '',
      newFileType === 'code' ? 'typescript' : undefined
    );
    
    newFileName = '';
    isCreating = false;
    onArtifactSelect(artifact);
  }

  function handleDeleteArtifact() {
    if (artifactToDelete) {
      artifactStore.deleteArtifact(artifactToDelete);
      artifactToDelete = null;
    }
  }

  function handleKeydown(e: KeyboardEvent) {
    if (e.key === 'Enter') {
      handleCreateFile();
    } else if (e.key === 'Escape') {
      isCreating = false;
      newFileName = '';
    }
  }

  function isOpen(artifactId: string): boolean {
    return openArtifactIds.includes(artifactId);
  }
</script>

<div class="flex h-full flex-col border-r border-zinc-800 bg-zinc-950">
  <!-- Header -->
  <div class="flex items-center justify-between border-b border-zinc-800 px-3 py-2">
    <span class="text-xs font-semibold uppercase tracking-wider text-zinc-500">
      Files
    </span>
    <button
      onclick={() => (isCreating = true)}
      class="rounded p-1 text-zinc-500 transition-colors hover:bg-zinc-800 hover:text-zinc-300"
      title="New file"
    >
      <Plus class="h-4 w-4" />
    </button>
  </div>

  <!-- New File Form -->
  {#if isCreating}
    <div class="border-b border-zinc-800 p-3">
      <input
        type="text"
        bind:value={newFileName}
        onkeydown={handleKeydown}
        placeholder="File name..."
        class="mb-2 w-full rounded border border-zinc-700 bg-zinc-900 px-2 py-1.5 text-sm text-zinc-100 placeholder-zinc-600 focus:border-amber-500 focus:outline-none"
        autofocus
      />
      <div class="mb-2 flex gap-1">
        <button
          onclick={() => (newFileType = 'text')}
          class="flex-1 rounded px-2 py-1 text-xs transition-colors {newFileType === 'text'
            ? 'bg-amber-500/20 text-amber-400'
            : 'bg-zinc-800 text-zinc-400 hover:bg-zinc-700'}"
        >
          Text
        </button>
        <button
          onclick={() => (newFileType = 'code')}
          class="flex-1 rounded px-2 py-1 text-xs transition-colors {newFileType === 'code'
            ? 'bg-amber-500/20 text-amber-400'
            : 'bg-zinc-800 text-zinc-400 hover:bg-zinc-700'}"
        >
          Code
        </button>
        <button
          onclick={() => (newFileType = 'socratic')}
          class="flex-1 rounded px-2 py-1 text-xs transition-colors {newFileType === 'socratic'
            ? 'bg-amber-500/20 text-amber-400'
            : 'bg-zinc-800 text-zinc-400 hover:bg-zinc-700'}"
        >
          Seminar
        </button>
      </div>
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
            isCreating = false;
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
    {#if artifacts.length === 0 && !isCreating}
      <div class="p-4 text-center text-sm text-zinc-600">
        No files yet
      </div>
    {:else}
      {#each artifacts as artifact (artifact.id)}
        {@const Icon = getFileIcon(artifact.type)}
        {@const currentVersion = artifact.versions[artifact.currentVersionIndex]}
        <div class="group relative">
          <button
            onclick={() => onArtifactSelect(artifact)}
            class="flex w-full items-center gap-2 px-3 py-1.5 text-left transition-colors hover:bg-zinc-800/50
              {isOpen(artifact.id) ? 'bg-zinc-800/70' : ''}"
          >
            <ChevronRight
              class="h-3 w-3 text-zinc-600 transition-transform
                {isOpen(artifact.id) ? 'rotate-90' : ''}"
            />
            <Icon
              class="h-4 w-4 flex-shrink-0
                {artifact.type === 'code'
                  ? 'text-blue-400'
                  : artifact.type === 'socratic'
                    ? 'text-amber-400'
                    : 'text-zinc-400'}"
            />
            <span class="flex-1 truncate text-sm text-zinc-300">
              {currentVersion?.title || 'Untitled'}
            </span>
            <span class="text-xs text-zinc-600">
              {getFileExtension(artifact.type, currentVersion?.language)}
            </span>
          </button>

          <!-- Delete button -->
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

  <!-- Footer with file count -->
  <div class="border-t border-zinc-800 px-3 py-2 text-xs text-zinc-600">
    {artifacts.length} file{artifacts.length !== 1 ? 's' : ''}
  </div>
</div>

<!-- Delete Confirmation Modal -->
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

