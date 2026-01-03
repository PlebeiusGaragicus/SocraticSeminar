<script lang="ts">
  import X from '@lucide/svelte/icons/x';
  import Globe from '@lucide/svelte/icons/globe';
  import Link from '@lucide/svelte/icons/link';
  import Sparkles from '@lucide/svelte/icons/sparkles';
  import Loader2 from '@lucide/svelte/icons/loader-2';
  import AlertCircle from '@lucide/svelte/icons/alert-circle';
  import Upload from '@lucide/svelte/icons/upload';
  import FileText from '@lucide/svelte/icons/file-text';
  import Image from '@lucide/svelte/icons/image';
  import Check from '@lucide/svelte/icons/check';
  import XCircle from '@lucide/svelte/icons/x-circle';
  import Clock from '@lucide/svelte/icons/clock';
  import Monitor from '@lucide/svelte/icons/monitor';
  import Settings2 from '@lucide/svelte/icons/settings-2';
  import ChevronDown from '@lucide/svelte/icons/chevron-down';
  import ChevronUp from '@lucide/svelte/icons/chevron-up';
  import { Button } from './ui/index.js';
  import { sourceStore, projectStore, workspaceStore } from '$lib/stores/index.js';
  import { DuplicateSourceError } from '$lib/stores/sources.svelte.js';
  import { cn } from '$lib/utils.js';
  import { onMount, onDestroy } from 'svelte';
  import { toast } from 'svelte-sonner';
  import type { Bibliography, ContentCrawlMethod, PreviewCrawlMethod } from '$lib/stores/types.js';

  // Backend URL for scraping service
  const BACKEND_URL = import.meta.env.PUBLIC_BACKEND_URL ?? 'http://localhost:8000';

  // Scraping timeout (matches backend: 15s HTTP + 30s PDF = ~45s max)
  const SCRAPE_TIMEOUT_SECONDS = 45;

  interface Props {
    column?: 'left' | 'right';
    onClose: () => void;
  }

  let { column = 'left', onClose }: Props = $props();

  // URL form state
  let urlList = $state('');
  let inputRef: HTMLTextAreaElement;
  let isProcessingUrls = $state(false);
  let urlProcessedCount = $state(0);
  let urlTotalCount = $state(0);
  let urlErrors = $state<string[]>([]);
  
  // Scraping progress state
  let currentScrapeUrl = $state<string | null>(null);
  let scrapeCountdown = $state(SCRAPE_TIMEOUT_SECONDS);
  let countdownInterval: ReturnType<typeof setInterval> | null = null;
  
  // Failed scrape for PDF upload fallback
  let failedScrapeUrl = $state<string | null>(null);
  let failedScrapeTitle = $state<string | null>(null);
  let pdfUploadInputRef: HTMLInputElement;
  
  // Scrape method options
  let showMethodOptions = $state(false);
  let selectedContentMethod = $state<ContentCrawlMethod>('markdownify');
  let selectedPreviewMethod = $state<PreviewCrawlMethod | 'off'>('weasyprint');
  const generatePdf = $derived(selectedPreviewMethod !== 'off');

  // File upload state
  let isDragging = $state(false);
  let isProcessingFiles = $state(false);
  let fileProcessedCount = $state(0);
  let fileTotalCount = $state(0);
  let fileResults = $state<Array<{ name: string; success: boolean; error?: string }>>([]);
  let fileInputRef: HTMLInputElement;

  const ALLOWED_EXTENSIONS = ['.pdf', '.txt', '.md', '.png', '.jpg', '.jpeg'];
  const ALLOWED_MIME_TYPES = [
    'application/pdf',
    'text/plain',
    'text/markdown',
    'image/png',
    'image/jpeg',
  ];

  // Cleanup countdown interval on destroy
  onDestroy(() => {
    if (countdownInterval) clearInterval(countdownInterval);
  });

  function startCountdown() {
    scrapeCountdown = SCRAPE_TIMEOUT_SECONDS;
    if (countdownInterval) clearInterval(countdownInterval);
    countdownInterval = setInterval(() => {
      scrapeCountdown = Math.max(0, scrapeCountdown - 1);
    }, 1000);
  }

  function stopCountdown() {
    if (countdownInterval) {
      clearInterval(countdownInterval);
      countdownInterval = null;
    }
    currentScrapeUrl = null;
  }

  // Scrape response type from backend
  interface ScrapeResponse {
    url: string;
    title: string;
    content: string;
    bibliography: Bibliography;
    scraped_at: number;
    preview_pdf: string | null;  // Base64-encoded PDF
    preview_error: string | null;  // Error message if PDF generation failed
  }

  /**
   * Scrape a URL via the backend service.
   * Returns structured data with title, content (markdown), and bibliography.
   */
  async function scrapeUrl(
    url: string,
    method: ContentCrawlMethod = 'markdownify',
    generatePdfPreview: boolean = true
  ): Promise<ScrapeResponse> {
    const response = await fetch(`${BACKEND_URL}/api/scrape/`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ 
        url, 
        timeout: 15.0,
        method,
        generate_pdf: generatePdfPreview
      }),
    });
    
    if (!response.ok) {
      const errorData = await response.json().catch(() => ({ detail: 'Unknown error' }));
      throw new Error(errorData.detail || `HTTP ${response.status}`);
    }
    
    return response.json();
  }

  /**
   * Extract a simple title from URL for fallback display.
   */
  function getTitleFromUrl(url: string): string {
    try {
      const urlObj = new URL(url);
      const pathParts = urlObj.pathname.split('/').filter(p => p.length > 0);
      if (pathParts.length > 0) {
        const lastPart = pathParts[pathParts.length - 1];
        return decodeURIComponent(lastPart.replace(/\.[^/.]+$/, '').replace(/[-_]/g, ' '));
      }
      return urlObj.hostname;
    } catch {
      return url;
    }
  }

  async function handleAddUrls() {
    const urls = urlList.split('\n').map(u => u.trim()).filter(u => u.length > 0 && u.startsWith('http'));
    if (urls.length === 0 || !projectStore.currentProjectId) return;

    isProcessingUrls = true;
    urlProcessedCount = 0;
    urlTotalCount = urls.length;
    urlErrors = [];
    failedScrapeUrl = null;
    failedScrapeTitle = null;
    
    const projectId = projectStore.currentProjectId;
    
    for (const url of urls) {
      try {
        // Check for duplicate URL first
        const existing = await sourceStore.checkDuplicateUrl(url);
        if (existing) {
          urlErrors = [...urlErrors, `"${url}" already exists as "${existing.title}"`];
          urlProcessedCount++;
          continue;
        }

        // Start countdown and show current URL
        currentScrapeUrl = url;
        startCountdown();

        // Scrape via backend service with selected methods
        const scraped = await scrapeUrl(url, selectedContentMethod, generatePdf);
        
        stopCountdown();
        
        // Show toast if PDF generation failed
        if (scraped.preview_error) {
          toast.warning('PDF preview unavailable', {
            description: scraped.preview_error,
            duration: 5000,
          });
        }
        
        // Create the source with scraped data and preview PDF
        const source = await sourceStore.createSource(
          projectId,
          scraped.title,
          scraped.url,
          scraped.content,
          { 
            bibliography: scraped.bibliography,
            scrapedAt: scraped.scraped_at,
            skipDuplicateCheck: true,
            previewPdfBase64: scraped.preview_pdf ?? undefined,
            previewError: scraped.preview_error ?? undefined,
            contentMethod: selectedContentMethod,
            previewMethod: generatePdf ? 'weasyprint' : undefined
          }
        );
        workspaceStore.openItem(source.id, 'source', column);
      } catch (error) {
        stopCountdown();
        
        if (error instanceof DuplicateSourceError) {
          urlErrors = [...urlErrors, error.message];
        } else {
          console.error('Failed to scrape URL:', url, error);
          const errorMsg = error instanceof Error ? error.message : String(error);
          
          toast.error('Scrape failed', {
            description: errorMsg,
            duration: 5000,
          });
          
          // Store failed URL for manual PDF upload option
          failedScrapeUrl = url;
          failedScrapeTitle = getTitleFromUrl(url);
          
          // Create a placeholder source with error info
          try {
            const source = await sourceStore.createSource(
              projectId,
              getTitleFromUrl(url),
              url,
              `# ${url}\n\n**Error scraping this URL:** ${errorMsg}\n\n**Tip**: Try asking the research agent to scrape this URL:\n\n> "Please add this URL as a source: ${url}"`,
              { scrapedAt: Date.now(), skipDuplicateCheck: true }
            );
            workspaceStore.openItem(source.id, 'source', column);
          } catch (createError) {
            if (createError instanceof DuplicateSourceError) {
              urlErrors = [...urlErrors, createError.message];
            } else {
              urlErrors = [...urlErrors, `Failed to add "${url}": ${errorMsg}`];
            }
          }
        }
      }
      
      urlProcessedCount++;
    }
    
    isProcessingUrls = false;
    if (urlErrors.length === 0 && !failedScrapeUrl) {
      onClose();
    }
  }

  /**
   * Handle manual PDF upload for a failed scrape.
   * Associates the uploaded PDF with the source URL.
   */
  async function handlePdfUploadForFailedScrape(e: Event) {
    const input = e.target as HTMLInputElement;
    if (!input.files?.[0] || !failedScrapeUrl || !projectStore.currentProjectId) return;
    
    const file = input.files[0];
    const projectId = projectStore.currentProjectId;
    
    try {
      // Create source with the uploaded PDF
      const source = await sourceStore.createFileSource(projectId, file, {
        url: failedScrapeUrl,
        title: failedScrapeTitle || file.name.replace(/\.pdf$/i, ''),
      });
      
      workspaceStore.openItem(source.id, 'source', column);
      
      toast.success('PDF uploaded successfully', {
        description: `Added "${source.title}" as a source`,
      });
      
      // Clear failed state
      failedScrapeUrl = null;
      failedScrapeTitle = null;
      onClose();
    } catch (error) {
      const errorMsg = error instanceof Error ? error.message : 'Unknown error';
      toast.error('Upload failed', { description: errorMsg });
    }
    
    input.value = '';
  }

  function openPdfUploadPicker() {
    pdfUploadInputRef?.click();
  }

  // File upload handlers
  function handleDragEnter(e: DragEvent) {
    e.preventDefault();
    isDragging = true;
  }

  function handleDragLeave(e: DragEvent) {
    e.preventDefault();
    // Only set to false if we're leaving the drop zone entirely
    const relatedTarget = e.relatedTarget as HTMLElement | null;
    if (!relatedTarget || !e.currentTarget?.contains?.(relatedTarget)) {
      isDragging = false;
    }
  }

  function handleDragOver(e: DragEvent) {
    e.preventDefault();
    if (e.dataTransfer) {
      e.dataTransfer.dropEffect = 'copy';
    }
  }

  async function handleDrop(e: DragEvent) {
    e.preventDefault();
    isDragging = false;
    
    if (!e.dataTransfer?.files || !projectStore.currentProjectId) return;
    
    const files = Array.from(e.dataTransfer.files);
    await processFiles(files);
  }

  function handleFileInputChange(e: Event) {
    const input = e.target as HTMLInputElement;
    if (!input.files || !projectStore.currentProjectId) return;
    
    const files = Array.from(input.files);
    processFiles(files);
    
    // Reset input so same file can be selected again
    input.value = '';
  }

  function openFilePicker() {
    fileInputRef?.click();
  }

  async function processFiles(files: File[]) {
    if (files.length === 0 || !projectStore.currentProjectId) return;
    
    isProcessingFiles = true;
    fileProcessedCount = 0;
    fileTotalCount = files.length;
    fileResults = [];
    
    const projectId = projectStore.currentProjectId;
    
    for (const file of files) {
      try {
        // Validate file type
        if (!ALLOWED_MIME_TYPES.includes(file.type)) {
          // Try extension-based fallback for .md files
          const ext = file.name.toLowerCase().match(/\.[^.]+$/)?.[0];
          if (ext !== '.md') {
            fileResults = [...fileResults, {
              name: file.name,
              success: false,
              error: `Unsupported file type. Allowed: ${ALLOWED_EXTENSIONS.join(', ')}`
            }];
            fileProcessedCount++;
            continue;
          }
        }
        
        const source = await sourceStore.createFileSource(projectId, file);
        workspaceStore.openItem(source.id, 'source', column);
        
        fileResults = [...fileResults, { name: file.name, success: true }];
      } catch (error) {
        const errorMsg = error instanceof Error ? error.message : 'Unknown error';
        fileResults = [...fileResults, {
          name: file.name,
          success: false,
          error: errorMsg
        }];
      }
      
      fileProcessedCount++;
    }
    
    isProcessingFiles = false;
    
    // Close if all succeeded
    if (fileResults.every(r => r.success)) {
      setTimeout(() => onClose(), 500);
    }
  }

  function handleKeydown(e: KeyboardEvent) {
    if (e.key === 'Escape' && !isProcessingUrls && !isProcessingFiles) {
      onClose();
    }
  }

  function handleBackdropClick(e: MouseEvent) {
    if (e.target === e.currentTarget && !isProcessingUrls && !isProcessingFiles) {
      onClose();
    }
  }

  const isProcessing = $derived(isProcessingUrls || isProcessingFiles);

  onMount(() => {
    inputRef?.focus();
  });
