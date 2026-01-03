// Source store using Svelte 5 runes
// Manages external sources within projects with IndexedDB persistence

import { nanoid } from 'nanoid';
import { untrack } from 'svelte';
import type { Source, SourceFile, Bibliography, SourceType, ContentCrawlMethod, PreviewCrawlMethod } from './types.js';
import { ALLOWED_FILE_TYPES } from './types.js';
import { db } from '$lib/services/indexeddb.js';

// Custom error for duplicate sources
export class DuplicateSourceError extends Error {
  constructor(
    message: string,
    public readonly existingSource: Source
  ) {
    super(message);
    this.name = 'DuplicateSourceError';
  }
}

// Reactive state
let sources = $state<Source[]>([]);
let currentSourceId = $state<string | null>(null);

// Derived state
const currentSource = $derived(
  sources.find((s) => s.id === currentSourceId) ?? null
);

// Persistence helper
async function persistSource(source: Source): Promise<void> {
  try {
    const plainSource: Source = {
      id: source.id,
      projectId: source.projectId,
      title: source.title,
      url: source.url,
      content: source.content,
      bibliography: source.bibliography ? JSON.parse(JSON.stringify(source.bibliography)) : undefined,
      scrapedAt: source.scrapedAt,
      metadata: source.metadata ? JSON.parse(JSON.stringify(source.metadata)) : undefined,
      createdAt: source.createdAt,
      updatedAt: source.updatedAt,
      viewed: source.viewed ?? false,
      // File source fields
      sourceType: source.sourceType,
      fileHash: source.fileHash,
      mimeType: source.mimeType,
      fileSize: source.fileSize,
      blobId: source.blobId,
      // Preview fields
      previewBlobId: source.previewBlobId,
      previewError: source.previewError,
      // Crawl method tracking
      contentMethod: source.contentMethod,
      previewMethod: source.previewMethod
    };
    await db.sources.save(plainSource);
  } catch (error) {
    console.error('Failed to persist source:', error);
  }
}

// Persist blob to IndexedDB
async function persistSourceFile(sourceFile: SourceFile): Promise<void> {
  try {
    await db.sourceFiles.save(sourceFile);
  } catch (error) {
    console.error('Failed to persist source file:', error);
    throw error;
  }
}

// Deduplication helpers
function findByUrl(url: string): Source | undefined {
  return sources.find(s => s.url === url);
}

function findByHash(hash: string): Source | undefined {
  return sources.find(s => s.fileHash === hash);
}

// Check for duplicates across all projects (async, from IndexedDB)
async function checkDuplicateUrl(url: string): Promise<Source | undefined> {
  // First check in-memory
  const inMemory = findByUrl(url);
  if (inMemory) return inMemory;
  
  // Then check IndexedDB
  return await db.sources.findByUrl(url);
}

async function checkDuplicateHash(hash: string): Promise<Source | undefined> {
  // First check in-memory
  const inMemory = findByHash(hash);
  if (inMemory) return inMemory;
  
  // Then check IndexedDB
  return await db.sources.findByHash(hash);
}

// Compute SHA-256 hash of a file
async function computeFileHash(file: File): Promise<string> {
  const buffer = await file.arrayBuffer();
  const hashBuffer = await crypto.subtle.digest('SHA-256', buffer);
  const hashArray = Array.from(new Uint8Array(hashBuffer));
  return hashArray.map(b => b.toString(16).padStart(2, '0')).join('');
}

// Validate file type
function isAllowedFileType(mimeType: string): boolean {
  return (ALLOWED_FILE_TYPES as readonly string[]).includes(mimeType);
}

// Get sources for a specific project
function getProjectSources(projectId: string): Source[] {
  return sources.filter((s) => s.projectId === projectId)
    .sort((s, b) => b.updatedAt - s.updatedAt);
}

// Load sources for a project from IndexedDB
async function loadProjectSources(projectId: string): Promise<void> {
  try {
    const loadedSources = await db.sources.getByProject(projectId);
    
    // Merge with existing sources
    // Use untrack to prevent creating subscriptions when called from effects
    const otherSources = untrack(() => sources.filter(s => s.projectId !== projectId));
    sources = [...otherSources, ...loadedSources];
  } catch (error) {
    console.error('Failed to load sources from IndexedDB:', error);
  }
}

// Options for creating a source
interface CreateSourceOptions {
  bibliography?: Bibliography;
  scrapedAt?: number;
  metadata?: Record<string, unknown>;
  skipDuplicateCheck?: boolean; // For agent-created sources where we've already verified
  // Preview PDF (base64 encoded or Blob)
  previewPdfBase64?: string;
  previewError?: string;
  // Crawl method tracking
  contentMethod?: ContentCrawlMethod;
  previewMethod?: PreviewCrawlMethod;
}

// Options for creating a file source
interface CreateFileSourceOptions {
  metadata?: Record<string, unknown>;
  url?: string;    // Override URL (e.g., for manual PDF upload of failed scrapes)
  title?: string;  // Override title
}

// Actions

/**
 * Create a URL-based source. Throws DuplicateSourceError if URL already exists.
 * Optionally stores a preview PDF blob.
 */
