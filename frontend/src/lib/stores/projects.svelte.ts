// Project store using Svelte 5 runes
// Stores projects locally in memory (IndexedDB integration can be added later)

import { nanoid } from 'nanoid';
import type { Project } from './types';

// Reactive state using Svelte 5 runes
let projects = $state<Project[]>([]);
let currentProjectId = $state<string | null>(null);
let isLoading = $state(false);

// Derived state
const currentProject = $derived(
  projects.find((p) => p.id === currentProjectId) ?? null
);

const sortedProjects = $derived(
  [...projects].sort((a, b) => b.updatedAt - a.updatedAt)
);

// Actions
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
  
  return project;
}

function updateProject(id: string, updates: Partial<Pick<Project, 'title'>>): void {
  projects = projects.map((p) =>
    p.id === id ? { ...p, ...updates, updatedAt: Date.now() } : p
  );
}

function deleteProject(id: string): void {
  projects = projects.filter((p) => p.id !== id);
  if (currentProjectId === id) {
    currentProjectId = projects[0]?.id ?? null;
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

// Export reactive getters and actions
export const projectStore = {
  get projects() { return projects; },
  get sortedProjects() { return sortedProjects; },
  get currentProject() { return currentProject; },
  get currentProjectId() { return currentProjectId; },
  get isLoading() { return isLoading; },
  
  createProject,
  updateProject,
  deleteProject,
  selectProject,
  loadProjects,
  setLoading
};

