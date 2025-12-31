<script lang="ts">
  import X from '@lucide/svelte/icons/x';
  import Globe from '@lucide/svelte/icons/globe';
  import Link from '@lucide/svelte/icons/link';
  import Search from '@lucide/svelte/icons/search';
  import Plus from '@lucide/svelte/icons/plus';
  import Loader2 from '@lucide/svelte/icons/loader-2';
  import { Button } from './ui/index.js';
  import { sourceStore, projectStore, workspaceStore } from '$lib/stores/index.js';
  import { cn } from '$lib/utils.js';
  import { onMount } from 'svelte';

  interface Props {
    column?: 'left' | 'right';
    onClose: () => void;
  }

  let { column = 'left', onClose }: Props = $props();

  let urlList = $state('');
  let inputRef: HTMLTextAreaElement;

  async function handleAddUrls() {
    const urls = urlList.split('\n').map(u => u.trim()).filter(u => u.length > 0);
    if (urls.length === 0 || !projectStore.currentProjectId) return;

    const projectId = projectStore.currentProjectId;
    
    for (const url of urls) {
      try {
        const response = await fetch(url, {
          method: 'GET',
          headers: {
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
          },
          mode: 'cors' 
        });
        
        if (response.ok) {
          const html = await response.text();
          const tempDiv = document.createElement('div');
          tempDiv.innerHTML = html;
          const textContent = tempDiv.textContent || tempDiv.innerText || '';
          
          const source = sourceStore.createSource(
            projectId,
            url.split('/').pop() || url,
            url,
            `# ${url}\n\n${textContent.slice(0, 5000)}`
          );
          workspaceStore.openItem(source.id, 'source', column);
        } else {
          const source = sourceStore.createSource(
            projectId,
            url.split('/').pop() || url,
            url,
            `# ${url}\n\nFailed to fetch content from this URL (HTTP ${response.status}).`
          );
          workspaceStore.openItem(source.id, 'source', column);
        }
      } catch (error) {
        console.error('Failed to add URL:', url, error);
        const source = sourceStore.createSource(
          projectId,
          url.split('/').pop() || url,
          url,
          `# ${url}\n\nError fetching content: ${error instanceof Error ? error.message : String(error)}`
        );
        workspaceStore.openItem(source.id, 'source', column);
      }
    }
    onClose();
  }

  function handleKeydown(e: KeyboardEvent) {
    if (e.key === 'Escape') {
      onClose();
    }
  }

  function handleBackdropClick(e: MouseEvent) {
    if (e.target === e.currentTarget) {
      onClose();
    }
  }

  onMount(() => {
    inputRef?.focus();
  });
</script>

<div 
  class="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4"
  onclick={handleBackdropClick}
>
  <div 
    class="w-full max-w-2xl rounded-xl border border-zinc-800 bg-zinc-900 shadow-2xl overflow-hidden flex flex-col max-h-[90vh]"
    role="dialog"
    aria-modal="true"
    onkeydown={handleKeydown}
  >
    <!-- Header -->
    <div class="flex items-center justify-between border-b border-zinc-800 px-4 py-3 bg-zinc-800/50">
      <div class="flex items-center gap-2">
        <Globe class="h-5 w-5 text-blue-500" />
        <h3 class="font-semibold text-zinc-100">Add New Sources</h3>
      </div>
      <button 
        onclick={onClose}
        class="rounded-lg p-1 text-zinc-500 hover:bg-zinc-700 hover:text-zinc-200 transition-colors"
      >
        <X class="h-5 w-5" />
      </button>
    </div>

    <div class="overflow-y-auto p-6 space-y-8">
      <!-- URL List Section -->
      <section>
        <label for="urls" class="block text-xs font-bold uppercase tracking-wider text-zinc-500 mb-2">Direct URLs (one per line)</label>
        <div class="space-y-3">
          <textarea
            id="urls"
            bind:this={inputRef}
            bind:value={urlList}
            placeholder="https://example.com/article1&#10;https://example.com/article2"
            class="w-full h-32 rounded-lg border border-zinc-700 bg-zinc-800 px-4 py-3 text-zinc-100 placeholder-zinc-600 outline-none focus:border-blue-500 transition-colors font-mono text-sm resize-none"
          ></textarea>
          <div class="flex justify-end">
            <Button 
              onclick={handleAddUrls}
              disabled={!urlList.trim()}
              class="bg-blue-600 hover:bg-blue-500"
            >
              <Link class="h-4 w-4 mr-2" />
              Add URLs
            </Button>
          </div>
        </div>
      </section>

      <div class="flex items-center gap-4 py-2">
        <div class="h-px flex-1 bg-zinc-800"></div>
        <span class="text-xs font-bold text-zinc-600">OR</span>
        <div class="h-px flex-1 bg-zinc-800"></div>
      </div>

      <!-- Web Search Section (Demo Only) -->
      <section class="opacity-50 pointer-events-none">
        <div class="flex items-center justify-between mb-2">
          <label for="search" class="block text-xs font-bold uppercase tracking-wider text-zinc-500">Web Search (Demo Only)</label>
          <span class="rounded bg-zinc-800 px-1.5 py-0.5 text-[10px] font-medium text-zinc-400">Coming Soon</span>
        </div>
        <div class="space-y-4">
          <div class="flex gap-2">
            <div class="relative flex-1">
              <Search class="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-zinc-500" />
              <input
                id="search"
                disabled
                placeholder="Search for research papers, articles..."
                class="w-full rounded-lg border border-zinc-700 bg-zinc-800 py-2 pl-10 pr-4 text-zinc-100 placeholder-zinc-600 outline-none transition-colors"
              />
            </div>
            <Button 
              variant="outline"
              disabled
              class="border-zinc-700 bg-zinc-800"
            >
              Search
            </Button>
          </div>
        </div>
      </section>
    </div>
  </div>
</div>

