# Tabbed Editor

The Tabbed Editor is the central workspace of Socratic Seminar, enabling users to seamlessly transition between intellectual discourse and document refinement. It supports a multi-document workflow where chats, artifacts, and external sources coexist in a unified, interactive environment.

## Overview

The editor is built to handle three primary types of content:
- **Artifacts**: Versioned Markdown documents (papers, notes, drafts).
- **Threads**: Chat conversations with AI agents.
- **Sources**: External reference materials and scraped content.

## Architecture

The implementation leverages a modern, reactive stack:

- **Svelte 5 & Runes**: The UI is powered by `TabbedPanel.svelte`, using Svelte 5 runes (`$state`, `$derived`, `$effect`) for high-performance reactivity.
- **CodeMirror 6**: A robust, extensible text editor used for editing Artifacts.
- **Custom Extensions**:
    - **Live Preview**: Real-time rendering of Markdown formatting.
    - **Inline Diffs**: Visualizes agent-proposed changes directly within the document.
- **Artifact Store**: Managed by `artifacts.svelte.ts`, providing:
    - **Versioning**: Each save can create a new version, allowing for easy history navigation.
    - **Persistence**: Automatic sync with IndexedDB via `db.artifacts`.
    - **Live Updates**: Synchronizes changes between the editor and the rest of the application.

## Core Features

### 1. Multi-Tab Workflow
Users can open multiple documents and chats simultaneously.
- **Drag and Drop**: Tabs can be rearranged within a panel or moved between the left and right panels for side-by-side comparison.
- **Split Panels**: The workspace supports a dual-column layout. Users can split their view to, for example, have a research source on the left and a draft on the right.
- **Panel Management**: Integrated controls allow for collapsing or expanding panels to maximize screen real estate for deep work.

### 2. Tab Bar Intelligence
The tab bar provides immediate context about the state of various project items:
- **Activity Indicators**: A small blue dot indicates "unviewed" changes, such as when an agent has updated an artifact or a thread while it was in the background.
- **Agent Status**: Threads display a status dot (Green: Idle, Blue: Busy/Thinking, Orange: Interrupted/Awaiting Input, Red: Error) so users can monitor agent progress at a glance.

### 3. Unified Creation & Search
The "New Tab" (`+`) menu serves as a central hub for workspace navigation:
- **Integrated Creation**: Quick access to create new artifacts, start new chat threads, or add external sources.
- **Fuzzy Search**: A built-in search bar allows users to quickly jump to any existing file, chat, or source by name, reducing the need to navigate via the sidebar.

### 4. Versioning and Navigation
The editor tracks the history of every Artifact. Users can:
- **Version Picker**: Navigate through versions using the version picker UI (e.g., `v3/5`).
- **Revert/Compare**: Easily move back to previous states or compare the current draft against earlier iterations.

### 5. Source Integration
External materials added to the project are rendered in a focused "Source Viewer":
- **Clean Reading View**: Stripped-down, readable version of scraped content.
- **Direct Linkage**: A "View Original" link allows users to jump back to the live source URL at any time.

### 6. Auto-save and Dirty State
The editor implements a robust "dirty state" tracking system to ensure data integrity while minimizing expensive persistence operations.

- **Reactive Dirty Tracking**: The `artifactStore` maintains an `isDirty` flag for each artifact. This flag is set to `true` via `updateLiveContent()` as soon as the user makes any change in the CodeMirror editor.
- **Dual-Layer Content Management**:
    - **`liveContentMap`**: A high-frequency reactive map that stores the "current" text as the user types. This is used for UI updates and by agents who need the most recent context.
    - **Persistent Versions**: The actual `ArtifactVersion` array in IndexedDB. Data is only moved from the live map to the version history during a "Save" event.
- **Debounced Persistence**: To avoid overwhelming IndexedDB, the `TabbedPanel` component uses a 500ms debounce timer (`scheduleAutoSave`). Continuous typing resets this timer; the save only fires once the user pauses.
- **Safety Mechanisms**: The system implements "Force Saves" to prevent data loss:
    - **Tab Switching**: Before an active artifact is swapped out, the current content is flushed to the store.
    - **Blur Events**: Losing focus on the editor window triggers an immediate save if the artifact is dirty.
    - **Lifecycle Hooks**: `onDestroy` ensures all pending changes across all open tabs are persisted before the component is unmounted.

## Co-Editing with Agents

Socratic Seminar treats agents as first-class collaborators in the editing process. Rather than overwriting your work, agents propose changes that you review in real-time within the editor.

### 1. The Patching Mechanism
Agents use the `patch_file` tool to suggest edits. Unlike a simple "replace all," this tool is precision-engineered for collaboration:
- **Search & Replace**: Agents provide a `search` string (the exact text to change) and a `replace` string (the new text).
- **Multi-Patch Batches**: Agents are instructed to group related changes into a single tool call. This allows you to review a coherent set of improvements (e.g., "Refine the introduction and fix three typos") as one logical unit.
- **Context Awareness**: By using exact string matching, the system ensures that changes are only proposed if the agent's internal model of the document matches your current version.

### 2. Visualizing Changes (Inline Diffs)
When an agent proposes edits, the Tabbed Editor uses a custom CodeMirror extension to render them as **Inline Diffs**, similar to "Track Changes" in traditional word processors:
- **Deletions**: The original text found by the `search` string is highlighted in red with a strikethrough.
- **Additions**: The proposed `replace` text is inserted immediately after as a green, highlighted block.
- **Non-Destructive**: These decorations are purely visual. Your actual document content remains unchanged until you explicitly decide to accept the suggestions.

