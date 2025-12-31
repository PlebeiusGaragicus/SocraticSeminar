// Workspace store for managing multi-column tabbed layout
import type { TabItem, TabType } from './types.js';
import { artifactStore } from './artifacts.svelte.js';
import { threadStore } from './threads.svelte.js';
import { projectStore } from './projects.svelte.js';
import { agentStore } from './agent.svelte.js';

let leftTabs = $state<TabItem[]>([]);
let rightTabs = $state<TabItem[]>([]);
let activeLeftTabId = $state<string | null>(null);
let activeRightTabId = $state<string | null>(null);
let rightPanelCollapsed = $state(true);
let forceSingleColumn = $state(false);

/**
 * Open an item in the workspace.
 */
function openItem(id: string, type: TabType, targetColumn?: 'left' | 'right') {
  // Check if already open
  if (leftTabs.some(t => t.id === id)) {
    activeLeftTabId = id;
    return;
  }
  if (rightTabs.some(t => t.id === id)) {
    activeRightTabId = id;
    rightPanelCollapsed = false;
    forceSingleColumn = false;
    return;
  }

  const newItem: TabItem = { id, type };

  // Determine which column to open in
  if (targetColumn === 'left') {
    leftTabs = [...leftTabs, newItem];
    activeLeftTabId = id;
  } else if (targetColumn === 'right') {
    rightTabs = [...rightTabs, newItem];
    activeRightTabId = id;
    rightPanelCollapsed = false;
    forceSingleColumn = false;
  } else {
    // Default logic
    if (leftTabs.length === 0 || forceSingleColumn) {
      leftTabs = [...leftTabs, newItem];
      activeLeftTabId = id;
    } else {
      rightTabs = [...rightTabs, newItem];
      activeRightTabId = id;
      rightPanelCollapsed = false;
    }
  }

  if (type === 'artifact') artifactStore.selectArtifact(id);
  else threadStore.selectThread(id);
}

function createNewFile(column: 'left' | 'right' = 'left') {
  const projectId = projectStore.currentProjectId;
  if (!projectId) return;
  
  const title = `untitled-${Date.now().toString().slice(-4)}.md`;
  const artifact = artifactStore.createArtifact(projectId, title, '');
  openItem(artifact.id, 'artifact', column);
}

function createNewThread(column: 'left' | 'right' = 'left') {
  const projectId = projectStore.currentProjectId;
  if (!projectId) return;

  agentStore.resetStream();
  const threads = threadStore.getProjectThreads(projectId);
  const existingEmpty = threads.find(t => threadStore.getThreadMessageCount(t.id) === 0);
  
  if (existingEmpty) {
    openItem(existingEmpty.id, 'thread', column);
  } else {
    const thread = threadStore.createThread(projectId, 'New Chat');
    openItem(thread.id, 'thread', column);
  }
}

function selectTab(id: string, column: 'left' | 'right') {
  if (column === 'left') {
    activeLeftTabId = id;
    const tab = leftTabs.find(t => t.id === id);
    if (tab?.type === 'artifact') artifactStore.selectArtifact(id);
    else if (tab?.type === 'thread') threadStore.selectThread(id);
  } else {
    activeRightTabId = id;
    const tab = rightTabs.find(t => t.id === id);
    if (tab?.type === 'artifact') artifactStore.selectArtifact(id);
    else if (tab?.type === 'thread') threadStore.selectThread(id);
  }
}

function closeTab(id: string, column: 'left' | 'right') {
  if (column === 'left') {
    leftTabs = leftTabs.filter(t => t.id !== id);
    if (activeLeftTabId === id) {
      activeLeftTabId = leftTabs[leftTabs.length - 1]?.id ?? null;
    }
  } else {
    rightTabs = rightTabs.filter(t => t.id !== id);
    if (activeRightTabId === id) {
      activeRightTabId = rightTabs[rightTabs.length - 1]?.id ?? null;
    }
    if (rightTabs.length === 0) {
      rightPanelCollapsed = true;
    }
  }
}

/**
 * Close the right panel and move all its tabs to the left.
 */
function collapseRightPanel() {
  leftTabs = [...leftTabs, ...rightTabs];
  if (!activeLeftTabId && activeRightTabId) {
    activeLeftTabId = activeRightTabId;
  }
  rightTabs = [];
  activeRightTabId = null;
  rightPanelCollapsed = true;
  forceSingleColumn = true;
}

function toggleRightPanel() {
  rightPanelCollapsed = !rightPanelCollapsed;
  if (!rightPanelCollapsed) {
    forceSingleColumn = false;
  }
}

function clearProjectState() {
  leftTabs = [];
  rightTabs = [];
  activeLeftTabId = null;
  activeRightTabId = null;
  rightPanelCollapsed = true;
  forceSingleColumn = false;
}

export const workspaceStore = {
  get leftTabs() { return leftTabs; },
  get rightTabs() { return rightTabs; },
  get activeLeftTabId() { return activeLeftTabId; },
  get activeRightTabId() { return activeRightTabId; },
  get rightPanelCollapsed() { return rightPanelCollapsed; },
  get forceSingleColumn() { return forceSingleColumn; },
  
  openItem,
  createNewFile,
  createNewThread,
  selectTab,
  closeTab,
  collapseRightPanel,
  toggleRightPanel,
  clearProjectState
};

