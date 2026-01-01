// Artifact store using Svelte 5 runes
// Manages versioned markdown artifacts within projects with IndexedDB persistence

import { nanoid } from 'nanoid';
import type { Artifact, ArtifactVersion } from './types.js';
import { db } from '$lib/services/indexeddb.js';
import { projectStore } from './projects.svelte.js';

// Reactive state
let artifacts = $state<Artifact[]>([]);
let currentArtifactId = $state<string | null>(null);
let openArtifactIds = $state<string[]>([]);
let liveContentMap = $state<Record<string, string>>({});
let pendingChanges = $state<{
  artifactId: string;
  newContent: string;
  oldContent: string;
} | null>(null);

// Derived state
const currentArtifact = $derived(
  artifacts.find((a) => a.id === currentArtifactId) ?? null
);

const currentArtifactContent = $derived(() => {
  if (!currentArtifact) return null;
  return currentArtifact.versions[currentArtifact.currentVersionIndex] ?? null;
});

const openArtifacts = $derived(
  openArtifactIds.map(id => artifacts.find(a => a.id === id)).filter(Boolean) as Artifact[]
);

// Persistence helper - creates a plain object copy to avoid Svelte proxy issues
async function persistArtifact(artifact: Artifact): Promise<void> {
  try {
    // Deep clone to remove Svelte's Proxy wrapper which can't be cloned by IndexedDB
    const plainArtifact: Artifact = {
      id: artifact.id,
      projectId: artifact.projectId,
      currentVersionIndex: artifact.currentVersionIndex,
      versions: artifact.versions.map(v => ({
        index: v.index,
        title: v.title,
        content: v.content,
        createdAt: v.createdAt
      })),
      createdAt: artifact.createdAt,
      updatedAt: artifact.updatedAt,
      viewed: artifact.viewed ?? false,
      tags: artifact.tags || []
    };
    await db.artifacts.save(plainArtifact);
  } catch (error) {
    console.error('Failed to persist artifact:', error);
  }
}

// Get artifacts for a specific project
function getProjectArtifacts(projectId: string): Artifact[] {
  return artifacts.filter((a) => a.projectId === projectId)
    .sort((a, b) => b.updatedAt - a.updatedAt);
}

// Load artifacts for a project from IndexedDB
async function loadProjectArtifacts(projectId: string): Promise<void> {
  try {
    const loadedArtifacts = await db.artifacts.getByProject(projectId);
    
    // Merge with existing artifacts (replace those with same projectId)
    const otherArtifacts = artifacts.filter(a => a.projectId !== projectId);
    artifacts = [...otherArtifacts, ...loadedArtifacts];
  } catch (error) {
    console.error('Failed to load artifacts from IndexedDB:', error);
  }
}

// Actions
function createArtifact(
  projectId: string,
  title: string,
  content: string = ''
): Artifact {
  const now = Date.now();
  const version: ArtifactVersion = {
    index: 0,
    title,
    content,
    createdAt: now
  };
  
  const artifact: Artifact = {
    id: nanoid(),
    projectId,
    currentVersionIndex: 0,
    versions: [version],
    createdAt: now,
    updatedAt: now,
    viewed: false
  };
  
  artifacts = [...artifacts, artifact];
  currentArtifactId = artifact.id;
  
  // Add to open tabs
  if (!openArtifactIds.includes(artifact.id)) {
    openArtifactIds = [...openArtifactIds, artifact.id];
  }
  
  // Persist async
  persistArtifact(artifact);
  
  return artifact;
}

function updateArtifact(
  id: string,
  title: string,
  content: string,
  createNewVersion: boolean = false
): ArtifactVersion {
  const artifact = artifacts.find((a) => a.id === id);
  if (!artifact) {
    throw new Error(`Artifact ${id} not found`);
  }
  
  const now = Date.now();
  let updatedArtifact: Artifact;
  let resultVersion: ArtifactVersion;

  if (createNewVersion) {
    const newVersion: ArtifactVersion = {
      index: artifact.versions.length,
      title,
      content,
      createdAt: now
    };
    
    updatedArtifact = {
      ...artifact,
      versions: [...artifact.versions, newVersion],
      currentVersionIndex: newVersion.index,
      updatedAt: now
    };
    resultVersion = newVersion;
  } else {
    // Update current version in place
    const versions = [...artifact.versions];
    const currentVersion = versions[artifact.currentVersionIndex];
    
    if (currentVersion) {
      versions[artifact.currentVersionIndex] = {
        ...currentVersion,
        title,
        content
      };
    }

    updatedArtifact = {
      ...artifact,
      versions,
      updatedAt: now
    };
    resultVersion = versions[artifact.currentVersionIndex];
  }
  
  artifacts = artifacts.map((a) => a.id === id ? updatedArtifact : a);
  
  // Also update live content map so everything is in sync
  liveContentMap[id] = content;
  
  // Persist async
  persistArtifact(updatedArtifact);
  
  return resultVersion;
}

function setArtifactVersion(id: string, versionIndex: number): void {
  const artifact = artifacts.find(a => a.id === id);
  if (!artifact || versionIndex < 0 || versionIndex >= artifact.versions.length) return;
  
  artifacts = artifacts.map((a) =>
    a.id === id ? { ...a, currentVersionIndex: versionIndex } : a
  );
}

function toggleArtifactTag(id: string, tagName: string): void {
  const artifact = artifacts.find(a => a.id === id);
  if (!artifact) return;
  
  const currentTags = artifact.tags || [];
  const hasTag = currentTags.includes(tagName);
  
  const newTags = hasTag 
    ? currentTags.filter(t => t !== tagName)
    : [...currentTags, tagName];
    
  artifacts = artifacts.map((a) =>
    a.id === id ? { ...a, tags: newTags } : a
  );
  
  persistArtifact(artifacts.find(a => a.id === id)!);
}

