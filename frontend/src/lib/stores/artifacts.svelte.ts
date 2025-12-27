// Artifact store using Svelte 5 runes
// Manages versioned artifacts within projects

import { nanoid } from 'nanoid';
import type { Artifact, ArtifactVersion, ArtifactType } from './types';

// Reactive state
let artifacts = $state<Artifact[]>([]);
let currentArtifactId = $state<string | null>(null);

// Derived state
const currentArtifact = $derived(
  artifacts.find((a) => a.id === currentArtifactId) ?? null
);

const currentArtifactContent = $derived(() => {
  if (!currentArtifact) return null;
  return currentArtifact.versions[currentArtifact.currentVersionIndex] ?? null;
});

// Get artifacts for a specific project
function getProjectArtifacts(projectId: string): Artifact[] {
  return artifacts.filter((a) => a.projectId === projectId)
    .sort((a, b) => b.updatedAt - a.updatedAt);
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
  
  artifacts = artifacts.map((a) =>
    a.id === id
      ? {
          ...a,
          versions: [...a.versions, newVersion],
          currentVersionIndex: newVersion.index,
          updatedAt: now
        }
      : a
  );
  
  return newVersion;
}

function setArtifactVersion(id: string, versionIndex: number): void {
  artifacts = artifacts.map((a) =>
    a.id === id && versionIndex >= 0 && versionIndex < a.versions.length
      ? { ...a, currentVersionIndex: versionIndex }
      : a
  );
}

function deleteArtifact(id: string): void {
  artifacts = artifacts.filter((a) => a.id !== id);
  if (currentArtifactId === id) {
    currentArtifactId = null;
  }
}

function selectArtifact(id: string | null): void {
  currentArtifactId = id;
}

function loadArtifacts(loadedArtifacts: Artifact[]): void {
  artifacts = loadedArtifacts;
}

// Export reactive getters and actions
export const artifactStore = {
  get artifacts() { return artifacts; },
  get currentArtifact() { return currentArtifact; },
  get currentArtifactId() { return currentArtifactId; },
  get currentArtifactContent() { return currentArtifactContent; },
  
  getProjectArtifacts,
  createArtifact,
  updateArtifact,
  setArtifactVersion,
  deleteArtifact,
  selectArtifact,
  loadArtifacts
};

