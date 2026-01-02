# Frontend Architecture

Socratic Seminar's frontend is a modern, local-first web application designed for high-performance interactive editing and AI collaboration. It is built as a Single Page Application (SPA) that runs entirely in the user's browser.

## Technology Stack

- **Svelte 5** with runes for fine-grained reactivity and state management.
- **SvelteKit** for routing and application structure.
- **Tailwind CSS** for a responsive, utility-first design system.
- **shadcn-svelte** for high-quality, accessible UI components.
- **CodeMirror 6** for the powerful, extensible [Tabbed Editor](tabbed_editor.md).
- **IndexedDB** for robust, [Local Storage](local_storage.md).
- **CypherTap** (submodule) for [Nostr Authentication](nostr.md) and Bitcoin eCash payments.

## Core Concepts

The frontend is organized around three pillars:

### 1. Unified State Management
The application's logic is encapsulated in specialized stores using Svelte 5 runes. This allows for complex, inter-dependent state (like syncing an agent's proposed edits to a document) to be handled predictably and efficiently.
- See [State Management](state_management.md) for details.

### 2. Local-First Persistence
Privacy and speed are paramount. All user data stays in the browser's IndexedDB, ensuring that the app is fast, works offline, and respects user sovereignty.
- See [Local Storage & Persistence](local_storage.md) for details.

### 3. Project-Based Workflow
The UI is optimized for focused research. Content is organized into [Projects](projects.md), which group together chat [Threads](agents.md), versioned artifacts, and external [Sources](sources.md).

## Key Components

### Workspace Layout
The `WorkspaceLayout.svelte` provides the main three-panel interface:
- **Left Sidebar**: Project and item navigation.
- **Center/Main**: The [Tabbed Editor](tabbed_editor.md) for active work.
- **Right Panel**: (Contextual) Often used for agent controls, metadata, or side-by-side comparison.

### Chat & Agent Interaction
The `ChatPanel.svelte` handles the communication with LangGraph agents, including streaming responses and specialized UI for agent interrupts.
- See [Agent Architecture](agents.md) for details on how the frontend handles interrupts.

### Artifact Editing
The [Tabbed Editor](tabbed_editor.md) is a custom implementation based on CodeMirror 6, supporting live previews, versioning, and inline diffs for AI-assisted editing.

## Agent Communication

The frontend communicates directly with the LangGraph server using the `@langchain/langgraph-sdk`. This allows for:
- **Real-time Streaming**: Watch the agent's response develop token-by-token.
- **Interrupt Handling**: Seamlessly pause for user input or client-side tool execution.
- **State Synchronization**: Keep the local chat history in sync with the agent's internal state.


# Project Management

Socratic Seminar uses a project-based organization to group related research, threads, and artifacts. Projects are the top-level container for all user data.

## Overview

A project acts as a siloed workspace. When a project is selected, the sidebar and workspace only show content belonging to that specific project. This helps users maintain focus and context during deep research.

## Project Structure

Each project contains:
- **Threads**: Chat conversations with AI agents.
- **Artifacts**: Versioned Markdown documents.
- **Sources**: Scraped web content and reference materials.
- **Metadata**: Title, creation date, tags, and the owner's Nostr public key (npub).

## The Project Store

Managed by `projects.svelte.ts`, the project store handles the lifecycle of projects:

- **Initialization**: Loads all projects associated with a user's `npub` from IndexedDB on startup.
- **Reactive State**: Uses Svelte 5 `$state` for the project list and `$derived` for the currently selected project.
- **CRUD Operations**:
    - `createProject(title, npub)`: Scaffolds a new project with default tags.
    - `updateProject(id, updates)`: Updates project metadata and persists to storage.
    - `deleteProject(id)`: Removes the project and its associated data (via cascade in logic).
- **Tagging**: Projects support custom tags (e.g., "Draft", "Final", "notes") for further organization.

## Persistence

Projects are persisted in the `projects` table of the browser's IndexedDB. They are indexed by the user's `npub`, ensuring that multiple users sharing a browser (with different Nostr keys) only see their own work.

## UI Integration

### Project Sidebar
The `ProjectSidebar.svelte` component provides navigation between:
1. **Projects**: A dropdown or list to switch between high-level workspaces.
2. **Project Items**: A nested tree or list showing the threads and artifacts within the active project.

### Project Dashboard
The `ProjectDashboard.svelte` (if available) or main workspace view provides an overview of the project's recent activity and quick access to its most important items.

# State Management

Socratic Seminar leverages **Svelte 5 Runes** for its entire state management layer. This modern approach provides fine-grained reactivity, excellent TypeScript support, and a significant reduction in boilerplate compared to traditional Svelte 4 stores.

## Core Principles

1.  **Runes-Based**: Uses `$state`, `$derived`, and `$effect` for reactivity.
2.  **Singleton Stores**: Stores are implemented as singleton objects exported from `.svelte.ts` files.
3.  **Encapsulated Logic**: Reactive state is kept private (within the file scope), and only getters and action functions are exposed.
4.  **Local-First Sync**: Stores are tightly integrated with IndexedDB for transparent persistence.

## Store Architecture

The application is divided into several specialized stores:

| Store | File | Responsibility |
| :--- | :--- | :--- |
| **Project Store** | `projects.svelte.ts` | High-level workspace management and project CRUD. |
| **Thread Store** | `threads.svelte.ts` | Chat history, message management, and agent status. |
| **Artifact Store** | `artifacts.svelte.ts` | Document content, versioning, and pending agent patches. |
| **Source Store** | `sources.svelte.ts` | External reference materials and scraped content. |
| **Agent Store** | `agent.svelte.ts` | LangGraph connection state, streaming events, and interrupts. |
| **Workspace Store** | `workspace.svelte.ts` | UI state: active tabs, sidebar collapse, modal visibility. |

## Example: The Artifact Store

The `artifactStore` demonstrates the power of runes for complex state:

```typescript
// artifacts.svelte.ts

// 1. Private reactive state
let artifacts = $state<Artifact[]>([]);
let currentArtifactId = $state<string | null>(null);

// 2. Derived state for UI efficiency
const currentArtifact = $derived(
  artifacts.find((a) => a.id === currentArtifactId) ?? null
);

// 3. Exported interface
export const artifactStore = {
  get artifacts() { return artifacts; },
  get currentArtifact() { return currentArtifact; },
  
  // Actions
  selectArtifact(id: string | null) {
    currentArtifactId = id;
  },
  // ...
};
```

## Reactivity and Persistence

To bridge the gap between reactive memory and persistent storage, stores follow a "Memory-First, Async-Persistence" pattern:

1.  **Action Triggered**: A user action (e.g., `updateArtifact`) modifies the `$state` variable.
2.  **UI Updates**: Svelte instantly updates all components depending on that state.
3.  **Async Save**: The store triggers an asynchronous call to the `db` service (IndexedDB) to mirror the change.
4.  **Dirty Tracking**: For expensive operations (like document saves), an `isDirty` flag is used to debounce persistence until the user stops typing or navigates away.

## Advanced Patterns

### Derived.by
Used for complex computations that require multiple dependencies or logic, such as `currentArtifactContent` which depends on both the `currentArtifactId` and the `versions` array within that artifact.

### Untrack
Used in initialization and sync logic to read state values without creating a reactive subscription, preventing infinite update loops when stores interact with each other.