</script>

<div 
  class="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4"
  onclick={handleBackdropClick}
  role="presentation"
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
      <!-- File Upload Section -->
      <section>
        <label class="block text-xs font-bold uppercase tracking-wider text-zinc-500 mb-2">
          Upload Files
        </label>
        
        <!-- Hidden file input -->
        <input
          bind:this={fileInputRef}
          type="file"
          multiple
          accept=".pdf,.txt,.md,.png,.jpg,.jpeg,application/pdf,text/plain,text/markdown,image/png,image/jpeg"
          onchange={handleFileInputChange}
          class="hidden"
        />
        
        <!-- Drop zone -->
        <div
          class={cn(
            'relative rounded-lg border-2 border-dashed p-8 transition-all text-center',
            isDragging
              ? 'border-blue-500 bg-blue-500/10'
              : 'border-zinc-700 hover:border-zinc-600 hover:bg-zinc-800/50',
            isProcessingFiles && 'pointer-events-none opacity-60'
          )}
          ondragenter={handleDragEnter}
          ondragleave={handleDragLeave}
          ondragover={handleDragOver}
          ondrop={handleDrop}
          role="button"
          tabindex="0"
          onclick={openFilePicker}
          onkeydown={(e) => e.key === 'Enter' && openFilePicker()}
        >
          {#if isProcessingFiles}
            <Loader2 class="h-10 w-10 text-blue-500 mx-auto mb-3 animate-spin" />
            <p class="text-sm text-zinc-300">Processing files... {fileProcessedCount}/{fileTotalCount}</p>
          {:else}
            <Upload class={cn('h-10 w-10 mx-auto mb-3', isDragging ? 'text-blue-400' : 'text-zinc-500')} />
            <p class="text-sm text-zinc-300 mb-1">
              {isDragging ? 'Drop files here' : 'Drag & drop files here, or click to browse'}
            </p>
            <p class="text-xs text-zinc-500">
              Supported: PDF, TXT, MD, PNG, JPEG
            </p>
          {/if}
        </div>
        
        <!-- File results -->
        {#if fileResults.length > 0}
          <div class="mt-3 space-y-1.5 max-h-32 overflow-y-auto">
            {#each fileResults as result}
              <div class={cn(
                'flex items-center gap-2 rounded px-3 py-1.5 text-sm',
                result.success ? 'bg-green-500/10 text-green-300' : 'bg-red-500/10 text-red-300'
              )}>
                {#if result.success}
                  <Check class="h-4 w-4 flex-shrink-0" />
                {:else}
                  <XCircle class="h-4 w-4 flex-shrink-0" />
                {/if}
                <span class="truncate flex-1">{result.name}</span>
                {#if result.error}
                  <span class="text-xs text-red-400 truncate max-w-[200px]">{result.error}</span>
                {/if}
              </div>
            {/each}
          </div>
        {/if}
      </section>

      <div class="relative">
        <div class="absolute inset-0 flex items-center">
          <div class="w-full border-t border-zinc-800"></div>
        </div>
        <div class="relative flex justify-center">
          <span class="bg-zinc-900 px-3 text-xs text-zinc-500 uppercase">or add by URL</span>
        </div>
      </div>

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
            disabled={isProcessingUrls}
            placeholder="https://example.com/article1&#10;https://example.com/article2"
            class="w-full h-24 rounded-lg border border-zinc-700 bg-zinc-800 px-4 py-3 text-zinc-100 placeholder-zinc-600 outline-none focus:border-blue-500 transition-colors font-mono text-sm resize-none disabled:opacity-50"
          ></textarea>
          
          <!-- Scrape Method Options (collapsible) -->
          <div class="rounded-lg border border-zinc-800 overflow-hidden">
            <button
              type="button"
              onclick={() => showMethodOptions = !showMethodOptions}
              class="w-full flex items-center justify-between px-3 py-2 text-left bg-zinc-800/50 hover:bg-zinc-800 transition-colors"
            >
              <div class="flex items-center gap-2">
                <Settings2 class="h-4 w-4 text-zinc-500" />
                <span class="text-xs font-medium text-zinc-400">Scrape Options</span>
                <span class="text-xs text-zinc-600">
                  ({selectedContentMethod}{generatePdf ? ` + ${selectedPreviewMethod}` : ', no PDF'})
                </span>
              </div>
              {#if showMethodOptions}
                <ChevronUp class="h-4 w-4 text-zinc-500" />
              {:else}
                <ChevronDown class="h-4 w-4 text-zinc-500" />
              {/if}
            </button>
            
            {#if showMethodOptions}
              <div class="p-3 space-y-4 border-t border-zinc-800">
                <!-- Content Method -->
                <div>
                  <label class="block text-[10px] font-bold uppercase tracking-wider text-zinc-600 mb-2">
                    Content Extraction
                  </label>
                  <div class="flex gap-2">
                    <button
                      type="button"
                      onclick={() => selectedContentMethod = 'markdownify'}
                      class={cn(
                        "flex-1 flex items-center justify-center gap-1.5 rounded-md border px-2 py-1.5 text-xs font-medium transition-all",
                        selectedContentMethod === 'markdownify'
                          ? "border-blue-500 bg-blue-500/10 text-blue-300"
                          : "border-zinc-700 text-zinc-400 hover:border-zinc-600"
                      )}
                    >
                      <Globe class="h-3.5 w-3.5" />
                      Markdownify
                    </button>
                    <button
                      type="button"
                      onclick={() => selectedContentMethod = 'firecrawl'}
                      class={cn(
                        "flex-1 flex items-center justify-center gap-1.5 rounded-md border px-2 py-1.5 text-xs font-medium transition-all",
                        selectedContentMethod === 'firecrawl'
                          ? "border-amber-500 bg-amber-500/10 text-amber-300"
                          : "border-zinc-700 text-zinc-400 hover:border-zinc-600"
                      )}
                    >
                      <Sparkles class="h-3.5 w-3.5" />
                      Firecrawl
                    </button>
                  </div>
                  <p class="text-[10px] text-zinc-600 mt-1">
                    {selectedContentMethod === 'firecrawl' 
                      ? 'Better for JS-heavy or complex pages (requires API key)'
                      : 'Built-in HTML to Markdown conversion'}
                  </p>
                </div>
                
                <!-- PDF Preview Method -->
                <div>
                  <label class="block text-[10px] font-bold uppercase tracking-wider text-zinc-600 mb-2">
                    PDF Preview
                  </label>
                  <div class="flex gap-2">
                    <button
                      type="button"
                      onclick={() => selectedPreviewMethod = 'weasyprint'}
                      class={cn(
                        "flex-1 flex items-center justify-center gap-1.5 rounded-md border px-2 py-1.5 text-xs font-medium transition-all",
                        selectedPreviewMethod === 'weasyprint'
                          ? "border-blue-500 bg-blue-500/10 text-blue-300"
                          : "border-zinc-700 text-zinc-400 hover:border-zinc-600"
                      )}
                    >
                      <Monitor class="h-3.5 w-3.5" />
                      WeasyPrint
                    </button>
                    <button
                      type="button"
                      onclick={() => selectedPreviewMethod = 'off'}
                      class={cn(
                        "flex-1 flex items-center justify-center gap-1.5 rounded-md border px-2 py-1.5 text-xs font-medium transition-all",
                        selectedPreviewMethod === 'off'
                          ? "border-zinc-500 bg-zinc-500/10 text-zinc-300"
                          : "border-zinc-700 text-zinc-400 hover:border-zinc-600"
                      )}
                    >
                      <XCircle class="h-3.5 w-3.5" />
                      Off
                    </button>
                  </div>
                  <p class="text-[10px] text-zinc-600 mt-1">
                    {selectedPreviewMethod === 'off' 
                      ? 'Skip PDF generation (faster scraping)'
                      : 'Generate PDF preview of the page'}
                  </p>
                </div>
              </div>
            {/if}
          </div>
          
          <!-- URL errors -->
          {#if urlErrors.length > 0}
            <div class="space-y-1">
              {#each urlErrors as error}
                <div class="flex items-center gap-2 text-xs text-amber-400">
                  <AlertCircle class="h-3.5 w-3.5 flex-shrink-0" />
                  <span>{error}</span>
                </div>
              {/each}
            </div>
          {/if}
          
          <!-- Scraping progress with countdown -->
          {#if isProcessingUrls && currentScrapeUrl}
            <div class="flex items-center gap-3 rounded-lg bg-blue-500/10 border border-blue-500/30 px-4 py-3">
              <Loader2 class="h-5 w-5 text-blue-400 animate-spin flex-shrink-0" />
              <div class="flex-1 min-w-0">
                <p class="text-sm text-blue-200 truncate">Scraping: {currentScrapeUrl}</p>
                <p class="text-xs text-blue-400/70 mt-0.5">Fetching content and generating PDF preview...</p>
              </div>
              <div class="flex items-center gap-1.5 text-blue-300">
                <Clock class="h-4 w-4" />
                <span class="text-sm font-mono tabular-nums">{scrapeCountdown}s</span>
              </div>
            </div>
          {/if}
          
          <div class="flex items-center justify-end">
            <Button 
              onclick={handleAddUrls}
              disabled={!urlList.trim() || isProcessingUrls}
              class="bg-blue-600 hover:bg-blue-500"
            >
              {#if isProcessingUrls}
                <Loader2 class="h-4 w-4 mr-2 animate-spin" />
                {urlProcessedCount}/{urlTotalCount}
              {:else}
                <Link class="h-4 w-4 mr-2" />
                Quick Add
              {/if}
            </Button>
          </div>
        </div>
      </section>
      
      <!-- Manual PDF Upload Fallback (shown when scrape fails) -->
      {#if failedScrapeUrl}
        <section class="rounded-lg border border-amber-500/30 bg-amber-500/5 p-4">
          <input
            bind:this={pdfUploadInputRef}
            type="file"
            accept=".pdf,application/pdf"
            onchange={handlePdfUploadForFailedScrape}
            class="hidden"
          />
          
          <div class="flex gap-3">
            <AlertCircle class="h-5 w-5 text-amber-400 flex-shrink-0 mt-0.5" />
            <div class="flex-1 space-y-3">
              <div>
                <h4 class="text-sm font-medium text-amber-200">Scrape failed for this URL</h4>
                <p class="text-xs text-zinc-400 mt-1 break-all">{failedScrapeUrl}</p>
              </div>
              <p class="text-xs text-zinc-400">
                You can manually upload a PDF of this page instead. Save the webpage as PDF in your browser, then upload it here.
              </p>
              <div class="flex items-center gap-2">
                <Button
                  onclick={openPdfUploadPicker}
                  class="bg-amber-600 hover:bg-amber-500"
                >
                  <Upload class="h-4 w-4 mr-2" />
                  Upload PDF Instead
                </Button>
                <Button
                  onclick={() => { failedScrapeUrl = null; failedScrapeTitle = null; }}
                  variant="ghost"
                  class="text-zinc-400 hover:text-zinc-200"
                >
                  Dismiss
                </Button>
              </div>
            </div>
          </div>
        </section>
      {/if}

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