function removeTagFromAllArtifacts(projectId: string, tagName: string): void {
  const projectArtifacts = artifacts.filter(a => a.projectId === projectId);
  
  projectArtifacts.forEach(artifact => {
    if (artifact.tags?.includes(tagName)) {
      const newTags = artifact.tags.filter(t => t !== tagName);
      artifacts = artifacts.map(a => a.id === artifact.id ? { ...a, tags: newTags } : a);
      persistArtifact(artifacts.find(a => a.id === artifact.id)!);
    }
  });
}

function renameArtifact(id: string, newTitle: string): void {
  const artifact = artifacts.find(a => a.id === id);
  if (!artifact) return;

  const updatedArtifact = {
    ...artifact,
    versions: artifact.versions.map((v, i) => 
      i === artifact.currentVersionIndex ? { ...v, title: newTitle } : v
    ),
    updatedAt: Date.now()
  };

  artifacts = artifacts.map(a => a.id === id ? updatedArtifact : a);
  persistArtifact(updatedArtifact);
}

async function deleteArtifact(id: string): Promise<void> {
  artifacts = artifacts.filter((a) => a.id !== id);
  openArtifactIds = openArtifactIds.filter(openId => openId !== id);
  
  if (currentArtifactId === id) {
    currentArtifactId = openArtifactIds[0] ?? null;
  }
  
  // Clear pending changes if for this artifact
  if (pendingChanges?.artifactId === id) {
    pendingChanges = null;
  }
  
  // Delete from IndexedDB
  try {
    await db.artifacts.delete(id);
  } catch (error) {
    console.error('Failed to delete artifact from IndexedDB:', error);
  }
}

function selectArtifact(id: string | null): void {
  currentArtifactId = id;
  
  if (id) {
    // Mark as viewed
    const artifact = artifacts.find(a => a.id === id);
    if (artifact && !artifact.viewed) {
      artifacts = artifacts.map(a => a.id === id ? { ...a, viewed: true } : a);
      persistArtifact(artifacts.find(a => a.id === id)!);
    }

    // Add to open tabs if not already there
    if (!openArtifactIds.includes(id)) {
      openArtifactIds = [...openArtifactIds, id];
    }
  }
}

function closeArtifact(id: string): void {
  openArtifactIds = openArtifactIds.filter(openId => openId !== id);
  delete liveContentMap[id];
  
  if (currentArtifactId === id) {
    // Select another open artifact or null
    currentArtifactId = openArtifactIds[openArtifactIds.length - 1] ?? null;
  }
}

function updateLiveContent(id: string, content: string): void {
  liveContentMap[id] = content;
}

function getLiveContent(id: string): string | null {
  if (liveContentMap[id] !== undefined) {
    return liveContentMap[id];
  }
  const artifact = artifacts.find(a => a.id === id);
  if (!artifact) return null;
  return artifact.versions[artifact.currentVersionIndex]?.content || '';
}

function loadArtifacts(loadedArtifacts: Artifact[]): void {
  artifacts = loadedArtifacts;
}

// Pending changes management (for agent edits)
function setPendingChanges(
  artifactId: string,
  newContent: string,
  oldContent: string
): void {
  pendingChanges = { artifactId, newContent, oldContent };
  
  // Make sure this artifact is selected and open
  if (!openArtifactIds.includes(artifactId)) {
    openArtifactIds = [...openArtifactIds, artifactId];
  }
  currentArtifactId = artifactId;
}

function acceptPendingChanges(): void {
  if (!pendingChanges) return;
  
  const artifact = artifacts.find(a => a.id === pendingChanges!.artifactId);
  if (!artifact) {
    pendingChanges = null;
    return;
  }
  
  const currentVersion = artifact.versions[artifact.currentVersionIndex];
  updateArtifact(
    pendingChanges.artifactId,
    currentVersion?.title || 'Untitled',
    pendingChanges.newContent
  );
  
  pendingChanges = null;
}

function rejectPendingChanges(): void {
  pendingChanges = null;
}

function clearPendingChanges(): void {
  pendingChanges = null;
}

function reset(): void {
  artifacts = [];
  currentArtifactId = null;
  openArtifactIds = [];
  liveContentMap = {};
  pendingChanges = null;
}

/**
 * Clear project-specific state when switching projects.
 * Keeps global state but resets selections and open tabs.
 */
function clearProjectState(): void {
  currentArtifactId = null;
  openArtifactIds = [];
  liveContentMap = {};
  pendingChanges = null;
}

// Export reactive getters and actions
export const artifactStore = {
  get artifacts() { return artifacts; },
  get currentArtifact() { return currentArtifact; },
  get currentArtifactId() { return currentArtifactId; },
  get currentArtifactContent() { return currentArtifactContent; },
  get openArtifacts() { return openArtifacts; },
  get openArtifactIds() { return openArtifactIds; },
  get pendingChanges() { return pendingChanges; },
  
  getProjectArtifacts,
  loadProjectArtifacts,
  createArtifact,
  updateArtifact,
  setArtifactVersion,
  toggleArtifactTag,
  removeTagFromAllArtifacts,
  renameArtifact,
  deleteArtifact,
  selectArtifact,
  closeArtifact,
  updateLiveContent,
  getLiveContent,
  loadArtifacts,
  setPendingChanges,
  acceptPendingChanges,
  rejectPendingChanges,
  clearPendingChanges,
  reset,
  clearProjectState
};
