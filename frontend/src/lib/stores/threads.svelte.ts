// Thread store using Svelte 5 runes
// Manages chat threads within projects

import { nanoid } from 'nanoid';
import type { Thread, Message } from './types.js';

// Reactive state
let threads = $state<Thread[]>([]);
let messages = $state<Map<string, Message[]>>(new Map());
let currentThreadId = $state<string | null>(null);

// Derived state
const currentThread = $derived(
  threads.find((t) => t.id === currentThreadId) ?? null
);

const currentMessages = $derived(
  currentThreadId ? (messages.get(currentThreadId) ?? []) : []
);

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
  messages.set(thread.id, []);
  currentThreadId = thread.id;
  
  return thread;
}

function updateThread(id: string, updates: Partial<Pick<Thread, 'title' | 'metadata'>>): void {
  threads = threads.map((t) =>
    t.id === id ? { ...t, ...updates, updatedAt: Date.now() } : t
  );
}

function deleteThread(id: string): void {
  threads = threads.filter((t) => t.id !== id);
  messages.delete(id);
  
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
  
  const threadMessages = messages.get(threadId) ?? [];
  messages.set(threadId, [...threadMessages, newMessage]);
  
  // Update thread's updatedAt
  threads = threads.map((t) =>
    t.id === threadId ? { ...t, updatedAt: Date.now() } : t
  );
  
  return newMessage;
}

function updateMessage(threadId: string, messageId: string, updates: Partial<Message>): void {
  const threadMessages = messages.get(threadId);
  if (!threadMessages) return;
  
  messages.set(
    threadId,
    threadMessages.map((m) => (m.id === messageId ? { ...m, ...updates } : m))
  );
}

function clearMessages(threadId: string): void {
  messages.set(threadId, []);
}

function loadThreads(loadedThreads: Thread[], loadedMessages?: Map<string, Message[]>): void {
  threads = loadedThreads;
  if (loadedMessages) {
    messages = loadedMessages;
  }
}

// Export reactive getters and actions
export const threadStore = {
  get threads() { return threads; },
  get currentThread() { return currentThread; },
  get currentThreadId() { return currentThreadId; },
  get currentMessages() { return currentMessages; },
  
  getProjectThreads,
  createThread,
  updateThread,
  deleteThread,
  selectThread,
  addMessage,
  updateMessage,
  clearMessages,
  loadThreads
};

