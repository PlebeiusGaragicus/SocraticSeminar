// Workspace store for managing multi-column tabbed layout
import type { TabItem, TabType } from './types.js';
import { artifactStore } from './artifacts.svelte.js';
import { threadStore } from './threads.svelte.js';
import { sourceStore } from './sources.svelte.js';
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
  // 1. If targetColumn is specified, check that column first
  if (targetColumn === 'left' && leftTabs.some(t => t.id === id)) {
    activeLeftTabId = id;
    return;
  }
  if (targetColumn === 'right' && rightTabs.some(t => t.id === id)) {
    activeRightTabId = id;
    rightPanelCollapsed = false;
    forceSingleColumn = false;
    return;
  }

  // 2. If it's in the OTHER column and targetColumn is specified, move it
  if (targetColumn === 'left' && rightTabs.some(t => t.id === id)) {
    moveTab(id, 'right', 'left');
    return;
  }
  if (targetColumn === 'right' && leftTabs.some(t => t.id === id)) {
    moveTab(id, 'left', 'right');
    return;
  }

  // 3. If no target column, check if it's already open anywhere
  if (!targetColumn) {
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
    
    // Default logic: where to open new item
    if (leftTabs.length === 0 || forceSingleColumn) {
      targetColumn = 'left';
    } else {
      targetColumn = 'right';
    }
  }

  const newItem: TabItem = { id, type };

  // 4. Actually open it in the target column
  if (targetColumn === 'left') {
    leftTabs = [...leftTabs, newItem];
    activeLeftTabId = id;
  } else {
    rightTabs = [...rightTabs, newItem];
    activeRightTabId = id;
    rightPanelCollapsed = false;
    forceSingleColumn = false;
  }

  if (type === 'artifact') artifactStore.selectArtifact(id);
  else if (type === 'thread') threadStore.selectThread(id);
  else if (type === 'source') sourceStore.selectSource(id);
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
    else if (tab?.type === 'source') sourceStore.selectSource(id);
  } else {
    activeRightTabId = id;
    const tab = rightTabs.find(t => t.id === id);
    if (tab?.type === 'artifact') artifactStore.selectArtifact(id);
    else if (tab?.type === 'thread') threadStore.selectThread(id);
    else if (tab?.type === 'source') sourceStore.selectSource(id);
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
  }
}

/**
 * Close an item from all columns it might be in.
 * Useful when an item is deleted.
 */
function closeItemGlobally(id: string) {
  // Check both columns as an item might (theoretically) be in both 
  // or we don't know which one it's in.
  if (leftTabs.some(t => t.id === id)) {
    closeTab(id, 'left');
  }
  if (rightTabs.some(t => t.id === id)) {
    closeTab(id, 'right');
  }
}

/**
 * Move a tab from one column to another.
 */
function moveTab(id: string, fromColumn: 'left' | 'right', toColumn: 'left' | 'right') {
  if (fromColumn === toColumn) return;

  const tabToMove = (fromColumn === 'left' ? leftTabs : rightTabs).find(t => t.id === id);
  if (!tabToMove) return;

  // Remove from source
  if (fromColumn === 'left') {
    leftTabs = leftTabs.filter(t => t.id !== id);
    if (activeLeftTabId === id) {
      activeLeftTabId = leftTabs[leftTabs.length - 1]?.id ?? null;
    }
  } else {
    rightTabs = rightTabs.filter(t => t.id !== id);
    if (activeRightTabId === id) {
      activeRightTabId = rightTabs[rightTabs.length - 1]?.id ?? null;
    }
    // We don't auto-collapse here to allow empty right panel
  }

  // Add to target
  if (toColumn === 'left') {
    if (!leftTabs.some(t => t.id === id)) {
      leftTabs = [...leftTabs, tabToMove];
    }
    activeLeftTabId = id;
  } else {
    if (!rightTabs.some(t => t.id === id)) {
      rightTabs = [...rightTabs, tabToMove];
    }
    activeRightTabId = id;
    rightPanelCollapsed = false;
    forceSingleColumn = false;
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
  moveTab,
  closeItemGlobally,
  collapseRightPanel,
  toggleRightPanel,
  clearProjectState
};