### 3. User Control (Human-in-the-Loop)
You remain the final authority on all document changes:
- **Granular Review**: You can read through the document and see exactly how each change fits into your existing narrative.
- **Accept/Reject**: A blue header appears when patches are pending, allowing you to "Accept All" or "Reject All" with a single click.
- **Direct Interaction**: The system manages these as `PendingPatch` objects in the `artifactStore` until they are resolved.

### 4. Technical Implementation
The co-editing flow is powered by coordination between the agent middleware and the frontend store:

**Agent Side (`client_tools.py`)**:
The agent's `patch_file` call triggers a LangGraph `interrupt`. This pauses the agent and sends the patch data to the frontend.

**Frontend Store (`artifacts.svelte.ts`)**:
```typescript
function addPendingPatches(artifactId, patches) {
  const newPatches = patches.map(p => ({
    id: nanoid(),
    artifactId,
    search: p.search,
    replace: p.replace,
    status: 'pending'
  }));
  pendingPatches = [...pendingPatches, ...newPatches];
}
```

**UI Rendering (`inlineDiff.ts`)**:
A CodeMirror `StateField` scans the document for the `search` strings of all pending patches and applies decorations:
```typescript
function buildDecorations(content, patches, callbacks) {
  const start = content.indexOf(patch.search);
  if (start !== -1) {
    // 1. Add 'cm-deletion' mark to original text
    builder.add(start, start + patch.search.length, deletionMark);
    // 2. Add 'InlineReplacementWidget' showing patch.replace
    builder.add(end, end, widget);
  }
}
```

### 7. Local-First Persistence
All edits are saved locally in the browser's IndexedDB. This ensures that progress is never lost, even if the browser is closed unexpectedly, without requiring a central server.

## User Story

> **The Researcher's Workflow**
>
> *As a researcher* investigating the history of monetary policy, I want to have my primary research paper open in the main editor tab while simultaneously chatting with a Socratic Tutor in a split panel.
>
> When the Tutor identifies a logical inconsistency in my third paragraph, I want it to propose a revision. I should see the suggested text highlighted in green over my original text. I can then read the suggestion, realize it strengthens my argument, and click "Accept" to instantly update my paper. Finally, I'll switch to a "Sources" tab to verify a quote from a scraped PDF, all without leaving my focused workspace.

## Implementation Details

The `TabbedPanel.svelte` component coordinates the rendering of the active tab:

```svelte
{#if activeTab?.type === 'thread'}
  <ChatPanel threadId={activeTabId} />
{:else if activeTab?.type === 'artifact'}
  <div use:setEditorContainer class="flex-1 overflow-hidden bg-zinc-950"></div>
{:else if activeTab?.type === 'source'}
  <div class="flex-1 overflow-y-auto p-8 prose prose-invert">
    {activeSource.content}
  </div>
{/if}
```

The `artifactStore` handles the logic for applying agent patches and managing the dirty state:

```typescript
// From artifacts.svelte.ts
function updateLiveContent(id: string, content: string): void {
  liveContentMap[id] = content;
  
  // Mark the artifact as dirty
  const artifact = artifacts.find(a => a.id === id);
  if (artifact && !artifact.isDirty) {
    artifacts = artifacts.map(a => a.id === id ? { ...a, isDirty: true } : a);
  }
}

async function saveArtifactNow(id: string): Promise<void> {
  const artifact = artifacts.find(a => a.id === id);
  const liveContent = liveContentMap[id];
  
  // ... update version in place and clear dirty flag ...
  await persistArtifact(updatedArtifact);
}
```

The `TabbedPanel` component manages the timing of these saves:

```typescript
// From TabbedPanel.svelte
function scheduleAutoSave(artifactId: string) {
  const existing = saveTimeouts.get(artifactId);
  if (existing) clearTimeout(existing);
  
  const timeout = setTimeout(() => {
    saveToArtifact(artifactId, false); // Autosave updates current version
  }, AUTOSAVE_DELAY);
  
  saveTimeouts.set(artifactId, timeout);
}
```


# Sources

Sources are external reference materials that you add to a project to provide context for your research and for AI agents to analyze.

## Overview

A source is typically a scraped web page, a PDF, or a snippet of text from an external site. Once added to a project, it becomes a permanent part of that workspace's knowledge base.

## Adding Sources

Users can add sources via the **New Source Modal**:
-   **URL Scraping**: Enter a URL, and the system (via a background service) extracts the core content, stripping away ads and navigation.
-   **Manual Entry**: Paste text directly and provide a title and optional source URL.
-   **File Upload**: (Future) Support for uploading PDFs and other document types.

## Source Store

Managed by `sources.svelte.ts`, the source store provides:
-   **Project Filtering**: Quick access to all sources associated with the active project.
-   **Persistence**: Automatic saving of scraped content to IndexedDB.
-   **Reactive Selection**: Tracks which source is currently being viewed in the [Tabbed Editor](tabbed_editor.md).

## Usage in Workflow

### 1. Research
Sources provide a focused reading environment. The **Source Viewer** in the Tabbed Editor presents content in a clean, Markdown-like format, making it easy to read long-form articles without distractions.

### 2. Agent Context
When you chat with an agent in a project, the agent can be given access to your sources. This allows the Socratic Tutor to:
-   Reference specific quotes from your research.
-   Identify contradictions between different sources.
-   Help you synthesize information from multiple external materials into your own artifacts.

### 3. Linking
Every source maintains its original URL, allowing you to quickly jump back to the live website for verification or to see the original formatting.

## Technical Details

Sources are stored as plain objects in IndexedDB:
```typescript
interface Source {
  id: string;
  projectId: string;
  title: string;
  url: string;
  content: string; // The full scraped text
  metadata: Record<string, any>;
  createdAt: number;
  updatedAt: number;
}
```