async function createSource(
  projectId: string,
  title: string,
  url: string,
  content: string = '',
  options: CreateSourceOptions = {}
): Promise<Source> {
  // Check for duplicate URL unless explicitly skipped
  if (!options.skipDuplicateCheck) {
    const existingByUrl = await checkDuplicateUrl(url);
    if (existingByUrl) {
      throw new DuplicateSourceError(
        `A source with URL "${url}" already exists: "${existingByUrl.title}"`,
        existingByUrl
      );
    }
  }
  
  const now = Date.now();
  const sourceId = nanoid();
  
  // Handle preview PDF if provided
  let previewBlobId: string | undefined;
  
  if (options.previewPdfBase64) {
    try {
      // Convert base64 to Blob
      const binaryString = atob(options.previewPdfBase64);
      const bytes = new Uint8Array(binaryString.length);
      for (let i = 0; i < binaryString.length; i++) {
        bytes[i] = binaryString.charCodeAt(i);
      }
      const pdfBlob = new Blob([bytes], { type: 'application/pdf' });
      
      // Store the preview PDF blob
      previewBlobId = nanoid();
      const previewFile: SourceFile = {
        id: previewBlobId,
        sourceId,
        blob: pdfBlob,
        createdAt: now
      };
      await persistSourceFile(previewFile);
    } catch (error) {
      console.error('Failed to store preview PDF:', error);
      // Don't fail the whole operation, just skip the preview
    }
  }
  
  const source: Source = {
    id: sourceId,
    projectId,
    title,
    url,
    content,
    bibliography: options.bibliography,
    scrapedAt: options.scrapedAt ?? now,
    metadata: options.metadata,
    createdAt: now,
    updatedAt: now,
    viewed: false,
    sourceType: 'url' as SourceType,
    previewBlobId,
    previewError: options.previewError,
    contentMethod: options.contentMethod,
    previewMethod: options.previewMethod
  };
  
  sources = [...sources, source];
  currentSourceId = source.id;
  
  // Persist async
  persistSource(source);
  
  return source;
}

/**
 * Create a file-based source from an uploaded file.
 * Computes SHA-256 hash and stores blob in IndexedDB.
 * Throws DuplicateSourceError if file with same hash already exists.
 * Throws Error if file type is not allowed.
 */
async function createFileSource(
  projectId: string,
  file: File,
  options: CreateFileSourceOptions = {}
): Promise<Source> {
  // Validate file type
  if (!isAllowedFileType(file.type)) {
    throw new Error(
      `File type "${file.type}" is not allowed. Allowed types: PDF, TXT, MD, PNG, JPEG, JPG`
    );
  }
  
  // Compute file hash
  const fileHash = await computeFileHash(file);
  
  // Check for duplicate hash
  const existingByHash = await checkDuplicateHash(fileHash);
  if (existingByHash) {
    throw new DuplicateSourceError(
      `A file with the same content already exists: "${existingByHash.title}"`,
      existingByHash
    );
  }
  
  const now = Date.now();
  const blobId = nanoid();
  
  // For text-based files, extract content
  let content = '';
  if (file.type === 'text/plain' || file.type === 'text/markdown') {
    content = await file.text();
  }
  
  const source: Source = {
    id: nanoid(),
    projectId,
    title: options.title || file.name,
    url: options.url || file.name, // Use filename as URL for file sources, or override
    content,
    metadata: options.metadata,
    createdAt: now,
    updatedAt: now,
    viewed: false,
    // File source fields
    sourceType: 'file' as SourceType,
    fileHash,
    mimeType: file.type,
    fileSize: file.size,
    blobId
  };
  
  // Create the source file record
  const sourceFile: SourceFile = {
    id: blobId,
    sourceId: source.id,
    blob: file, // File extends Blob
    createdAt: now
  };
  
  // Persist both source and blob
  await persistSourceFile(sourceFile);
  
  sources = [...sources, source];
  currentSourceId = source.id;
  
  await persistSource(source);
  
  return source;
}

/**
 * Get the blob for a file source
 */
async function getSourceBlob(sourceId: string): Promise<Blob | undefined> {
  const source = sources.find(s => s.id === sourceId);
  if (!source?.blobId) return undefined;
  
  const sourceFile = await db.sourceFiles.get(source.blobId);
  return sourceFile?.blob;
}

/**
 * Get the preview PDF blob for a URL source
 */
async function getPreviewBlob(sourceId: string): Promise<Blob | undefined> {
  const source = sources.find(s => s.id === sourceId);
  if (!source?.previewBlobId) return undefined;
  
  const sourceFile = await db.sourceFiles.get(source.previewBlobId);
  return sourceFile?.blob;
}

async function deleteSource(id: string): Promise<void> {
  sources = sources.filter((s) => s.id !== id);
  
  if (currentSourceId === id) {
    currentSourceId = null;
  }
  
  try {
    await db.sources.delete(id);
  } catch (error) {
    console.error('Failed to delete source from IndexedDB:', error);
  }
}

function selectSource(id: string | null): void {
  currentSourceId = id;
  
  if (id) {
    // Mark as viewed
    const source = sources.find(s => s.id === id);
    if (source && !source.viewed) {
      sources = sources.map(s => s.id === id ? { ...s, viewed: true } : s);
      persistSource(sources.find(s => s.id === id)!);
    }
  }
}

function reset(): void {
  sources = [];
  currentSourceId = null;
}

function clearProjectState(): void {
  currentSourceId = null;
}

// Export reactive getters and actions
export const sourceStore = {
  get sources() { return sources; },
  get currentSource() { return currentSource; },
  get currentSourceId() { return currentSourceId; },
  
  getProjectSources,
  loadProjectSources,
  createSource,
  createFileSource,
  deleteSource,
  selectSource,
  getSourceBlob,
  getPreviewBlob,
  findByUrl,
  findByHash,
  checkDuplicateUrl,
  checkDuplicateHash,
  computeFileHash,
  isAllowedFileType,
  reset,
  clearProjectState
};

