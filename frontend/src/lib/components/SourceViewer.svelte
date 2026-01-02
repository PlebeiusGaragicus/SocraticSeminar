<script lang="ts">
  import Globe from '@lucide/svelte/icons/globe';
  import ExternalLink from '@lucide/svelte/icons/external-link';
  import FileText from '@lucide/svelte/icons/file-text';
  import Monitor from '@lucide/svelte/icons/monitor';
  import ChevronDown from '@lucide/svelte/icons/chevron-down';
  import ChevronRight from '@lucide/svelte/icons/chevron-right';
  import User from '@lucide/svelte/icons/user';
  import Calendar from '@lucide/svelte/icons/calendar';
  import Building from '@lucide/svelte/icons/building';
  import Tag from '@lucide/svelte/icons/tag';
  import AlertCircle from '@lucide/svelte/icons/alert-circle';
  import type { Source } from '$lib/stores/types.js';
  import { cn } from '$lib/utils.js';
  import Markdown from './Markdown.svelte';

  interface Props {
    source: Source;
  }

  let { source }: Props = $props();

  // Tab state
  type ViewTab = 'content' | 'preview';
  let activeTab = $state<ViewTab>('content');

  // Metadata expansion state
  let metadataExpanded = $state(true);

  // Iframe loading state
  let iframeLoaded = $state(false);
  let iframeError = $state(false);

  const bibliography = $derived(source.bibliography);
  const hasBibliography = $derived(
    bibliography && (
      bibliography.author || 
      bibliography.publishedDate || 
      bibliography.publisher || 
      bibliography.resourceType
    )
  );

  function formatDate(dateStr: string | undefined): string {
    if (!dateStr) return '';
    try {
      const date = new Date(dateStr);
      if (isNaN(date.getTime())) return dateStr;
      return date.toLocaleDateString('en-US', {
        year: 'numeric',
        month: 'long',
        day: 'numeric'
      });
    } catch {
      return dateStr;
    }
  }

  function handleIframeLoad() {
    iframeLoaded = true;
  }

  function handleIframeError() {
    iframeError = true;
    iframeLoaded = true;
  }

  // Reset iframe state when source changes
  $effect(() => {
    if (source.url) {
      iframeLoaded = false;
      iframeError = false;
    }
  });
</script>

