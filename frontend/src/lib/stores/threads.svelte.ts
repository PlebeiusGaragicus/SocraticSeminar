// Thread store using Svelte 5 runes
// Manages chat threads within projects with IndexedDB persistence

import { nanoid } from 'nanoid';
import type { Thread, Message } from './types.js';
import { db } from '$lib/services/indexeddb.js';

// Reactive state
let threads = $state<Thread[]>([]);
// Use a plain object instead of Map for better Svelte 5 reactivity
let messagesByThread = $state<Record<string, Message[]>>({});
let currentThreadId = $state<string | null>(null);
let isLoaded = $state(false);

// Version counter to force reactivity updates
let messagesVersion = $state(0);

// Derived state
const currentThread = $derived(
  threads.find((t) => t.id === currentThreadId) ?? null
);

// Use messagesVersion as a dependency to force re-computation
const currentMessages = $derived.by(() => {
  // Access messagesVersion to create dependency
  const _v = messagesVersion;
  if (!currentThreadId) return [];
  return messagesByThread[currentThreadId] ?? [];
});

// Get threads for a specific project
function getProjectThreads(projectId: string): Thread[] {
  return threads.filter((t) => t.projectId === projectId)
    .sort((a, b) => b.updatedAt - a.updatedAt);
}

// =============================================================================
// PERSISTENCE HELPERS
// =============================================================================

async function persistThread(thread: Thread): Promise<void> {
  try {
    await db.threads.save(thread);
  } catch (e) {
    console.error('[ThreadStore] Failed to persist thread:', e);
  }
}

async function persistMessages(threadId: string, messages: Message[]): Promise<void> {
  try {
    // Delete existing messages and save new ones
    await db.messages.deleteByThread(threadId);
    if (messages.length > 0) {
      await db.messages.saveMany(messages);
    }
  } catch (e) {
    console.error('[ThreadStore] Failed to persist messages:', e);
  }
}

async function deletePersistedThread(threadId: string): Promise<void> {
  try {
    await db.threads.delete(threadId);
  } catch (e) {
    console.error('[ThreadStore] Failed to delete persisted thread:', e);
  }
}

// =============================================================================
// ACTIONS
// =============================================================================

function createThread(projectId: string, title?: string): Thread {
  const now = Date.now();
  const thread: Thread = {
    id: nanoid(),
    projectId,
    title: title ?? 'New Thread',
    createdAt: now,
    updatedAt: now
  };
  
  threads = [...threads, thread];
  messagesByThread = { ...messagesByThread, [thread.id]: [] };
  messagesVersion++;
  currentThreadId = thread.id;
  
  // Persist asynchronously
  persistThread(thread);
  
  return thread;
}

function updateThread(id: string, updates: Partial<Pick<Thread, 'title' | 'metadata' | 'langGraphThreadId'>>): void {
  let updatedThread: Thread | null = null;
  
  threads = threads.map((t) => {
    if (t.id === id) {
      updatedThread = { ...t, ...updates, updatedAt: Date.now() };
      return updatedThread;
    }
    return t;
  });
  
  // Persist asynchronously
  if (updatedThread) {
    persistThread(updatedThread);
  }
}

function deleteThread(id: string): void {
  threads = threads.filter((t) => t.id !== id);
  const { [id]: removed, ...rest } = messagesByThread;
  messagesByThread = rest;
  messagesVersion++;
  
  if (currentThreadId === id) {
    currentThreadId = null;
  }
  
  // Persist asynchronously
  deletePersistedThread(id);
}

function selectThread(id: string | null): void {
  currentThreadId = id;
}

function addMessage(threadId: string, message: Omit<Message, 'id' | 'threadId' | 'createdAt'>): Message {
  const newMessage: Message = {
    ...message,
    id: nanoid(),
    threadId,
    createdAt: Date.now()
  };
  
  const threadMessages = messagesByThread[threadId] ?? [];
  const updatedMessages = [...threadMessages, newMessage];
  
  // Create new object to trigger reactivity
  messagesByThread = {
    ...messagesByThread,
    [threadId]: updatedMessages
  };
  messagesVersion++;
  
  console.log('[ThreadStore] Added message to thread', threadId, 'Total messages:', updatedMessages.length);
  
  // Update thread's updatedAt
  let updatedThread: Thread | null = null;
  threads = threads.map((t) => {
    if (t.id === threadId) {
      updatedThread = { ...t, updatedAt: Date.now() };
      return updatedThread;
    }
    return t;
  });
  
  // Persist asynchronously
  if (updatedThread) {
    persistThread(updatedThread);
  }
  persistMessages(threadId, updatedMessages);
  
  return newMessage;
}

