// Project store using Svelte 5 runes
// Stores projects with IndexedDB persistence

import { nanoid } from 'nanoid';
import type { Project } from './types.js';
import { db } from '$lib/services/indexeddb.js';

// Reactive state using Svelte 5 runes
let projects = $state<Project[]>([]);
let currentProjectId = $state<string | null>(null);
let isLoading = $state(false);
let isInitialized = $state(false);

// Derived state
const currentProject = $derived(
  projects.find((p) => p.id === currentProjectId) ?? null
);

const sortedProjects = $derived(
  [...projects].sort((a, b) => b.updatedAt - a.updatedAt)
);

// Persistence helpers
async function persistProject(project: Project): Promise<void> {
  try {
    await db.projects.save(project);
  } catch (error) {
    console.error('Failed to persist project:', error);
  }
}

// Actions
async function init(npub: string): Promise<void> {
  if (isInitialized) return;
  
  isLoading = true;
  try {
    const loadedProjects = await db.projects.getAll(npub);
    projects = loadedProjects;
    if (loadedProjects.length > 0 && !currentProjectId) {
      currentProjectId = loadedProjects.sort((a: Project, b: Project) => b.updatedAt - a.updatedAt)[0].id;
    }
    isInitialized = true;
  } catch (error) {
    console.error('Failed to load projects from IndexedDB:', error);
  } finally {
    isLoading = false;
  }
}

function createProject(title: string, npub: string): Project {
  const now = Date.now();
  const project: Project = {
    id: nanoid(),
    npub,
    title,
    createdAt: now,
    updatedAt: now
  };
  
  projects = [...projects, project];
  currentProjectId = project.id;
  
  // Persist async
  persistProject(project);
  
  return project;
}

function updateProject(id: string, updates: Partial<Pick<Project, 'title'>>): void {
  const updatedProject = projects.find(p => p.id === id);
  if (!updatedProject) return;
  
  const updated = { ...updatedProject, ...updates, updatedAt: Date.now() };
  projects = projects.map((p) => p.id === id ? updated : p);
  
  // Persist async
  persistProject(updated);
}

async function deleteProject(id: string): Promise<void> {
  projects = projects.filter((p) => p.id !== id);
  if (currentProjectId === id) {
    currentProjectId = projects[0]?.id ?? null;
  }
  
  // Delete from IndexedDB
  try {
    await db.projects.delete(id);
  } catch (error) {
    console.error('Failed to delete project from IndexedDB:', error);
  }
}

function selectProject(id: string | null): void {
  currentProjectId = id;
}

function loadProjects(loadedProjects: Project[]): void {
  projects = loadedProjects;
  if (loadedProjects.length > 0 && !currentProjectId) {
    currentProjectId = loadedProjects[0].id;
  }
}

function setLoading(loading: boolean): void {
  isLoading = loading;
}

function reset(): void {
  projects = [];
  currentProjectId = null;
  isInitialized = false;
}

// Export reactive getters and actions
export const projectStore = {
  get projects() { return projects; },
  get sortedProjects() { return sortedProjects; },
  get currentProject() { return currentProject; },
  get currentProjectId() { return currentProjectId; },
  get isLoading() { return isLoading; },
  get isInitialized() { return isInitialized; },
  
  init,
  createProject,
  updateProject,
  deleteProject,
  selectProject,
  loadProjects,
  setLoading,
  reset
};
