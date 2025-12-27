// Artifact store using Svelte 5 runes
// Manages versioned artifacts within projects with IndexedDB persistence

import { nanoid } from 'nanoid';
import type { Artifact, ArtifactVersion, ArtifactType } from './types.js';
import { db } from '$lib/services/indexeddb.js';

// Reactive state
let artifacts = $state<Artifact[]>([]);
let currentArtifactId = $state<string | null>(null);
let openArtifactIds = $state<string[]>([]);
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

// Persistence helper
async function persistArtifact(artifact: Artifact): Promise<void> {
  try {
    await db.artifacts.save(artifact);
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
  type: ArtifactType,
  title: string,
  content: string,
  language?: string
): Artifact {
  const now = Date.now();
  const version: ArtifactVersion = {
    index: 0,
    title,
    content,
    language,
    createdAt: now
  };
  
  const artifact: Artifact = {
    id: nanoid(),
    projectId,
    type,
    currentVersionIndex: 0,
    versions: [version],
    createdAt: now,
    updatedAt: now
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
  language?: string
): ArtifactVersion {
  const artifact = artifacts.find((a) => a.id === id);
  if (!artifact) {
    throw new Error(`Artifact ${id} not found`);
  }
  
  const now = Date.now();
  const newVersion: ArtifactVersion = {
    index: artifact.versions.length,
    title,
    content,
    language,
    createdAt: now
  };
  
  const updatedArtifact = {
    ...artifact,
    versions: [...artifact.versions, newVersion],
    currentVersionIndex: newVersion.index,
    updatedAt: now
  };
  
  artifacts = artifacts.map((a) => a.id === id ? updatedArtifact : a);
  
  // Persist async
  persistArtifact(updatedArtifact);
  
  return newVersion;
}

function setArtifactVersion(id: string, versionIndex: number): void {
  const artifact = artifacts.find(a => a.id === id);
  if (!artifact || versionIndex < 0 || versionIndex >= artifact.versions.length) return;
  
  artifacts = artifacts.map((a) =>
    a.id === id ? { ...a, currentVersionIndex: versionIndex } : a
  );
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
  
  // Add to open tabs if not already there
  if (id && !openArtifactIds.includes(id)) {
    openArtifactIds = [...openArtifactIds, id];
  }
}

function closeArtifact(id: string): void {
  openArtifactIds = openArtifactIds.filter(openId => openId !== id);
  
  if (currentArtifactId === id) {
    // Select another open artifact or null
    currentArtifactId = openArtifactIds[openArtifactIds.length - 1] ?? null;
  }
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
    pendingChanges.newContent,
    currentVersion?.language
  );
  
  pendingChanges = null;
}

function rejectPendingChanges(): void {
  pendingChanges = null;
}

function reset(): void {
  artifacts = [];
  currentArtifactId = null;
  openArtifactIds = [];
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
  deleteArtifact,
  selectArtifact,
  closeArtifact,
  loadArtifacts,
  setPendingChanges,
  acceptPendingChanges,
  rejectPendingChanges,
  reset
};
