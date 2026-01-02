<script lang="ts">
  import X from '@lucide/svelte/icons/x';
  import Globe from '@lucide/svelte/icons/globe';
  import Link from '@lucide/svelte/icons/link';
  import Sparkles from '@lucide/svelte/icons/sparkles';
  import Loader2 from '@lucide/svelte/icons/loader-2';
  import AlertCircle from '@lucide/svelte/icons/alert-circle';
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
  let isProcessing = $state(false);
  let processedCount = $state(0);
  let totalCount = $state(0);

  function extractTitle(html: string, url: string): string {
    // Try to extract title from HTML
    const titleMatch = html.match(/<title[^>]*>([^<]+)<\/title>/i);
    if (titleMatch && titleMatch[1]) {
      return titleMatch[1].trim();
    }
    
    // Try og:title
    const ogTitleMatch = html.match(/<meta[^>]*property=["']og:title["'][^>]*content=["']([^"']+)["']/i) ||
                         html.match(/<meta[^>]*content=["']([^"']+)["'][^>]*property=["']og:title["']/i);
    if (ogTitleMatch && ogTitleMatch[1]) {
      return ogTitleMatch[1].trim();
    }
    
    // Fallback to last path segment or domain
    try {
      const urlObj = new URL(url);
      const pathParts = urlObj.pathname.split('/').filter(p => p.length > 0);
      if (pathParts.length > 0) {
        const lastPart = pathParts[pathParts.length - 1];
        // Remove file extensions and decode
        return decodeURIComponent(lastPart.replace(/\.[^/.]+$/, '').replace(/[-_]/g, ' '));
      }
      return urlObj.hostname;
    } catch {
      return url;
    }
  }

  function extractTextContent(html: string): string {
    // Remove script and style elements
    let cleaned = html.replace(/<script[^>]*>[\s\S]*?<\/script>/gi, '');
    cleaned = cleaned.replace(/<style[^>]*>[\s\S]*?<\/style>/gi, '');
    cleaned = cleaned.replace(/<nav[^>]*>[\s\S]*?<\/nav>/gi, '');
    cleaned = cleaned.replace(/<footer[^>]*>[\s\S]*?<\/footer>/gi, '');
    cleaned = cleaned.replace(/<header[^>]*>[\s\S]*?<\/header>/gi, '');
    
    // Create a temporary element to extract text
    const tempDiv = document.createElement('div');
    tempDiv.innerHTML = cleaned;
    
    // Get text content
    let text = tempDiv.textContent || tempDiv.innerText || '';
    
    // Clean up whitespace
    text = text.replace(/\s+/g, ' ').trim();
    
    return text;
  }

  async function handleAddUrls() {
    const urls = urlList.split('\n').map(u => u.trim()).filter(u => u.length > 0 && u.startsWith('http'));
    if (urls.length === 0 || !projectStore.currentProjectId) return;

    isProcessing = true;
    processedCount = 0;
    totalCount = urls.length;
    
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
          const title = extractTitle(html, url);
          const textContent = extractTextContent(html);
          
          const source = sourceStore.createSource(
            projectId,
            title,
            url,
            `# ${title}\n\n${textContent.slice(0, 10000)}`,
            { scrapedAt: Date.now() }
          );
          workspaceStore.openItem(source.id, 'source', column);
        } else {
          const source = sourceStore.createSource(
            projectId,
            extractTitle('', url),
            url,
            `# ${url}\n\nFailed to fetch content from this URL (HTTP ${response.status}).\n\nTip: Ask the agent to scrape this URL for better results.`,
            { scrapedAt: Date.now() }
          );
          workspaceStore.openItem(source.id, 'source', column);
        }
      } catch (error) {
        console.error('Failed to add URL:', url, error);
        const errorMsg = error instanceof Error ? error.message : String(error);
        const isCors = errorMsg.includes('CORS') || errorMsg.includes('Failed to fetch');
        
        const source = sourceStore.createSource(
          projectId,
          extractTitle('', url),
          url,
          `# ${url}\n\n${isCors ? '**CORS Error**: This website blocks direct browser access.' : `Error: ${errorMsg}`}\n\n**Tip**: Ask the research agent to scrape this URL:\n\n> "Please add this URL as a source: ${url}"`,
          { scrapedAt: Date.now() }
        );
        workspaceStore.openItem(source.id, 'source', column);
      }
      
      processedCount++;
    }
    
    isProcessing = false;
    onClose();
  }

  function handleKeydown(e: KeyboardEvent) {
    if (e.key === 'Escape' && !isProcessing) {
      onClose();
    }
  }

  function handleBackdropClick(e: MouseEvent) {
    if (e.target === e.currentTarget && !isProcessing) {
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
        disabled={isProcessing}
        class="rounded-lg p-1 text-zinc-500 hover:bg-zinc-700 hover:text-zinc-200 transition-colors disabled:opacity-50"
      >
        <X class="h-5 w-5" />
      </button>
    </div>

    <div class="overflow-y-auto p-6 space-y-6">
      <!-- URL List Section -->
      <section>
        <label for="urls" class="block text-xs font-bold uppercase tracking-wider text-zinc-500 mb-2">
          Quick Add URLs (one per line)
        </label>
        <div class="space-y-3">
          <textarea
            id="urls"
            bind:this={inputRef}
            bind:value={urlList}
            disabled={isProcessing}
            placeholder="https://example.com/article1&#10;https://example.com/article2"
            class="w-full h-32 rounded-lg border border-zinc-700 bg-zinc-800 px-4 py-3 text-zinc-100 placeholder-zinc-600 outline-none focus:border-blue-500 transition-colors font-mono text-sm resize-none disabled:opacity-50"
          ></textarea>
          
          <div class="flex items-center justify-between">
            <div class="flex items-center gap-2 text-xs text-zinc-500">
              <AlertCircle class="h-3.5 w-3.5" />
              <span>Some sites may block direct access (CORS)</span>
            </div>
            <Button 
              onclick={handleAddUrls}
              disabled={!urlList.trim() || isProcessing}
              class="bg-blue-600 hover:bg-blue-500"
            >
              {#if isProcessing}
                <Loader2 class="h-4 w-4 mr-2 animate-spin" />
                {processedCount}/{totalCount}
              {:else}
                <Link class="h-4 w-4 mr-2" />
                Quick Add
              {/if}
            </Button>
          </div>
        </div>
      </section>

      <!-- Agent Tip -->
      <div class="rounded-lg border border-amber-500/20 bg-amber-500/5 p-4">
        <div class="flex gap-3">
          <Sparkles class="h-5 w-5 text-amber-400 flex-shrink-0 mt-0.5" />
          <div class="space-y-2">
            <h4 class="text-sm font-medium text-amber-200">Smart Scrape with Agent</h4>
            <p class="text-xs text-zinc-400 leading-relaxed">
              For better results with metadata extraction, ask the research agent in chat:
            </p>
            <div class="rounded bg-zinc-800/80 px-3 py-2 font-mono text-xs text-zinc-300">
              "Please add this URL as a source: https://..."
            </div>
            <p class="text-xs text-zinc-500">
              The agent will extract author, publication date, and other citation info.
            </p>
          </div>
        </div>
      </div>
    </div>
  </div>
</div>
