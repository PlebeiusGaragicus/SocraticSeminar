// IndexedDB service for Socratic Seminar
// Provides persistence for projects, artifacts, threads, and messages

import { openDB, type DBSchema, type IDBPDatabase } from 'idb';
import type { Project, Artifact, Thread, Message } from '../stores/types.js';

const DB_NAME = 'socratic-seminar';
const DB_VERSION = 2; // Bumped for threads/messages

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
  threads: {
    key: string;
    value: Thread;
    indexes: { 'by-project': string; 'by-updated': number };
  };
  messages: {
    key: string;
    value: Message;
    indexes: { 'by-thread': string; 'by-created': number };
  };
}

let dbPromise: Promise<IDBPDatabase<SocraticDB>> | null = null;

function getDB(): Promise<IDBPDatabase<SocraticDB>> {
  if (!dbPromise) {
    dbPromise = openDB<SocraticDB>(DB_NAME, DB_VERSION, {
      upgrade(db, oldVersion) {
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

        // Threads store (added in version 2)
        if (!db.objectStoreNames.contains('threads')) {
          const threadStore = db.createObjectStore('threads', { keyPath: 'id' });
          threadStore.createIndex('by-project', 'projectId');
          threadStore.createIndex('by-updated', 'updatedAt');
        }

        // Messages store (added in version 2)
        if (!db.objectStoreNames.contains('messages')) {
          const messageStore = db.createObjectStore('messages', { keyPath: 'id' });
          messageStore.createIndex('by-thread', 'threadId');
          messageStore.createIndex('by-created', 'createdAt');
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
  
  // Delete all artifacts and threads in the project first
  const tx = db.transaction(['projects', 'artifacts', 'threads', 'messages'], 'readwrite');
  
  // Delete artifacts
  const artifactIndex = tx.objectStore('artifacts').index('by-project');
  let artifactCursor = await artifactIndex.openCursor(IDBKeyRange.only(id));
  while (artifactCursor) {
    await artifactCursor.delete();
    artifactCursor = await artifactCursor.continue();
  }
  
  // Get threads to delete their messages
  const threadIndex = tx.objectStore('threads').index('by-project');
  const threads = await threadIndex.getAll(IDBKeyRange.only(id));
  
  // Delete messages for each thread
  const messageStore = tx.objectStore('messages');
  for (const thread of threads) {
    const messageIndex = messageStore.index('by-thread');
    let msgCursor = await messageIndex.openCursor(IDBKeyRange.only(thread.id));
    while (msgCursor) {
      await msgCursor.delete();
      msgCursor = await msgCursor.continue();
    }
  }
  
  // Delete threads
  let threadCursor = await threadIndex.openCursor(IDBKeyRange.only(id));
  while (threadCursor) {
    await threadCursor.delete();
    threadCursor = await threadCursor.continue();
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

// Thread operations
export async function getProjectThreads(projectId: string): Promise<Thread[]> {
  const db = await getDB();
  return db.getAllFromIndex('threads', 'by-project', projectId);
}

export async function getAllThreads(): Promise<Thread[]> {
  const db = await getDB();
  return db.getAll('threads');
}

export async function getThread(id: string): Promise<Thread | undefined> {
  const db = await getDB();
  return db.get('threads', id);
}

export async function saveThread(thread: Thread): Promise<void> {
  const db = await getDB();
  await db.put('threads', thread);
}

export async function deleteThread(id: string): Promise<void> {
  const db = await getDB();
  
  // Delete all messages in the thread first
  const tx = db.transaction(['threads', 'messages'], 'readwrite');
  const messageIndex = tx.objectStore('messages').index('by-thread');
  
  let cursor = await messageIndex.openCursor(IDBKeyRange.only(id));
  while (cursor) {
    await cursor.delete();
    cursor = await cursor.continue();
  }
  
  await tx.objectStore('threads').delete(id);
  await tx.done;
}

// Message operations
export async function getThreadMessages(threadId: string): Promise<Message[]> {
  const db = await getDB();
  const messages = await db.getAllFromIndex('messages', 'by-thread', threadId);
  // Sort by createdAt
  return messages.sort((a, b) => a.createdAt - b.createdAt);
}

export async function getMessage(id: string): Promise<Message | undefined> {
  const db = await getDB();
  return db.get('messages', id);
}

export async function saveMessage(message: Message): Promise<void> {
  const db = await getDB();
  await db.put('messages', message);
}

export async function saveMessages(messages: Message[]): Promise<void> {
  const db = await getDB();
  const tx = db.transaction('messages', 'readwrite');
  await Promise.all([
    ...messages.map(m => tx.store.put(m)),
    tx.done
  ]);
}

export async function deleteMessage(id: string): Promise<void> {
  const db = await getDB();
  await db.delete('messages', id);
}

export async function deleteThreadMessages(threadId: string): Promise<void> {
  const db = await getDB();
  const tx = db.transaction('messages', 'readwrite');
  const index = tx.store.index('by-thread');
  
  let cursor = await index.openCursor(IDBKeyRange.only(threadId));
  while (cursor) {
    await cursor.delete();
    cursor = await cursor.continue();
  }
  
  await tx.done;
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

export async function saveThreads(threads: Thread[]): Promise<void> {
  const db = await getDB();
  const tx = db.transaction('threads', 'readwrite');
  await Promise.all([
    ...threads.map(t => tx.store.put(t)),
    tx.done
  ]);
}

// Clear all data (for logout)
export async function clearAllData(): Promise<void> {
  const db = await getDB();
  const tx = db.transaction(['projects', 'artifacts', 'threads', 'messages'], 'readwrite');
  await Promise.all([
    tx.objectStore('projects').clear(),
    tx.objectStore('artifacts').clear(),
    tx.objectStore('threads').clear(),
    tx.objectStore('messages').clear(),
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
  threads: {
    getByProject: getProjectThreads,
    getAll: getAllThreads,
    get: getThread,
    save: saveThread,
    delete: deleteThread,
    saveMany: saveThreads
  },
  messages: {
    getByThread: getThreadMessages,
    get: getMessage,
    save: saveMessage,
    saveMany: saveMessages,
    delete: deleteMessage,
    deleteByThread: deleteThreadMessages
  },
  clearAll: clearAllData
};
