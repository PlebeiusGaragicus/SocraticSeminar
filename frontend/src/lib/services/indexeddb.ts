// IndexedDB service for Socratic Seminar
// Provides persistence for projects and artifacts

import { openDB, type DBSchema, type IDBPDatabase } from 'idb';
import type { Project, Artifact } from '../stores/types.js';

const DB_NAME = 'socratic-seminar';
const DB_VERSION = 1;

interface SocraticDB extends DBSchema {
  projects: {
    key: string;
    value: Project;
    indexes: { 'by-npub': string; 'by-updated': number };
  };
  artifacts: {
    key: string;
    value: Artifact;
    indexes: { 'by-project': string; 'by-updated': number };
  };
}

let dbPromise: Promise<IDBPDatabase<SocraticDB>> | null = null;

function getDB(): Promise<IDBPDatabase<SocraticDB>> {
  if (!dbPromise) {
    dbPromise = openDB<SocraticDB>(DB_NAME, DB_VERSION, {
      upgrade(db) {
        // Projects store
        if (!db.objectStoreNames.contains('projects')) {
          const projectStore = db.createObjectStore('projects', { keyPath: 'id' });
          projectStore.createIndex('by-npub', 'npub');
          projectStore.createIndex('by-updated', 'updatedAt');
        }

        // Artifacts store
        if (!db.objectStoreNames.contains('artifacts')) {
          const artifactStore = db.createObjectStore('artifacts', { keyPath: 'id' });
          artifactStore.createIndex('by-project', 'projectId');
          artifactStore.createIndex('by-updated', 'updatedAt');
        }
      }
    });
  }
  return dbPromise;
}

// Project operations
export async function getAllProjects(npub?: string): Promise<Project[]> {
  const db = await getDB();
  if (npub) {
    return db.getAllFromIndex('projects', 'by-npub', npub);
  }
  return db.getAll('projects');
}

export async function getProject(id: string): Promise<Project | undefined> {
  const db = await getDB();
  return db.get('projects', id);
}

export async function saveProject(project: Project): Promise<void> {
  const db = await getDB();
  await db.put('projects', project);
}

export async function deleteProject(id: string): Promise<void> {
  const db = await getDB();
  
  // Delete all artifacts in the project first
  const tx = db.transaction(['projects', 'artifacts'], 'readwrite');
  const artifactIndex = tx.objectStore('artifacts').index('by-project');
  
  let cursor = await artifactIndex.openCursor(IDBKeyRange.only(id));
  while (cursor) {
    await cursor.delete();
    cursor = await cursor.continue();
  }
  
  await tx.objectStore('projects').delete(id);
  await tx.done;
}

// Artifact operations
export async function getProjectArtifacts(projectId: string): Promise<Artifact[]> {
  const db = await getDB();
  return db.getAllFromIndex('artifacts', 'by-project', projectId);
}

export async function getArtifact(id: string): Promise<Artifact | undefined> {
  const db = await getDB();
  return db.get('artifacts', id);
}

export async function saveArtifact(artifact: Artifact): Promise<void> {
  const db = await getDB();
  await db.put('artifacts', artifact);
}

export async function deleteArtifact(id: string): Promise<void> {
  const db = await getDB();
  await db.delete('artifacts', id);
}

// Batch operations
export async function saveProjects(projects: Project[]): Promise<void> {
  const db = await getDB();
  const tx = db.transaction('projects', 'readwrite');
  await Promise.all([
    ...projects.map(p => tx.store.put(p)),
    tx.done
  ]);
}

export async function saveArtifacts(artifacts: Artifact[]): Promise<void> {
  const db = await getDB();
  const tx = db.transaction('artifacts', 'readwrite');
  await Promise.all([
    ...artifacts.map(a => tx.store.put(a)),
    tx.done
  ]);
}

// Clear all data (for logout)
export async function clearAllData(): Promise<void> {
  const db = await getDB();
  const tx = db.transaction(['projects', 'artifacts'], 'readwrite');
  await Promise.all([
    tx.objectStore('projects').clear(),
    tx.objectStore('artifacts').clear(),
    tx.done
  ]);
}

// Export database service object
export const db = {
  projects: {
    getAll: getAllProjects,
    get: getProject,
    save: saveProject,
    delete: deleteProject,
    saveMany: saveProjects
  },
  artifacts: {
    getByProject: getProjectArtifacts,
    get: getArtifact,
    save: saveArtifact,
    delete: deleteArtifact,
    saveMany: saveArtifacts
  },
  clearAll: clearAllData
};