<div class="flex h-full flex-col bg-zinc-950 overflow-hidden">
  <!-- Header Bar -->
  <div class="flex items-center justify-between border-b border-zinc-800 bg-zinc-900/50 px-4 py-2.5">
    <div class="flex items-center gap-3 min-w-0 flex-1">
      <Globe class="h-4 w-4 flex-shrink-0 text-blue-400" />
      <div class="min-w-0 flex-1">
        <h2 class="text-sm font-medium text-zinc-100 truncate">{source.title}</h2>
        <a 
          href={source.url}
          target="_blank"
          rel="noopener noreferrer"
          class="text-xs text-zinc-500 hover:text-blue-400 truncate block transition-colors"
        >
          {source.url}
        </a>
      </div>
    </div>
    
    <!-- Tab Switcher -->
    <div class="flex items-center gap-1 rounded-lg bg-zinc-800/50 p-1 mx-4">
      <button
        onclick={() => activeTab = 'content'}
        class={cn(
          "flex items-center gap-1.5 rounded-md px-3 py-1.5 text-xs font-medium transition-all",
          activeTab === 'content'
            ? "bg-zinc-700 text-zinc-100 shadow-sm"
            : "text-zinc-400 hover:text-zinc-200"
        )}
      >
        <FileText class="h-3.5 w-3.5" />
        Content
      </button>
      <button
        onclick={() => activeTab = 'preview'}
        class={cn(
          "flex items-center gap-1.5 rounded-md px-3 py-1.5 text-xs font-medium transition-all",
          activeTab === 'preview'
            ? "bg-zinc-700 text-zinc-100 shadow-sm"
            : "text-zinc-400 hover:text-zinc-200"
        )}
      >
        <Monitor class="h-3.5 w-3.5" />
        Preview
      </button>
    </div>

    <a 
      href={source.url} 
      target="_blank" 
      rel="noopener noreferrer"
      class="flex items-center gap-1.5 rounded-md bg-zinc-800 px-3 py-1.5 text-xs font-medium text-zinc-300 hover:bg-zinc-700 hover:text-zinc-100 transition-colors flex-shrink-0"
    >
      <span>Open Original</span>
      <ExternalLink class="h-3 w-3" />
    </a>
  </div>

  <!-- Collapsible Metadata Section -->
  {#if hasBibliography}
    <div class="border-b border-zinc-800">
      <button
        onclick={() => metadataExpanded = !metadataExpanded}
        class="flex w-full items-center gap-2 px-4 py-2 text-left text-xs font-medium text-zinc-400 hover:bg-zinc-900/50 transition-colors"
      >
        {#if metadataExpanded}
          <ChevronDown class="h-3.5 w-3.5" />
        {:else}
          <ChevronRight class="h-3.5 w-3.5" />
        {/if}
        <span class="uppercase tracking-wider">Citation Info</span>
      </button>
      
      {#if metadataExpanded}
        <div class="px-4 pb-3 grid grid-cols-2 md:grid-cols-4 gap-3">
          {#if bibliography?.author}
            <div class="flex items-start gap-2">
              <User class="h-3.5 w-3.5 text-zinc-500 mt-0.5 flex-shrink-0" />
              <div>
                <div class="text-[10px] uppercase tracking-wider text-zinc-600">Author</div>
                <div class="text-xs text-zinc-300">{bibliography.author}</div>
              </div>
            </div>
          {/if}
          
          {#if bibliography?.publishedDate}
            <div class="flex items-start gap-2">
              <Calendar class="h-3.5 w-3.5 text-zinc-500 mt-0.5 flex-shrink-0" />
              <div>
                <div class="text-[10px] uppercase tracking-wider text-zinc-600">Published</div>
                <div class="text-xs text-zinc-300">{formatDate(bibliography.publishedDate)}</div>
              </div>
            </div>
          {/if}
          
          {#if bibliography?.publisher}
            <div class="flex items-start gap-2">
              <Building class="h-3.5 w-3.5 text-zinc-500 mt-0.5 flex-shrink-0" />
              <div>
                <div class="text-[10px] uppercase tracking-wider text-zinc-600">Publisher</div>
                <div class="text-xs text-zinc-300">{bibliography.publisher}</div>
              </div>
            </div>
          {/if}
          
          {#if bibliography?.resourceType}
            <div class="flex items-start gap-2">
              <Tag class="h-3.5 w-3.5 text-zinc-500 mt-0.5 flex-shrink-0" />
              <div>
                <div class="text-[10px] uppercase tracking-wider text-zinc-600">Type</div>
                <div class="text-xs text-zinc-300">{bibliography.resourceType}</div>
              </div>
            </div>
          {/if}
        </div>
      {/if}
    </div>
  {/if}

  <!-- Content Area -->
  <div class="flex-1 overflow-hidden relative">
    {#if activeTab === 'content'}
      <!-- Markdown Content View -->
      <div class="absolute inset-0 overflow-y-auto">
        <div class="max-w-4xl mx-auto px-8 py-6">
          <Markdown content={source.content} />
        </div>
      </div>
    {:else}
      <!-- Iframe Preview View -->
      <div class="absolute inset-0 flex flex-col">
        {#if !iframeLoaded}
          <div class="absolute inset-0 flex items-center justify-center bg-zinc-950">
            <div class="text-center">
              <div class="mb-3 h-6 w-6 animate-spin rounded-full border-2 border-zinc-600 border-t-blue-500 mx-auto"></div>
              <p class="text-sm text-zinc-500">Loading preview...</p>
            </div>
          </div>
        {/if}
        
        {#if iframeError}
          <div class="absolute inset-0 flex items-center justify-center bg-zinc-950">
            <div class="text-center max-w-md px-6">
              <AlertCircle class="h-10 w-10 text-amber-500 mx-auto mb-3" />
              <h3 class="text-base font-medium text-zinc-200 mb-2">Preview Unavailable</h3>
              <p class="text-sm text-zinc-500 mb-4">
                This website prevents embedding in iframes for security reasons.
              </p>
              <a 
                href={source.url}
                target="_blank"
                rel="noopener noreferrer"
                class="inline-flex items-center gap-2 rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-500 transition-colors"
              >
                <span>Open in New Tab</span>
                <ExternalLink class="h-4 w-4" />
              </a>
            </div>
          </div>
        {:else}
          <iframe
            src={source.url}
            title="Source preview"
            class={cn(
              "flex-1 w-full bg-white",
              !iframeLoaded && "opacity-0"
            )}
            sandbox="allow-scripts allow-same-origin allow-popups"
            onload={handleIframeLoad}
            onerror={handleIframeError}
          ></iframe>
        {/if}
      </div>
    {/if}
  </div>

  <!-- Footer with scraped timestamp -->
  <div class="border-t border-zinc-800 px-4 py-1.5 flex items-center justify-between text-[10px] text-zinc-600">
    <span>
      {#if source.scrapedAt}
        Scraped {new Date(source.scrapedAt).toLocaleDateString()} at {new Date(source.scrapedAt).toLocaleTimeString()}
      {:else}
        Added {new Date(source.createdAt).toLocaleDateString()}
      {/if}
    </span>
    <span class="uppercase tracking-wider font-medium text-zinc-700">Read Only</span>
  </div>
</div>

