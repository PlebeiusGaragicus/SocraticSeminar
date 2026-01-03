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
  import Upload from '@lucide/svelte/icons/upload';
  import Loader2 from '@lucide/svelte/icons/loader-2';
  import Check from '@lucide/svelte/icons/check';
  import Copy from '@lucide/svelte/icons/copy';
  import RefreshCw from '@lucide/svelte/icons/refresh-cw';
  import X from '@lucide/svelte/icons/x';
  import Sparkles from '@lucide/svelte/icons/sparkles';
  import PenLine from '@lucide/svelte/icons/pen-line';
  import Clock from '@lucide/svelte/icons/clock';
  import Camera from '@lucide/svelte/icons/camera';
  import type { Source, ContentCrawlMethod, PreviewCrawlMethod } from '$lib/stores/types.js';
  import { sourceStore } from '$lib/stores/index.js';
  import { cn } from '$lib/utils.js';
  import { onDestroy } from 'svelte';
  import { toast } from 'svelte-sonner';
  import { nanoid } from 'nanoid';
  import { db } from '$lib/services/indexeddb.js';
  import Markdown from './Markdown.svelte';
  import { Button } from './ui/index.js';
  
  // Backend URL for scraping service
  const BACKEND_URL = import.meta.env.PUBLIC_BACKEND_URL ?? 'http://localhost:8000';

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

  // PDF upload state
  let pdfUploadInputRef: HTMLInputElement;
  let isUploadingPdf = $state(false);
  
  // Re-scrape modal state
  let showRescrapeModal = $state(false);
  let rescrapeTarget = $state<'content' | 'preview' | 'both'>('both');
  let selectedContentMethod = $state<ContentCrawlMethod>('markdownify');
  let selectedPreviewMethod = $state<PreviewCrawlMethod>('weasyprint');
  let isRescraping = $state(false);
  let manualContentInput = $state('');
  
  // Re-scrape timeout/countdown state (like NewSourcesModal)
  const RESCRAPE_TIMEOUT_SECONDS = 60;  // Longer timeout for re-scrape
  let rescrapeCountdown = $state(RESCRAPE_TIMEOUT_SECONDS);
  let rescrapeCountdownInterval: ReturnType<typeof setInterval> | null = null;
  
  // Cleanup countdown interval on destroy
  onDestroy(() => {
    if (rescrapeCountdownInterval) clearInterval(rescrapeCountdownInterval);
  });
  
  function startRescrapeCountdown() {
    rescrapeCountdown = RESCRAPE_TIMEOUT_SECONDS;
    if (rescrapeCountdownInterval) clearInterval(rescrapeCountdownInterval);
    rescrapeCountdownInterval = setInterval(() => {
      rescrapeCountdown = Math.max(0, rescrapeCountdown - 1);
    }, 1000);
  }
  
  function stopRescrapeCountdown() {
    if (rescrapeCountdownInterval) {
      clearInterval(rescrapeCountdownInterval);
      rescrapeCountdownInterval = null;
    }
  }
  
  // Manual content file upload
  let manualContentFileRef: HTMLInputElement;
  
  // Header container ref for responsive behavior
  let headerRef: HTMLDivElement;
  let headerWidth = $state(0);
  const isCompact = $derived(headerWidth < 500);

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

  function openPdfUploadPicker() {
    pdfUploadInputRef?.click();
  }

  function openManualContentFilePicker() {
    manualContentFileRef?.click();
  }

  // ResizeObserver for responsive header
  $effect(() => {
    if (!headerRef) return;
    
    const observer = new ResizeObserver((entries) => {
      for (const entry of entries) {
        headerWidth = entry.contentRect.width;
      }
    });
    
    observer.observe(headerRef);
    return () => observer.disconnect();
  });

  function openRescrapeModal() {
    showRescrapeModal = true;
    rescrapeTarget = 'both';
    selectedContentMethod = source.contentMethod || 'markdownify';
    selectedPreviewMethod = source.previewMethod || 'weasyprint';
    manualContentInput = '';
  }

  function closeRescrapeModal() {
    showRescrapeModal = false;
    isRescraping = false;
    stopRescrapeCountdown();
  }

  /**
   * Handle manual content text/file upload.
   */
  async function handleManualContentFile(e: Event) {
    const input = e.target as HTMLInputElement;
    if (!input.files?.[0]) return;
    
    const file = input.files[0];
    if (!file.type.startsWith('text/')) {
      toast.error('Invalid file type', { description: 'Please upload a text or markdown file.' });
      input.value = '';
      return;
    }
    
    manualContentInput = await file.text();
    input.value = '';
    toast.success('File loaded', { description: `${file.name} content loaded` });
  }

  /**
   * Execute re-scrape with selected methods.
   */
  async function executeRescrape() {
    if (!source.url.startsWith('http')) {
      toast.error('Cannot re-scrape', { description: 'This source does not have a valid URL.' });
      return;
    }
    
    isRescraping = true;
    startRescrapeCountdown();
    const now = Date.now();
    
    try {
      let newContent = source.content;
      let newContentMethod: ContentCrawlMethod = source.contentMethod || 'markdownify';
      let newPreviewBlobId = source.previewBlobId;
      let newPreviewError = source.previewError;
      let newPreviewMethod: PreviewCrawlMethod = source.previewMethod || 'weasyprint';
      
      // Re-scrape content if requested
      if (rescrapeTarget === 'content' || rescrapeTarget === 'both') {
        if (selectedContentMethod === 'manual') {
          if (!manualContentInput.trim()) {
            toast.error('No content provided', { description: 'Please enter or upload content.' });
            stopRescrapeCountdown();
            isRescraping = false;
            return;
          }
          newContent = manualContentInput;
          newContentMethod = 'manual';
        } else {
          // Call backend with method parameter
          const response = await fetch(`${BACKEND_URL}/api/scrape/`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              url: source.url,
              timeout: 15.0,
              generate_pdf: false,
              method: selectedContentMethod
            }),
          });
          
          if (!response.ok) {
            const err = await response.json().catch(() => ({ detail: 'Unknown error' }));
            throw new Error(err.detail || `HTTP ${response.status}`);
          }
          
          const scraped = await response.json();
          newContent = scraped.content;
          newContentMethod = selectedContentMethod;
        }
      }
      
      // Re-scrape preview if requested  
      if (rescrapeTarget === 'preview' || rescrapeTarget === 'both') {
        if (selectedPreviewMethod === 'manual') {
          // Just keep current - user will upload via the preview pane
          newPreviewMethod = 'manual';
        } else {
          // Re-generate PDF via backend with selected preview method
          const response = await fetch(`${BACKEND_URL}/api/scrape/`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              url: source.url,
              timeout: 15.0,
              generate_pdf: true,
              preview_method: selectedPreviewMethod
            }),
          });
          
          if (response.ok) {
            const scraped = await response.json();
            if (scraped.preview_pdf) {
              // Store the new preview PDF
              const binaryString = atob(scraped.preview_pdf);
              const bytes = new Uint8Array(binaryString.length);
              for (let i = 0; i < binaryString.length; i++) {
                bytes[i] = binaryString.charCodeAt(i);
              }
              const pdfBlob = new Blob([bytes], { type: 'application/pdf' });
              
              newPreviewBlobId = nanoid();
              await db.sourceFiles.save({
                id: newPreviewBlobId,
                sourceId: source.id,
                blob: pdfBlob,
                createdAt: now
              });
              newPreviewError = undefined;
              newPreviewMethod = selectedPreviewMethod;
              
              // Update preview blob URL
              if (previewBlobUrl) URL.revokeObjectURL(previewBlobUrl);
              previewBlobUrl = URL.createObjectURL(pdfBlob);
            } else {
              newPreviewError = scraped.preview_error || 'PDF generation failed';
            }
          }
        }
      }
      
      // Update source via store (updates both reactive state AND IndexedDB)
      await sourceStore.updateSource(source.id, {
        content: newContent,
        bibliography: source.bibliography ? JSON.parse(JSON.stringify(source.bibliography)) : undefined,
        scrapedAt: now,
        metadata: source.metadata ? JSON.parse(JSON.stringify(source.metadata)) : undefined,
        previewBlobId: newPreviewBlobId,
        previewError: newPreviewError,
        contentMethod: newContentMethod,
        previewMethod: newPreviewMethod
      });

      stopRescrapeCountdown();
      toast.success('Re-scrape complete', {
        description: `Updated using ${newContentMethod} method`
      });
      
      closeRescrapeModal();
      
    } catch (error) {
      stopRescrapeCountdown();
      const errorMsg = error instanceof Error ? error.message : 'Unknown error';
      toast.error('Re-scrape failed', { description: errorMsg });
    } finally {
      isRescraping = false;
    }
  }

  /**
   * Handle manual PDF upload to replace the failed/missing preview.
   * Stores the PDF blob and updates the source's previewBlobId.
   */
  async function handlePdfUpload(e: Event) {
    const input = e.target as HTMLInputElement;
    if (!input.files?.[0]) return;
    
    const file = input.files[0];
    if (file.type !== 'application/pdf') {
      toast.error('Invalid file type', { description: 'Please upload a PDF file.' });
      input.value = '';
      return;
    }
    
    isUploadingPdf = true;
    
    try {
      const now = Date.now();
      const newPreviewBlobId = nanoid();
      
      // Store the preview PDF blob
      await db.sourceFiles.save({
        id: newPreviewBlobId,
        sourceId: source.id,
        blob: file,
        createdAt: now
      });
      
      // Update source via store (updates both reactive state AND IndexedDB)
      await sourceStore.updateSource(source.id, {
        previewBlobId: newPreviewBlobId,
        previewError: undefined,
        previewMethod: 'manual' as PreviewCrawlMethod
      });
      
      // Update local state by reloading the preview
      previewBlobUrl = URL.createObjectURL(file);
      previewLoadError = null;
      
      toast.success('PDF uploaded successfully', {
        description: 'Preview is now available for this source.'
      });
      
    } catch (error) {
      const errorMsg = error instanceof Error ? error.message : 'Unknown error';
      toast.error('Upload failed', { description: errorMsg });
    } finally {
      isUploadingPdf = false;
      input.value = '';
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

<!-- Hidden PDF upload input -->
<input
  bind:this={pdfUploadInputRef}
  type="file"
  accept=".pdf,application/pdf"
  onchange={handlePdfUpload}
  class="hidden"
/>

<div class="flex h-full flex-col bg-zinc-950 overflow-hidden">
  <!-- Header Bar -->
  <div 
    bind:this={headerRef}
    class="flex items-center border-b border-zinc-800 bg-zinc-900/50 px-3 py-2 gap-2"
  >
    <div class="flex items-center gap-2 min-w-0 flex-shrink overflow-hidden flex-1">
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
        {:else if !isCompact}
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
      <!-- Tab Switcher (only for URL sources) - responsive -->
      <div class="flex items-center gap-0.5 rounded-lg bg-zinc-800/50 p-0.5 flex-shrink-0">
        <button
          onclick={() => activeTab = 'content'}
          title="Content"
          class={cn(
            "flex items-center gap-1.5 rounded-md px-2 py-1.5 text-xs font-medium transition-all",
            activeTab === 'content'
              ? "bg-zinc-700 text-zinc-100 shadow-sm"
              : "text-zinc-400 hover:text-zinc-200"
          )}
        >
          <FileText class="h-3.5 w-3.5" />
          {#if !isCompact}<span>Content</span>{/if}
        </button>
        <button
          onclick={() => activeTab = 'preview'}
          title="Preview"
          class={cn(
            "flex items-center gap-1.5 rounded-md px-2 py-1.5 text-xs font-medium transition-all",
            activeTab === 'preview'
              ? "bg-zinc-700 text-zinc-100 shadow-sm"
              : "text-zinc-400 hover:text-zinc-200",
            !hasPreview && hasPreviewError && "opacity-60"
          )}
        >
          <Monitor class="h-3.5 w-3.5" />
          {#if !isCompact}<span>Preview</span>{/if}
        </button>
      </div>
      
      <!-- Re-scrape button -->
      <button
        onclick={openRescrapeModal}
        title="Re-scrape with different method"
        class="flex items-center justify-center rounded-md bg-zinc-800 p-1.5 text-zinc-400 hover:bg-zinc-700 hover:text-zinc-200 transition-colors flex-shrink-0"
      >
        <RefreshCw class="h-3.5 w-3.5" />
      </button>
    {/if}

    {#if isFileSource}
      <button 
        onclick={downloadFile}
        title="Download file"
        class={cn(
          "flex items-center gap-1.5 rounded-md bg-zinc-800 px-2 py-1.5 text-xs font-medium text-zinc-300 hover:bg-zinc-700 hover:text-zinc-100 transition-colors flex-shrink-0",
          isCompact && "px-1.5"
        )}
      >
        <Download class="h-3.5 w-3.5" />
        {#if !isCompact}<span>Download</span>{/if}
      </button>
    {:else}
      <a 
        href={source.url} 
        target="_blank" 
        rel="noopener noreferrer"
        title="Open original URL"
        class={cn(
          "flex items-center gap-1.5 rounded-md bg-zinc-800 px-2 py-1.5 text-xs font-medium text-zinc-300 hover:bg-zinc-700 hover:text-zinc-100 transition-colors flex-shrink-0",
          isCompact && "px-1.5"
        )}
      >
        {#if !isCompact}<span>Open</span>{/if}
        <ExternalLink class="h-3.5 w-3.5" />
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
              <div class="flex flex-col gap-3 items-center">
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
                <div class="border-t border-zinc-800 pt-3 mt-1 w-full">
                  <p class="text-xs text-zinc-500 mb-2">
                    Or save the webpage as PDF in your browser and upload it:
                  </p>
                  <button
                    onclick={openPdfUploadPicker}
                    disabled={isUploadingPdf}
                    class="inline-flex items-center gap-2 rounded-lg bg-amber-600 px-4 py-2 text-sm font-medium text-white hover:bg-amber-500 transition-colors disabled:opacity-50"
                  >
                    {#if isUploadingPdf}
                      <Loader2 class="h-4 w-4 animate-spin" />
                      <span>Uploading...</span>
                    {:else}
                      <Upload class="h-4 w-4" />
                      <span>Upload PDF Instead</span>
                    {/if}
                  </button>
                </div>
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
              <div class="flex flex-col gap-3 items-center">
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
                <div class="border-t border-zinc-800 pt-3 mt-1 w-full">
                  <p class="text-xs text-zinc-500 mb-2">
                    You can add a PDF preview by saving the webpage as PDF:
                  </p>
                  <button
                    onclick={openPdfUploadPicker}
                    disabled={isUploadingPdf}
                    class="inline-flex items-center gap-2 rounded-lg bg-amber-600 px-4 py-2 text-sm font-medium text-white hover:bg-amber-500 transition-colors disabled:opacity-50"
                  >
                    {#if isUploadingPdf}
                      <Loader2 class="h-4 w-4 animate-spin" />
                      <span>Uploading...</span>
                    {:else}
                      <Upload class="h-4 w-4" />
                      <span>Upload PDF</span>
                    {/if}
                  </button>
                </div>
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

  <!-- Footer with scraped timestamp and method info -->
  <div class="border-t border-zinc-800 px-4 py-1.5 flex items-center justify-between text-[10px] text-zinc-600">
    <span>
      {#if isFileSource}
        {#if source.fileHash}
          SHA256: {source.fileHash.slice(0, 16)}...
        {/if}
      {:else if source.scrapedAt}
        Scraped {new Date(source.scrapedAt).toLocaleDateString()} at {new Date(source.scrapedAt).toLocaleTimeString()}
        {#if source.contentMethod}
          · Content: {source.contentMethod}
        {/if}
        {#if source.previewMethod}
          · PDF: {source.previewMethod}
        {/if}
      {:else}
        Added {new Date(source.createdAt).toLocaleDateString()}
      {/if}
    </span>
    <span class="uppercase tracking-wider font-medium text-zinc-700">Read Only</span>
  </div>
</div>

<!-- Hidden input for manual content file upload -->
<input
  bind:this={manualContentFileRef}
  type="file"
  accept=".txt,.md,text/plain,text/markdown"
  onchange={handleManualContentFile}
  class="hidden"
/>

<!-- Re-scrape Modal -->
{#if showRescrapeModal}
  <div 
    class="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4"
    onclick={(e) => e.target === e.currentTarget && closeRescrapeModal()}
    role="presentation"
  >
    <div 
      class="w-full max-w-md rounded-xl border border-zinc-800 bg-zinc-900 shadow-2xl overflow-hidden"
      role="dialog"
      aria-modal="true"
    >
      <!-- Header -->
      <div class="flex items-center justify-between border-b border-zinc-800 px-4 py-3 bg-zinc-800/50">
        <div class="flex items-center gap-2">
          <RefreshCw class="h-5 w-5 text-blue-500" />
          <h3 class="font-semibold text-zinc-100">Re-scrape Source</h3>
        </div>
        <button 
          onclick={closeRescrapeModal}
          disabled={isRescraping}
          class="rounded-lg p-1 text-zinc-500 hover:bg-zinc-700 hover:text-zinc-200 transition-colors disabled:opacity-50"
        >
          <X class="h-5 w-5" />
        </button>
      </div>

      <div class="p-5 space-y-5">
        <!-- Target Selection -->
        <div>
          <label class="block text-xs font-bold uppercase tracking-wider text-zinc-500 mb-2">
            What to re-scrape
          </label>
          <div class="flex gap-2">
            <button
              onclick={() => rescrapeTarget = 'content'}
              class={cn(
                "flex-1 rounded-lg border px-3 py-2 text-sm font-medium transition-all",
                rescrapeTarget === 'content'
                  ? "border-blue-500 bg-blue-500/10 text-blue-300"
                  : "border-zinc-700 text-zinc-400 hover:border-zinc-600"
              )}
            >
              <FileText class="h-4 w-4 mx-auto mb-1" />
              Content
            </button>
            <button
              onclick={() => rescrapeTarget = 'preview'}
              class={cn(
                "flex-1 rounded-lg border px-3 py-2 text-sm font-medium transition-all",
                rescrapeTarget === 'preview'
                  ? "border-blue-500 bg-blue-500/10 text-blue-300"
                  : "border-zinc-700 text-zinc-400 hover:border-zinc-600"
              )}
            >
              <Monitor class="h-4 w-4 mx-auto mb-1" />
              Preview
            </button>
            <button
              onclick={() => rescrapeTarget = 'both'}
              class={cn(
                "flex-1 rounded-lg border px-3 py-2 text-sm font-medium transition-all",
                rescrapeTarget === 'both'
                  ? "border-blue-500 bg-blue-500/10 text-blue-300"
                  : "border-zinc-700 text-zinc-400 hover:border-zinc-600"
              )}
            >
              <RefreshCw class="h-4 w-4 mx-auto mb-1" />
              Both
            </button>
          </div>
        </div>

        <!-- Content Method (if content or both) -->
        {#if rescrapeTarget === 'content' || rescrapeTarget === 'both'}
          <div>
            <label class="block text-xs font-bold uppercase tracking-wider text-zinc-500 mb-2">
              Content extraction method
            </label>
            <div class="space-y-2">
              <button
                onclick={() => selectedContentMethod = 'markdownify'}
                class={cn(
                  "w-full flex items-center gap-3 rounded-lg border px-3 py-2.5 text-left transition-all",
                  selectedContentMethod === 'markdownify'
                    ? "border-blue-500 bg-blue-500/10"
                    : "border-zinc-700 hover:border-zinc-600"
                )}
              >
                <Globe class={cn("h-5 w-5", selectedContentMethod === 'markdownify' ? "text-blue-400" : "text-zinc-500")} />
                <div>
                  <div class={cn("text-sm font-medium", selectedContentMethod === 'markdownify' ? "text-blue-200" : "text-zinc-300")}>
                    Markdownify
                  </div>
                  <div class="text-xs text-zinc-500">Built-in HTML to Markdown conversion</div>
                </div>
              </button>
              <button
                onclick={() => selectedContentMethod = 'firecrawl'}
                class={cn(
                  "w-full flex items-center gap-3 rounded-lg border px-3 py-2.5 text-left transition-all",
                  selectedContentMethod === 'firecrawl'
                    ? "border-blue-500 bg-blue-500/10"
                    : "border-zinc-700 hover:border-zinc-600"
                )}
              >
                <Sparkles class={cn("h-5 w-5", selectedContentMethod === 'firecrawl' ? "text-amber-400" : "text-zinc-500")} />
                <div>
                  <div class={cn("text-sm font-medium", selectedContentMethod === 'firecrawl' ? "text-blue-200" : "text-zinc-300")}>
                    Firecrawl API
                  </div>
                  <div class="text-xs text-zinc-500">Better for complex/JS-heavy pages</div>
                </div>
              </button>
              <button
                onclick={() => selectedContentMethod = 'manual'}
                class={cn(
                  "w-full flex items-center gap-3 rounded-lg border px-3 py-2.5 text-left transition-all",
                  selectedContentMethod === 'manual'
                    ? "border-blue-500 bg-blue-500/10"
                    : "border-zinc-700 hover:border-zinc-600"
                )}
              >
                <PenLine class={cn("h-5 w-5", selectedContentMethod === 'manual' ? "text-green-400" : "text-zinc-500")} />
                <div>
                  <div class={cn("text-sm font-medium", selectedContentMethod === 'manual' ? "text-blue-200" : "text-zinc-300")}>
                    Manual Input
                  </div>
                  <div class="text-xs text-zinc-500">Paste or upload your own text</div>
                </div>
              </button>
            </div>
            
            <!-- Manual content input -->
            {#if selectedContentMethod === 'manual'}
              <div class="mt-3 space-y-2">
                <textarea
                  bind:value={manualContentInput}
                  placeholder="Paste content here, or upload a text file..."
                  class="w-full h-32 rounded-lg border border-zinc-700 bg-zinc-800 px-3 py-2 text-sm text-zinc-100 placeholder-zinc-600 outline-none focus:border-blue-500 transition-colors resize-none"
                ></textarea>
                <button
                  onclick={openManualContentFilePicker}
                  class="text-xs text-blue-400 hover:text-blue-300 transition-colors"
                >
                  Or upload a .txt/.md file
                </button>
              </div>
            {/if}
          </div>
        {/if}

        <!-- Preview Method (if preview or both) -->
        {#if rescrapeTarget === 'preview' || rescrapeTarget === 'both'}
          <div>
            <label class="block text-xs font-bold uppercase tracking-wider text-zinc-500 mb-2">
              PDF preview method
            </label>
            <div class="space-y-2">
              <button
                onclick={() => selectedPreviewMethod = 'weasyprint'}
                class={cn(
                  "w-full flex items-center gap-3 rounded-lg border px-3 py-2.5 text-left transition-all",
                  selectedPreviewMethod === 'weasyprint'
                    ? "border-blue-500 bg-blue-500/10"
                    : "border-zinc-700 hover:border-zinc-600"
                )}
              >
                <Monitor class={cn("h-5 w-5", selectedPreviewMethod === 'weasyprint' ? "text-blue-400" : "text-zinc-500")} />
                <div>
                  <div class={cn("text-sm font-medium", selectedPreviewMethod === 'weasyprint' ? "text-blue-200" : "text-zinc-300")}>
                    WeasyPrint
                  </div>
                  <div class="text-xs text-zinc-500">Server-side HTML to PDF rendering</div>
                </div>
              </button>
              <button
                onclick={() => selectedPreviewMethod = 'firecrawl'}
                class={cn(
                  "w-full flex items-center gap-3 rounded-lg border px-3 py-2.5 text-left transition-all",
                  selectedPreviewMethod === 'firecrawl'
                    ? "border-blue-500 bg-blue-500/10"
                    : "border-zinc-700 hover:border-zinc-600"
                )}
              >
                <Camera class={cn("h-5 w-5", selectedPreviewMethod === 'firecrawl' ? "text-amber-400" : "text-zinc-500")} />
                <div>
                  <div class={cn("text-sm font-medium", selectedPreviewMethod === 'firecrawl' ? "text-blue-200" : "text-zinc-300")}>
                    Firecrawl Screenshot
                  </div>
                  <div class="text-xs text-zinc-500">Full-page screenshot (best for JS-heavy pages)</div>
                </div>
              </button>
              <button
                onclick={() => selectedPreviewMethod = 'manual'}
                class={cn(
                  "w-full flex items-center gap-3 rounded-lg border px-3 py-2.5 text-left transition-all",
                  selectedPreviewMethod === 'manual'
                    ? "border-blue-500 bg-blue-500/10"
                    : "border-zinc-700 hover:border-zinc-600"
                )}
              >
                <Upload class={cn("h-5 w-5", selectedPreviewMethod === 'manual' ? "text-green-400" : "text-zinc-500")} />
                <div>
                  <div class={cn("text-sm font-medium", selectedPreviewMethod === 'manual' ? "text-blue-200" : "text-zinc-300")}>
                    Manual Upload
                  </div>
                  <div class="text-xs text-zinc-500">Upload your own PDF (use Preview tab after)</div>
                </div>
              </button>
            </div>
          </div>
        {/if}
        
        <!-- Countdown timer when re-scraping -->
        {#if isRescraping}
          <div class="flex items-center justify-center gap-2 py-2 text-sm text-zinc-400">
            <Clock class="h-4 w-4 animate-pulse" />
            <span>Scraping... {rescrapeCountdown}s remaining</span>
          </div>
        {/if}
      </div>

      <!-- Footer -->
      <div class="flex items-center justify-end gap-3 border-t border-zinc-800 px-4 py-3 bg-zinc-800/30">
        <Button
          onclick={closeRescrapeModal}
          disabled={isRescraping}
          variant="ghost"
          class="text-zinc-400 hover:text-zinc-200"
        >
          Cancel
        </Button>
        <Button
          onclick={executeRescrape}
          disabled={isRescraping || (selectedContentMethod === 'manual' && !manualContentInput.trim() && (rescrapeTarget === 'content' || rescrapeTarget === 'both'))}
          class="bg-blue-600 hover:bg-blue-500"
        >
          {#if isRescraping}
            <Loader2 class="h-4 w-4 mr-2 animate-spin" />
            Re-scraping...
          {:else}
            <RefreshCw class="h-4 w-4 mr-2" />
            Re-scrape
          {/if}
        </Button>
      </div>
    </div>
  </div>
{/if}
