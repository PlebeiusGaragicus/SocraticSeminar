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
  import File from '@lucide/svelte/icons/file';
  import FileImage from '@lucide/svelte/icons/file-image';
  import Download from '@lucide/svelte/icons/download';
  import Loader2 from '@lucide/svelte/icons/loader-2';
  import Check from '@lucide/svelte/icons/check';
  import Copy from '@lucide/svelte/icons/copy';
  import type { Source } from '$lib/stores/types.js';
  import { sourceStore } from '$lib/stores/index.js';
  import { cn } from '$lib/utils.js';
  import Markdown from './Markdown.svelte';

  interface Props {
    source: Source;
  }

  let { source }: Props = $props();

  // Determine source type
  const isFileSource = $derived(source.sourceType === 'file');
  const isPdf = $derived(isFileSource && source.mimeType === 'application/pdf');
  const isImage = $derived(isFileSource && source.mimeType?.startsWith('image/'));
  const isText = $derived(isFileSource && (source.mimeType === 'text/plain' || source.mimeType === 'text/markdown'));

  // Check if preview PDF is available for URL sources
  const hasPreview = $derived(!isFileSource && source.previewBlobId);
  const hasPreviewError = $derived(!isFileSource && source.previewError);

  // Tab state
  type ViewTab = 'content' | 'preview';
  let activeTab = $state<ViewTab>('content');

  // Metadata expansion state
  let metadataExpanded = $state(true);

  // File blob state (for file sources)
  let blobUrl = $state<string | null>(null);
  let blobLoading = $state(false);
  let blobError = $state<string | null>(null);

  // Preview PDF blob state (for URL sources)
  let previewBlobUrl = $state<string | null>(null);
  let previewLoading = $state(false);
  let previewLoadError = $state<string | null>(null);

  // URL copy feedback
  let urlCopied = $state(false);

  const bibliography = $derived(source.bibliography);
  const hasBibliography = $derived(
    bibliography && (
      bibliography.author || 
      bibliography.publishedDate || 
      bibliography.publisher || 
      bibliography.resourceType
    )
  );

  // File info for file sources
  const fileInfo = $derived(() => {
    if (!isFileSource) return null;
    return {
      name: source.title,
      size: source.fileSize ? formatFileSize(source.fileSize) : 'Unknown size',
      type: source.mimeType || 'Unknown type',
    };
  });

  function formatFileSize(bytes: number): string {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  }

  async function copyUrlToClipboard() {
    try {
      await navigator.clipboard.writeText(source.url);
      urlCopied = true;
      setTimeout(() => {
        urlCopied = false;
      }, 2000);
    } catch (error) {
      console.error('Failed to copy URL:', error);
    }
  }

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

  async function loadBlob() {
    if (!source.blobId || blobUrl) return;
    
    blobLoading = true;
    blobError = null;
    
    try {
      const blob = await sourceStore.getSourceBlob(source.id);
      if (blob) {
        blobUrl = URL.createObjectURL(blob);
      } else {
        blobError = 'File not found in storage';
      }
    } catch (error) {
      blobError = error instanceof Error ? error.message : 'Failed to load file';
    } finally {
      blobLoading = false;
    }
  }

  async function loadPreviewBlob() {
    if (!source.previewBlobId || previewBlobUrl) return;
    
    previewLoading = true;
    previewLoadError = null;
    
    try {
      const blob = await sourceStore.getPreviewBlob(source.id);
      if (blob) {
        previewBlobUrl = URL.createObjectURL(blob);
      } else {
        previewLoadError = 'Preview PDF not found in storage';
      }
    } catch (error) {
      previewLoadError = error instanceof Error ? error.message : 'Failed to load preview';
    } finally {
      previewLoading = false;
    }
  }

  async function downloadFile() {
    if (!blobUrl) {
      await loadBlob();
    }
    
    if (blobUrl) {
      const a = document.createElement('a');
      a.href = blobUrl;
      a.download = source.title;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
    }
  }

  // Load blob when switching to file source
  $effect(() => {
    if (isFileSource && source.blobId && !blobUrl && !blobLoading) {
      loadBlob();
    }
  });

  // Load preview blob when switching to preview tab for URL sources
  $effect(() => {
    if (!isFileSource && activeTab === 'preview' && source.previewBlobId && !previewBlobUrl && !previewLoading) {
      loadPreviewBlob();
    }
  });

  // Cleanup blob URLs on unmount
  $effect(() => {
    return () => {
      if (blobUrl) {
        URL.revokeObjectURL(blobUrl);
      }
      if (previewBlobUrl) {
        URL.revokeObjectURL(previewBlobUrl);
      }
    };
  });

  // Revoke old blob URLs when source changes
  $effect(() => {
    const _id = source.id;
    return () => {
      if (blobUrl) {
        URL.revokeObjectURL(blobUrl);
        blobUrl = null;
      }
      if (previewBlobUrl) {
        URL.revokeObjectURL(previewBlobUrl);
        previewBlobUrl = null;
      }
      previewLoadError = null;
    };
  });
