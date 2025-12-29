<script lang="ts">
  import FileText from '@lucide/svelte/icons/file-text';
  import ChevronDown from '@lucide/svelte/icons/chevron-down';
  import ChevronRight from '@lucide/svelte/icons/chevron-right';
  import Eye from '@lucide/svelte/icons/eye';
  import FolderOpen from '@lucide/svelte/icons/folder-open';
  import X from '@lucide/svelte/icons/x';
  import { agentStore } from '$lib/stores/index.js';

  // Local state
  let expanded = $state(false);
  let viewingFile = $state<string | null>(null);

  // Derived state
  const scratchFiles = $derived(agentStore.scratchFiles);
  const fileCount = $derived(Object.keys(scratchFiles).length);
  const filePaths = $derived(Object.keys(scratchFiles).sort());

  function getFileName(path: string): string {
    return path.split('/').pop() || path;
  }

  function getFileContent(path: string): string {
    const file = scratchFiles[path];
    if (!file?.content) return '';
    return file.content.join('\n');
  }

  function toggleExpanded() {
    expanded = !expanded;
  }

  function viewFile(path: string) {
    viewingFile = path;
  }

  function closeViewer() {
    viewingFile = null;
  }
</script>

{#if fileCount > 0}
  <div class="border-t border-zinc-800 bg-zinc-900/50">
    <!-- Header -->
    <button
      type="button"
      onclick={toggleExpanded}
      class="flex w-full items-center justify-between px-3 py-2 text-left hover:bg-zinc-800/50 transition-colors"
    >
      <div class="flex items-center gap-2">
        {#if expanded}
          <ChevronDown class="h-3.5 w-3.5 text-zinc-500" />
        {:else}
          <ChevronRight class="h-3.5 w-3.5 text-zinc-500" />
        {/if}
        <FolderOpen class="h-3.5 w-3.5 text-amber-500" />
        <span class="text-xs font-medium text-zinc-400">Agent Scratch Files</span>
      </div>
      <span class="text-[10px] text-zinc-600 bg-zinc-800 px-1.5 py-0.5 rounded">
        {fileCount}
      </span>
    </button>

    <!-- File List -->
    {#if expanded}
      <div class="px-3 pb-2 space-y-1">
        {#each filePaths as path}
          <button
            type="button"
            onclick={() => viewFile(path)}
            class="flex w-full items-center gap-2 px-2 py-1.5 rounded text-left text-xs hover:bg-zinc-800/70 transition-colors group"
          >
            <FileText class="h-3.5 w-3.5 text-zinc-500 flex-shrink-0" />
            <span class="text-zinc-400 truncate flex-1">{getFileName(path)}</span>
            <Eye class="h-3 w-3 text-zinc-600 opacity-0 group-hover:opacity-100 transition-opacity" />
          </button>
        {/each}
        <p class="text-[10px] text-zinc-600 px-2 pt-1 italic">
          Read-only: Agent's working memory
        </p>
      </div>
    {/if}
  </div>
{/if}

<!-- File Viewer Modal -->
{#if viewingFile}
  <div class="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm">
    <div class="w-full max-w-3xl mx-4 max-h-[80vh] flex flex-col rounded-xl border border-zinc-700 bg-zinc-900 shadow-2xl overflow-hidden">
      <!-- Modal Header -->
      <div class="flex items-center justify-between border-b border-zinc-700 bg-zinc-800/50 px-4 py-3">
        <div class="flex items-center gap-2">
          <FileText class="h-4 w-4 text-amber-500" />
          <span class="font-mono text-sm text-zinc-200">{viewingFile}</span>
        </div>
        <div class="flex items-center gap-2">
          <span class="text-[10px] text-zinc-500 bg-zinc-700/50 px-2 py-0.5 rounded">
            READ-ONLY
          </span>
          <button
            onclick={closeViewer}
            class="p-1 rounded text-zinc-400 hover:text-zinc-200 hover:bg-zinc-700"
          >
            <X class="h-4 w-4" />
          </button>
        </div>
      </div>

      <!-- File Content -->
      <div class="flex-1 overflow-y-auto p-4">
        <pre class="text-xs text-zinc-300 font-mono whitespace-pre-wrap break-words leading-relaxed">{getFileContent(viewingFile)}</pre>
      </div>
    </div>
  </div>
{/if}

