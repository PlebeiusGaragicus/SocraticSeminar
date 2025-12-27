// Assistants store using Svelte 5 runes
// Manages available agents from LangGraph server

import { Client, type Assistant } from '@langchain/langgraph-sdk';

// Configuration
const LANGGRAPH_URL = import.meta.env.PUBLIC_LANGGRAPH_URL ?? 'http://localhost:54367';

// LangGraph client (lazy initialized)
let client: Client | null = null;

function getClient(): Client {
  if (!client) {
    client = new Client({ apiUrl: LANGGRAPH_URL });
  }
  return client;
}

// Reactive state
let assistants = $state<Assistant[]>([]);
let selectedAssistantId = $state<string | null>(null);
let isLoading = $state(false);
let error = $state<string | null>(null);

// Derived state
const selectedAssistant = $derived(
  assistants.find((a) => a.assistant_id === selectedAssistantId) ?? null
);

// Actions
async function fetchAssistants(): Promise<void> {
  isLoading = true;
  error = null;

  try {
    const lgClient = getClient();
    const result = await lgClient.assistants.search({});
    assistants = result;

    // Auto-select first assistant if none selected
    if (!selectedAssistantId && result.length > 0) {
      selectedAssistantId = result[0].assistant_id;
    }
  } catch (e) {
    const errorMessage = e instanceof Error ? e.message : 'Failed to fetch assistants';
    error = errorMessage;
    console.error('Failed to fetch assistants:', e);
  } finally {
    isLoading = false;
  }
}

function selectAssistant(id: string): void {
  if (assistants.find((a) => a.assistant_id === id)) {
    selectedAssistantId = id;
  }
}

function clearError(): void {
  error = null;
}

// Export reactive getters and actions
export const assistantStore = {
  get assistants() {
    return assistants;
  },
  get selectedAssistant() {
    return selectedAssistant;
  },
  get selectedAssistantId() {
    return selectedAssistantId;
  },
  get isLoading() {
    return isLoading;
  },
  get error() {
    return error;
  },

  fetchAssistants,
  selectAssistant,
  clearError,
  getClient
};