</script>

<div class="flex h-full flex-col bg-zinc-950 overflow-hidden">
  <!-- Header Bar -->
  <div class="flex items-center border-b border-zinc-800 bg-zinc-900/50 px-4 py-2.5 gap-4">
    <div class="flex items-center gap-3 min-w-0 flex-shrink overflow-hidden">
      {#if isFileSource}
        {#if isPdf}
          <File class="h-4 w-4 flex-shrink-0 text-red-400" />
        {:else if isImage}
          <FileImage class="h-4 w-4 flex-shrink-0 text-purple-400" />
        {:else}
          <FileText class="h-4 w-4 flex-shrink-0 text-green-400" />
        {/if}
      {:else}
        <Globe class="h-4 w-4 flex-shrink-0 text-blue-400" />
      {/if}
      <div class="min-w-0 overflow-hidden">
        <h2 class="text-sm font-medium text-zinc-100 truncate">{source.title}</h2>
        {#if isFileSource}
          <span class="text-xs text-zinc-500">
            {fileInfo()?.size} · {fileInfo()?.type}
          </span>
        {:else}
          <button 
            onclick={copyUrlToClipboard}
            class="text-xs text-zinc-500 hover:text-blue-400 transition-colors text-left flex items-center gap-1.5 group max-w-full"
            title="Click to copy URL"
          >
            <span class="truncate">{source.url}</span>
            {#if urlCopied}
              <Check class="h-3 w-3 text-green-400 flex-shrink-0" />
            {:else}
              <Copy class="h-3 w-3 opacity-0 group-hover:opacity-100 flex-shrink-0 transition-opacity" />
            {/if}
          </button>
        {/if}
      </div>
    </div>
    
    {#if !isFileSource}
      <!-- Tab Switcher (only for URL sources) -->
      <div class="flex items-center gap-1 rounded-lg bg-zinc-800/50 p-1 flex-shrink-0">
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
              : "text-zinc-400 hover:text-zinc-200",
            !hasPreview && hasPreviewError && "opacity-60"
          )}
        >
          <Monitor class="h-3.5 w-3.5" />
          Preview
        </button>
      </div>
    {/if}

    {#if isFileSource}
      <button 
        onclick={downloadFile}
        class="flex items-center gap-1.5 rounded-md bg-zinc-800 px-3 py-1.5 text-xs font-medium text-zinc-300 hover:bg-zinc-700 hover:text-zinc-100 transition-colors flex-shrink-0"
      >
        <Download class="h-3 w-3" />
        <span>Download</span>
      </button>
    {:else}
      <a 
        href={source.url} 
        target="_blank" 
        rel="noopener noreferrer"
        class="flex items-center gap-1.5 rounded-md bg-zinc-800 px-3 py-1.5 text-xs font-medium text-zinc-300 hover:bg-zinc-700 hover:text-zinc-100 transition-colors flex-shrink-0"
      >
        <span>Open Original</span>
        <ExternalLink class="h-3 w-3" />
      </a>
    {/if}
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
    {#if isFileSource}
      <!-- File Source Content -->
      {#if blobLoading}
        <div class="absolute inset-0 flex items-center justify-center bg-zinc-950">
          <div class="text-center">
            <Loader2 class="h-8 w-8 animate-spin text-blue-500 mx-auto mb-3" />
            <p class="text-sm text-zinc-500">Loading file...</p>
          </div>
        </div>
      {:else if blobError}
        <div class="absolute inset-0 flex items-center justify-center bg-zinc-950">
          <div class="text-center max-w-md px-6">
            <AlertCircle class="h-10 w-10 text-red-500 mx-auto mb-3" />
            <h3 class="text-base font-medium text-zinc-200 mb-2">Failed to Load File</h3>
            <p class="text-sm text-zinc-500">{blobError}</p>
          </div>
        </div>
      {:else if isPdf && blobUrl}
        <!-- PDF Viewer using native embed -->
        <object
          data={blobUrl}
          type="application/pdf"
          class="absolute inset-0 w-full h-full"
          title={source.title}
        >
          <div class="absolute inset-0 flex items-center justify-center bg-zinc-950">
            <div class="text-center max-w-md px-6">
              <File class="h-10 w-10 text-red-400 mx-auto mb-3" />
              <h3 class="text-base font-medium text-zinc-200 mb-2">PDF Preview Not Available</h3>
              <p class="text-sm text-zinc-500 mb-4">
                Your browser doesn't support inline PDF viewing.
              </p>
              <button 
                onclick={downloadFile}
                class="inline-flex items-center gap-2 rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-500 transition-colors"
              >
                <Download class="h-4 w-4" />
                <span>Download PDF</span>
              </button>
            </div>
          </div>
        </object>
      {:else if isImage && blobUrl}
        <!-- Image Viewer -->
        <div class="absolute inset-0 overflow-auto flex items-center justify-center bg-zinc-900/50 p-8">
          <img
            src={blobUrl}
            alt={source.title}
            class="max-w-full max-h-full object-contain rounded-lg shadow-xl"
          />
        </div>
      {:else if isText}
        <!-- Text/Markdown Content -->
        <div class="absolute inset-0 overflow-y-auto">
          <div class="max-w-4xl mx-auto px-8 py-6">
            <Markdown content={source.content} />
          </div>
        </div>
      {:else}
        <!-- Unknown file type fallback -->
        <div class="absolute inset-0 flex items-center justify-center bg-zinc-950">
          <div class="text-center max-w-md px-6">
            <File class="h-10 w-10 text-zinc-500 mx-auto mb-3" />
            <h3 class="text-base font-medium text-zinc-200 mb-2">{source.title}</h3>
            <p class="text-sm text-zinc-500 mb-4">
              This file type cannot be previewed in the browser.
            </p>
            <button 
              onclick={downloadFile}
              class="inline-flex items-center gap-2 rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-500 transition-colors"
            >
              <Download class="h-4 w-4" />
              <span>Download File</span>
            </button>
          </div>
        </div>
      {/if}
    {:else if activeTab === 'content'}
      <!-- Markdown Content View (URL sources) -->
      <div class="absolute inset-0 overflow-y-auto">
        <div class="max-w-4xl mx-auto px-8 py-6">
          <Markdown content={source.content} />
        </div>
      </div>
    {:else}
      <!-- PDF Preview View (URL sources) -->
      <div class="absolute inset-0 flex flex-col">
        {#if previewLoading}
          <div class="absolute inset-0 flex items-center justify-center bg-zinc-950">
            <div class="text-center">
              <Loader2 class="h-8 w-8 animate-spin text-blue-500 mx-auto mb-3" />
              <p class="text-sm text-zinc-500">Loading preview...</p>
            </div>
          </div>
        {:else if hasPreviewError || previewLoadError}
          <!-- Preview generation failed or loading failed - show error with fallback -->
          <div class="absolute inset-0 flex items-center justify-center bg-zinc-950">
            <div class="text-center max-w-md px-6">
              <AlertCircle class="h-10 w-10 text-amber-500 mx-auto mb-3" />
              <h3 class="text-base font-medium text-zinc-200 mb-2">Preview Unavailable</h3>
              <p class="text-sm text-zinc-500 mb-4">
                {source.previewError || previewLoadError || 'Could not generate preview for this page.'}
              </p>
              <div class="flex gap-3 justify-center">
                <button
                  onclick={() => activeTab = 'content'}
                  class="inline-flex items-center gap-2 rounded-lg bg-zinc-700 px-4 py-2 text-sm font-medium text-zinc-200 hover:bg-zinc-600 transition-colors"
                >
                  <FileText class="h-4 w-4" />
                  <span>View Content</span>
                </button>
                <a 
                  href={source.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  class="inline-flex items-center gap-2 rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-500 transition-colors"
                >
                  <span>Open Original</span>
                  <ExternalLink class="h-4 w-4" />
                </a>
              </div>
            </div>
          </div>
        {:else if !hasPreview}
          <!-- No preview available (older source without PDF) -->
          <div class="absolute inset-0 flex items-center justify-center bg-zinc-950">
            <div class="text-center max-w-md px-6">
              <Monitor class="h-10 w-10 text-zinc-500 mx-auto mb-3" />
              <h3 class="text-base font-medium text-zinc-200 mb-2">No Preview Available</h3>
              <p class="text-sm text-zinc-500 mb-4">
                This source was added before preview capture was enabled.
              </p>
              <div class="flex gap-3 justify-center">
                <button
                  onclick={() => activeTab = 'content'}
                  class="inline-flex items-center gap-2 rounded-lg bg-zinc-700 px-4 py-2 text-sm font-medium text-zinc-200 hover:bg-zinc-600 transition-colors"
                >
                  <FileText class="h-4 w-4" />
                  <span>View Content</span>
                </button>
                <a 
                  href={source.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  class="inline-flex items-center gap-2 rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-500 transition-colors"
                >
                  <span>Open Original</span>
                  <ExternalLink class="h-4 w-4" />
                </a>
              </div>
            </div>
          </div>
        {:else if previewBlobUrl}
          <!-- PDF Preview -->
          <object
            data={previewBlobUrl}
            type="application/pdf"
            class="absolute inset-0 w-full h-full"
            title="{source.title} - Preview"
          >
            <div class="absolute inset-0 flex items-center justify-center bg-zinc-950">
              <div class="text-center max-w-md px-6">
                <File class="h-10 w-10 text-red-400 mx-auto mb-3" />
                <h3 class="text-base font-medium text-zinc-200 mb-2">PDF Preview Not Supported</h3>
                <p class="text-sm text-zinc-500 mb-4">
                  Your browser doesn't support inline PDF viewing.
                </p>
                <a 
                  href={source.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  class="inline-flex items-center gap-2 rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-500 transition-colors"
                >
                  <span>Open Original</span>
                  <ExternalLink class="h-4 w-4" />
                </a>
              </div>
            </div>
          </object>
        {:else}
          <!-- Loading state fallback -->
          <div class="absolute inset-0 flex items-center justify-center bg-zinc-950">
            <div class="text-center">
              <Loader2 class="h-8 w-8 animate-spin text-blue-500 mx-auto mb-3" />
              <p class="text-sm text-zinc-500">Loading preview...</p>
            </div>
          </div>
        {/if}
      </div>
    {/if}
  </div>

  <!-- Footer with scraped timestamp -->
  <div class="border-t border-zinc-800 px-4 py-1.5 flex items-center justify-between text-[10px] text-zinc-600">
    <span>
      {#if isFileSource}
        {#if source.fileHash}
          SHA256: {source.fileHash.slice(0, 16)}...
        {/if}
      {:else if source.scrapedAt}
        Scraped {new Date(source.scrapedAt).toLocaleDateString()} at {new Date(source.scrapedAt).toLocaleTimeString()}
      {:else}
        Added {new Date(source.createdAt).toLocaleDateString()}
      {/if}
    </span>
    <span class="uppercase tracking-wider font-medium text-zinc-700">Read Only</span>
  </div>
</div>
