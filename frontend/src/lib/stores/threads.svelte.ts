// Thread store using Svelte 5 runes
// Manages chat threads within projects

import { nanoid } from 'nanoid';
import type { Thread, Message } from './types.js';

// Reactive state
let threads = $state<Thread[]>([]);
// Use a plain object instead of Map for better Svelte 5 reactivity
let messagesByThread = $state<Record<string, Message[]>>({});
let currentThreadId = $state<string | null>(null);

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

// Actions
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
  
  return thread;
}

function updateThread(id: string, updates: Partial<Pick<Thread, 'title' | 'metadata' | 'langGraphThreadId'>>): void {
  threads = threads.map((t) =>
    t.id === id ? { ...t, ...updates, updatedAt: Date.now() } : t
  );
}

function deleteThread(id: string): void {
  threads = threads.filter((t) => t.id !== id);
  const { [id]: removed, ...rest } = messagesByThread;
  messagesByThread = rest;
  messagesVersion++;
  
  if (currentThreadId === id) {
    currentThreadId = null;
  }
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
  // Create new object to trigger reactivity
  messagesByThread = {
    ...messagesByThread,
    [threadId]: [...threadMessages, newMessage]
  };
  messagesVersion++;
  
  console.log('[ThreadStore] Added message to thread', threadId, 'Total messages:', messagesByThread[threadId]?.length);
  
  // Update thread's updatedAt
  threads = threads.map((t) =>
    t.id === threadId ? { ...t, updatedAt: Date.now() } : t
  );
  
  return newMessage;
}

function updateMessage(threadId: string, messageId: string, updates: Partial<Message>): void {
  const threadMessages = messagesByThread[threadId];
  if (!threadMessages) return;
  
  messagesByThread = {
    ...messagesByThread,
    [threadId]: threadMessages.map((m) => (m.id === messageId ? { ...m, ...updates } : m))
  };
  messagesVersion++;
}

function clearMessages(threadId: string): void {
  messagesByThread = { ...messagesByThread, [threadId]: [] };
  messagesVersion++;
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

// Load threads for a specific project (threads are currently in-memory only)
function loadProjectThreads(projectId: string): void {
  // Threads are stored in memory for now
  // In the future, this could load from IndexedDB or LangGraph server
  // For now, just ensure the currentThreadId is valid for this project
  const projectThreads = getProjectThreads(projectId);
  if (currentThreadId) {
    const isCurrentValid = projectThreads.some(t => t.id === currentThreadId);
    if (!isCurrentValid) {
      currentThreadId = projectThreads[0]?.id ?? null;
    }
  }
}

function reset(): void {
  threads = [];
  messagesByThread = {};
  messagesVersion++;
  currentThreadId = null;
}

// Export reactive getters and actions
export const threadStore = {
  get threads() { return threads; },
  get currentThread() { return currentThread; },
  get currentThreadId() { return currentThreadId; },
  get currentMessages() { return currentMessages; },
  
  getProjectThreads,
  getMessages,
  getThreadMessageCount,
  loadProjectThreads,
  createThread,
  updateThread,
  deleteThread,
  selectThread,
  addMessage,
  updateMessage,
  clearMessages,
  loadThreads,
  reset
};
