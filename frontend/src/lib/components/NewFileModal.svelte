<script lang="ts">
  import X from '@lucide/svelte/icons/x';
  import FilePlus from '@lucide/svelte/icons/file-plus';
  import FileText from '@lucide/svelte/icons/file-text';
  import Upload from '@lucide/svelte/icons/upload';
  import { Button } from './ui/index.js';
  import { artifactStore, projectStore, workspaceStore } from '$lib/stores/index.js';
  import { FILE_TEMPLATES } from '$lib/templates.js';
  import { cn } from '$lib/utils.js';
  import { onMount } from 'svelte';

  interface Props {
    column?: 'left' | 'right';
    onClose: () => void;
  }

  let { column = 'left', onClose }: Props = $props();

  let fileName = $state('');
  let isDragging = $state(false);
  let inputRef: HTMLInputElement;

  function handleCreateEmpty() {
    if (!fileName.trim()) return;
    let name = fileName.trim();
    if (!name.includes('.')) name += '.md';
    
    const projectId = projectStore.currentProjectId;
    if (!projectId) return;

    const artifact = artifactStore.createArtifact(projectId, name, '');
    workspaceStore.openItem(artifact.id, 'artifact', column);
    onClose();
  }

  function handleTemplateSelect(template: typeof FILE_TEMPLATES[0]) {
    const projectId = projectStore.currentProjectId;
    if (!projectId) return;

    const artifact = artifactStore.createArtifact(projectId, template.title + '.md', template.content);
    workspaceStore.openItem(artifact.id, 'artifact', column);
    onClose();
  }

  async function handleFiles(files: FileList | null) {
    if (!files || !projectStore.currentProjectId) return;
    
    for (const file of Array.from(files)) {
      const content = await file.text();
      const artifact = artifactStore.createArtifact(projectStore.currentProjectId, file.name, content);
      workspaceStore.openItem(artifact.id, 'artifact', column);
    }
    onClose();
  }

  function handleDrop(e: DragEvent) {
    e.preventDefault();
    isDragging = false;
    handleFiles(e.dataTransfer?.files || null);
  }

  function handleKeydown(e: KeyboardEvent) {
    if (e.key === 'Enter') {
      handleCreateEmpty();
    } else if (e.key === 'Escape') {
      onClose();
    }
  }

  onMount(() => {
    inputRef?.focus();
  });

  function handleBackdropClick(e: MouseEvent) {
    if (e.target === e.currentTarget) {
      onClose();
    }
  }
</script>

<div 
  class="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4"
  onclick={handleBackdropClick}
>
  <div 
    class="w-full max-w-lg rounded-xl border border-zinc-800 bg-zinc-900 shadow-2xl overflow-hidden flex flex-col max-h-[90vh]"
    role="dialog"
    aria-modal="true"
  >
    <!-- Header -->
    <div class="flex items-center justify-between border-b border-zinc-800 px-4 py-3 bg-zinc-800/50">
      <div class="flex items-center gap-2">
        <FilePlus class="h-5 w-5 text-amber-500" />
        <h3 class="font-semibold text-zinc-100">Create New File</h3>
      </div>
      <button 
        onclick={onClose}
        class="rounded-lg p-1 text-zinc-500 hover:bg-zinc-700 hover:text-zinc-200 transition-colors"
      >
        <X class="h-5 w-5" />
      </button>
    </div>

    <div class="overflow-y-auto p-6 space-y-8">
      <!-- Filename Input -->
      <section>
        <label for="filename" class="block text-xs font-bold uppercase tracking-wider text-zinc-500 mb-2">File Name</label>
        <div class="flex gap-2">
          <input
            id="filename"
            bind:this={inputRef}
            bind:value={fileName}
            onkeydown={handleKeydown}
            placeholder="document.md"
            class="flex-1 rounded-lg border border-zinc-700 bg-zinc-800 px-4 py-2 text-zinc-100 placeholder-zinc-600 outline-none focus:border-amber-500 transition-colors"
          />
          <Button 
            onclick={handleCreateEmpty}
            disabled={!fileName.trim()}
            class="bg-amber-600 hover:bg-amber-500"
          >
            New Empty File
          </Button>
        </div>
      </section>

      <!-- Templates -->
      <section>
        <label class="block text-xs font-bold uppercase tracking-wider text-zinc-500 mb-3">Templates</label>
        <div class="grid grid-cols-1 sm:grid-cols-2 gap-3">
          {#each FILE_TEMPLATES as template}
            <button
              onclick={() => handleTemplateSelect(template)}
              class="flex items-center gap-3 rounded-lg border border-zinc-800 bg-zinc-800/30 p-3 text-left hover:border-zinc-700 hover:bg-zinc-800 transition-all group"
            >
              <div class="rounded bg-zinc-800 p-2 text-zinc-500 group-hover:text-amber-500 transition-colors">
                <FileText class="h-4 w-4" />
              </div>
              <div>
                <div class="text-sm font-medium text-zinc-200">{template.title}</div>
                <div class="text-[10px] text-zinc-500">Quick start template</div>
              </div>
            </button>
          {/each}
        </div>
      </section>

      <!-- Drag & Drop -->
      <section>
        <label class="block text-xs font-bold uppercase tracking-wider text-zinc-500 mb-3">Import Files</label>
        <div
          oncontainerdragover={(e) => { e.preventDefault(); isDragging = true; }}
          oncontainerdragleave={() => isDragging = false}
          ondrop={handleDrop}
          class={cn(
            "relative flex flex-col items-center justify-center rounded-xl border-2 border-dashed p-8 transition-all",
            isDragging 
              ? "border-amber-500 bg-amber-500/5" 
              : "border-zinc-800 bg-zinc-800/10 hover:border-zinc-700"
          )}
        >
          <input
            type="file"
            multiple
            class="absolute inset-0 cursor-pointer opacity-0"
            onchange={(e) => handleFiles(e.currentTarget.files)}
          />
          <div class="mb-3 rounded-full bg-zinc-800 p-3 text-zinc-500">
            <Upload class="h-6 w-6" />
          </div>
          <p class="text-sm font-medium text-zinc-300">Click or drag files here to upload</p>
          <p class="mt-1 text-xs text-zinc-500 text-center">Supports markdown, text, and other code files</p>
        </div>
      </section>
    </div>
  </div>
</div>