function updateMessage(threadId: string, messageId: string, updates: Partial<Message>): void {
  const threadMessages = messagesByThread[threadId];
  if (!threadMessages) return;
  
  const updatedMessages = threadMessages.map((m) => 
    m.id === messageId ? { ...m, ...updates } : m
  );
  
  messagesByThread = {
    ...messagesByThread,
    [threadId]: updatedMessages
  };
  messagesVersion++;
  
  // Persist asynchronously
  persistMessages(threadId, updatedMessages);
}

function clearMessages(threadId: string): void {
  messagesByThread = { ...messagesByThread, [threadId]: [] };
  messagesVersion++;
  
  // Persist asynchronously
  persistMessages(threadId, []);
}

/**
 * Sync/replace all messages for a thread.
 * Used to sync with LangGraph server state after a conversation completes.
 */
function syncMessages(threadId: string, messages: Omit<Message, 'createdAt'>[]): void {
  const now = Date.now();
  const newMessages: Message[] = messages.map((msg, index) => ({
    ...msg,
    id: msg.id || `synced-${threadId}-${index}-${now}`,
    threadId,
    createdAt: now - (messages.length - index) * 1000 // Preserve order with timestamps
  }));
  
  messagesByThread = { ...messagesByThread, [threadId]: newMessages };
  messagesVersion++;
  
  console.log('[ThreadStore] Synced messages for thread', threadId, 'Total:', newMessages.length);
  
  // Update thread's updatedAt
  let updatedThread: Thread | null = null;
  threads = threads.map((t) => {
    if (t.id === threadId) {
      updatedThread = { ...t, updatedAt: Date.now() };
      return updatedThread;
    }
    return t;
  });
  
  // Persist asynchronously
  if (updatedThread) {
    persistThread(updatedThread);
  }
  persistMessages(threadId, newMessages);
}

function getMessages(threadId: string): Message[] {
  return messagesByThread[threadId] ?? [];
}

function getThreadMessageCount(threadId: string): number {
  return messagesByThread[threadId]?.length ?? 0;
}

function loadThreads(loadedThreads: Thread[], loadedMessages?: Record<string, Message[]>): void {
  threads = loadedThreads;
  if (loadedMessages) {
    messagesByThread = loadedMessages;
    messagesVersion++;
  }
}

/**
 * Load all threads and messages from IndexedDB.
 * Called on app startup.
 */
async function loadFromStorage(): Promise<void> {
  if (isLoaded) return;
  
  try {
    console.log('[ThreadStore] Loading from IndexedDB...');
    
    // Load all threads
    const storedThreads = await db.threads.getAll();
    threads = storedThreads;
    
    // Load messages for each thread
    const messagesMap: Record<string, Message[]> = {};
    for (const thread of storedThreads) {
      const threadMessages = await db.messages.getByThread(thread.id);
      if (threadMessages.length > 0) {
        messagesMap[thread.id] = threadMessages;
      }
    }
    messagesByThread = messagesMap;
    messagesVersion++;
    isLoaded = true;
    
    console.log('[ThreadStore] Loaded', storedThreads.length, 'threads from IndexedDB');
  } catch (e) {
    console.error('[ThreadStore] Failed to load from IndexedDB:', e);
    isLoaded = true; // Mark as loaded anyway to prevent infinite retries
  }
}

// Load threads for a specific project
async function loadProjectThreads(projectId: string): Promise<void> {
  // Ensure we've loaded from storage first
  if (!isLoaded) {
    await loadFromStorage();
  }
  
  // Ensure the currentThreadId is valid for this project
  // If the current thread doesn't belong to this project, clear the selection
  const projectThreads = getProjectThreads(projectId);
  if (currentThreadId) {
    const isCurrentValid = projectThreads.some(t => t.id === currentThreadId);
    if (!isCurrentValid) {
      // Don't auto-select - just clear the invalid selection
      // User should explicitly select a thread for the new project
      currentThreadId = null;
    }
  }
}

function reset(): void {
  threads = [];
  messagesByThread = {};
  messagesVersion++;
  currentThreadId = null;
  isLoaded = false;
}

/**
 * Clear project-specific state when switching projects.
 * Clears the current thread selection.
 */
function clearProjectState(): void {
  currentThreadId = null;
}

// Export reactive getters and actions
export const threadStore = {
  get threads() { return threads; },
  get currentThread() { return currentThread; },
  get currentThreadId() { return currentThreadId; },
  get currentMessages() { return currentMessages; },
  get isLoaded() { return isLoaded; },
  
  getProjectThreads,
  getMessages,
  getThreadMessageCount,
  loadProjectThreads,
  loadFromStorage,
  createThread,
  updateThread,
  deleteThread,
  selectThread,
  addMessage,
  updateMessage,
  clearMessages,
  syncMessages,
  loadThreads,
  reset,
  clearProjectState
};
