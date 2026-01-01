// Source store using Svelte 5 runes
// Manages external sources within projects with IndexedDB persistence

import { nanoid } from 'nanoid';
import { untrack } from 'svelte';
import type { Source } from './types.js';
import { db } from '$lib/services/indexeddb.js';

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
      metadata: source.metadata ? JSON.parse(JSON.stringify(source.metadata)) : undefined,
      createdAt: source.createdAt,
      updatedAt: source.updatedAt,
      viewed: source.viewed ?? false
    };
    await db.sources.save(plainSource);
  } catch (error) {
    console.error('Failed to persist source:', error);
  }
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

// Actions
function createSource(
  projectId: string,
  title: string,
  url: string,
  content: string = '',
  metadata: Record<string, unknown> = {}
): Source {
  const now = Date.now();
  
  const source: Source = {
    id: nanoid(),
    projectId,
    title,
    url,
    content,
    metadata,
    createdAt: now,
    updatedAt: now,
    viewed: false
  };
  
  sources = [...sources, source];
  currentSourceId = source.id;
  
  // Persist async
  persistSource(source);
  
  return source;
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
  deleteSource,
  selectSource,
  reset,
  clearProjectState
};

