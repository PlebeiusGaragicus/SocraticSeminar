/**
 * Tool Executor Service
 * 
 * Executes tool calls locally against IndexedDB.
 * This is the client-side counterpart to the tools defined in ClientToolsMiddleware.
 * 
 * Flow:
 * 1. Agent calls a tool (list_files, read_file, write_file, etc.)
 * 2. ClientToolsMiddleware interrupts with tool_calls
 * 3. Frontend receives interrupt with pending tool calls
 * 4. This service executes tools against local IndexedDB
 * 5. Frontend resumes the graph with tool results
 * 
 * Read operations (list_files, read_file, search_files, grep_files, glob_files) and write operations (write_file, patch_file) require human approval.
 */

import { db } from './indexeddb.js';
import { artifactStore } from '../stores/artifacts.svelte.js';
import { sourceStore } from '../stores/sources.svelte.js';
import type { ToolCall, ToolResult, ProjectFile, Artifact, ArtifactVersion, Bibliography } from '../stores/types.js';

/**
 * Execute a single tool call and return the result.
 */
export async function executeToolCall(
  toolCall: ToolCall,
  projectId: string
): Promise<ToolResult> {
  const { id: toolCallId, name, args } = toolCall;

  try {
    switch (name) {
      case 'list_files':
        return await executeListFiles(
          toolCallId, 
          name, 
          projectId,
          args.file_type as 'artifact' | 'document' | 'code' | undefined
        );

      case 'read_file':
        // Support both file_id (new) and args.file_id (legacy)
        const fileId = (args.file_id as string) || (args.fileId as string);
        return await executeReadFile(toolCallId, name, fileId);

      case 'get_file':
        // Legacy name, same as read_file
        return await executeReadFile(toolCallId, name, args.file_id as string);

      case 'search_files':
        return await executeSearchFiles(
          toolCallId,
          name,
          projectId,
          args.query as string,
          (args.top_k as number) || 5
        );

      case 'write_file':
        return executeWriteFile(
          toolCallId,
          name,
          projectId,
          args.title as string,
          args.content as string,
          (args.file_type as 'artifact' | 'document' | 'code') || 'artifact'
        );

      case 'patch_file':
        return await executePatchFile(
          toolCallId,
          name,
          args.file_id as string,
          args.patches as Array<{search: string, replace: string}> | undefined,
          args.description as string || '',
          args.search as string,
          args.replace as string
        );

      case 'grep_files':
        return await executeGrepFiles(
          toolCallId,
          name,
          projectId,
          args.pattern as string,
          args.glob_pattern as string | undefined,
          (args.case_sensitive as boolean) || false
        );

      case 'glob_files':
        return await executeGlobFiles(
          toolCallId,
          name,
          projectId,
          args.pattern as string
        );

      case 'create_source':
        return executeCreateSource(
          toolCallId,
          name,
          projectId,
          args.url as string,
          args.title as string,
          args.content as string,
          {
            author: args.author as string | undefined,
            publishedDate: args.published_date as string | undefined,
            publisher: args.publisher as string | undefined,
            resourceType: args.resource_type as string | undefined,
          }
        );

      default:
        return {
          tool_call_id: toolCallId,
          name,
          content: '',
          error: `Unknown tool: ${name}`
        };
    }
  } catch (error) {
    const errorMessage = error instanceof Error ? error.message : 'Unknown error';
    console.error(`[ToolExecutor] Error executing ${name}:`, error);
    return {
      tool_call_id: toolCallId,
      name,
      content: '',
      error: errorMessage
    };
  }
}

/**
 * Execute multiple tool calls in parallel.
 */
export async function executeToolCalls(
  toolCalls: ToolCall[],
  projectId: string
): Promise<ToolResult[]> {
  return Promise.all(
    toolCalls.map(tc => executeToolCall(tc, projectId))
  );
}

/**
 * list_files(file_type?) - List files in the project, optionally filtered
 */
async function executeListFiles(
  toolCallId: string,
  toolName: string,
  projectId: string,
  filterFileType?: 'artifact' | 'document' | 'code'
): Promise<ToolResult> {
  let artifacts = await db.artifacts.getByProject(projectId);
  
  // Filter by file_type if provided (for now all are 'artifact')
  // This filter is a placeholder for when we support different types
  
  const files: ProjectFile[] = artifacts.map(artifact => ({
    id: artifact.id,
    title: artifact.versions[artifact.currentVersionIndex]?.title || 'Untitled',
    file_type: 'artifact' as const,
  }));

  return {
    tool_call_id: toolCallId,
    name: toolName,
    content: JSON.stringify(files, null, 2)
  };
}

/**
 * read_file(file_id) - Read full content of a file
 * Also handles legacy get_file calls
 */
async function executeReadFile(
  toolCallId: string,
  toolName: string,
  fileId: string
): Promise<ToolResult> {
  if (!fileId) {
    return {
      tool_call_id: toolCallId,
      name: toolName,
      content: '',
      error: 'file_id is required'
    };
  }

  // Try to get live content from store first (most up-to-date)
  let content = artifactStore.getLiveContent(fileId);
  let title = 'Untitled';
  let version = 0;
  let totalVersions = 1;

  if (content === null) {
    // If not in live map, fallback to DB
    const artifact = await db.artifacts.get(fileId);
    if (!artifact) {
      return {
        tool_call_id: toolCallId,
        name: toolName,
        content: '',
        error: `File not found: ${fileId}`
      };
    }
    const currentVersion = artifact.versions[artifact.currentVersionIndex];
    content = currentVersion?.content || '';
    title = currentVersion?.title || 'Untitled';
    version = artifact.currentVersionIndex;
    totalVersions = artifact.versions.length;
  } else {
    // Found in live map, get metadata from store
    const artifact = artifactStore.artifacts.find(a => a.id === fileId);
    if (artifact) {
      const currentVersion = artifact.versions[artifact.currentVersionIndex];
      title = currentVersion?.title || 'Untitled';
      version = artifact.currentVersionIndex;
      totalVersions = artifact.versions.length;
    }
  }

  if (content === '') {
    return {
      tool_call_id: toolCallId,
      name: toolName,
      content: '',
      error: 'File is empty'
    };
  }

  // Return structured response
  const result = {
    id: fileId,
    title,
    content,
    version,
    totalVersions
  };

  return {
    tool_call_id: toolCallId,
    name: toolName,
    content: JSON.stringify(result, null, 2)
  };
}

/**
 * write_file(title, content, file_type) - Create a new file
 */
function executeWriteFile(
  toolCallId: string,
  toolName: string,
  projectId: string,
  title: string,
  content: string,
  fileType: 'artifact' | 'document' | 'code'
): ToolResult {
  if (!title) {
    return {
      tool_call_id: toolCallId,
      name: toolName,
      content: '',
      error: 'title is required'
    };
  }

  if (!projectId) {
    return {
      tool_call_id: toolCallId,
      name: toolName,
      content: '',
      error: 'projectId is required for creating files'
    };
  }

  // Create the artifact directly - for new files, there's no diff to show
  const artifact = artifactStore.createArtifact(projectId, title, content || '');

  console.log(`[ToolExecutor] Created new file via store: ${title} (${artifact.id})`);

  return {
    tool_call_id: toolCallId,
    name: toolName,
    content: JSON.stringify({
      success: true,
      message: `File "${title}" created successfully`,
      file_id: artifact.id,
      file_type: fileType
    })
  };
}

/**
 * patch_file(file_id, patches, description) - Apply patches to an existing file immediately
 * 
 * Patches are applied directly to the artifact content. Open editor tabs will
 * automatically refresh via the reactive liveContentMap system.
 */
async function executePatchFile(
  toolCallId: string,
  toolName: string,
  fileId: string,
  patches: Array<{search: string, replace: string}> | undefined,
  description: string,
  legacySearch?: string,
  legacyReplace?: string
): Promise<ToolResult> {
  if (!fileId) {
    return {
      tool_call_id: toolCallId,
      name: toolName,
      content: '',
      error: 'file_id is required'
    };
  }

  // Normalize patches: use provided patches list or fallback to legacy search/replace
  const patchList = patches || (legacySearch !== undefined ? [{ search: legacySearch, replace: legacyReplace || '' }] : []);

  if (patchList.length === 0) {
    return {
      tool_call_id: toolCallId,
      name: toolName,
      content: '',
      error: 'No patches provided'
    };
  }

  const artifact = artifactStore.artifacts.find(a => a.id === fileId);
  if (!artifact) {
    return {
      tool_call_id: toolCallId,
      name: toolName,
      content: '',
      error: `File not found in store: ${fileId}`
    };
  }

  // IMPORTANT: Save any unsaved user edits before applying patches
  // This ensures we apply against the most up-to-date content
  if (artifact.isDirty) {
    await artifactStore.saveArtifactNow(fileId);
  }

  // Get live content if available, otherwise current version
  let currentContent = artifactStore.getLiveContent(fileId);
  if (currentContent === null) {
    const currentVersion = artifact.versions[artifact.currentVersionIndex];
    currentContent = currentVersion?.content || '';
  }

  if (currentContent === '') {
    return {
      tool_call_id: toolCallId,
      name: toolName,
      content: '',
      error: 'File has no content to patch'
    };
  }

  // Apply all patches sequentially
  let newContent = currentContent;

  for (let i = 0; i < patchList.length; i++) {
    const { search, replace } = patchList[i];
    
    if (!newContent.includes(search)) {
      return {
        tool_call_id: toolCallId,
        name: toolName,
        content: '',
        error: `Search string not found in file (Patch #${i+1}). Make sure it matches exactly (including whitespace and line endings).`
      };
    }

    // Check for multiple occurrences
    const occurrences = newContent.split(search).length - 1;
    if (occurrences > 1) {
      return {
        tool_call_id: toolCallId,
        name: toolName,
        content: '',
        error: `Search string found multiple times (${occurrences}) in Patch #${i+1}. Please provide a more unique search string.`
      };
    }

    // Apply the patch
    newContent = newContent.replace(search, replace);
  }

  // Update the live content - this will trigger the reactive system to refresh open editors
  artifactStore.updateLiveContent(fileId, newContent);
  
  const currentTitle = artifact.versions[artifact.currentVersionIndex]?.title || 'Untitled';
  console.log(`[ToolExecutor] Applied ${patchList.length} patches to: ${currentTitle}`);

  return {
    tool_call_id: toolCallId,
    name: toolName,
    content: JSON.stringify({
      success: true,
      message: `Applied ${patchList.length} patch${patchList.length !== 1 ? 'es' : ''}${description ? `: ${description}` : ''}`,
      file_id: fileId,
      patches_applied: patchList.length
    })
  };
}

/**
 * search_files(query, top_k) - Semantic search across files
 * 
 * Note: This is a simple text-based search for now.
 * TODO: Implement proper semantic search with embeddings
 */
async function executeSearchFiles(
  toolCallId: string,
  toolName: string,
  projectId: string,
  query: string,
  topK: number
): Promise<ToolResult> {
  if (!query) {
    return {
      tool_call_id: toolCallId,
      name: toolName,
      content: '',
      error: 'query is required'
    };
  }

  const artifacts = await db.artifacts.getByProject(projectId);
  
  if (artifacts.length === 0) {
    return {
      tool_call_id: toolCallId,
      name: toolName,
      content: JSON.stringify({ results: [], message: 'No files in project' })
    };
  }

  // Simple text search - find files containing query terms
  const queryLower = query.toLowerCase();
  const queryTerms = queryLower.split(/\s+/).filter(t => t.length > 2);
  
  const results: Array<{
    file_id: string;
    file_title: string;
    excerpt: string;
    score: number;
  }> = [];

  for (const artifact of artifacts) {
    const currentVersion = artifact.versions[artifact.currentVersionIndex];
    if (!currentVersion?.content) continue;

    const content = currentVersion.content;
    const contentLower = content.toLowerCase();
    
    // Score based on term matches
    let score = 0;
    for (const term of queryTerms) {
      if (contentLower.includes(term)) {
        score += 1;
      }
    }
    
    if (score > 0) {
      // Find a relevant excerpt (first occurrence of any term)
      let excerptStart = 0;
      for (const term of queryTerms) {
        const idx = contentLower.indexOf(term);
        if (idx !== -1) {
          excerptStart = Math.max(0, idx - 50);
          break;
        }
      }
      
      const excerpt = content.slice(excerptStart, excerptStart + 200);
      
      results.push({
        file_id: artifact.id,
        file_title: currentVersion.title,
        excerpt: excerpt.trim() + (excerpt.length === 200 ? '...' : ''),
        score: score / queryTerms.length
      });
    }
  }

  // Sort by score and limit
  results.sort((a, b) => b.score - a.score);
  const limitedResults = results.slice(0, Math.min(topK, 10));

  if (limitedResults.length === 0) {
    return {
      tool_call_id: toolCallId,
      name: toolName,
      content: JSON.stringify({ results: [], message: 'No matching content found' })
    };
  }

  return {
    tool_call_id: toolCallId,
    name: toolName,
    content: JSON.stringify({ results: limitedResults })
  };
}

/**
 * grep_files(pattern, glob_pattern?, case_sensitive?) - Search file contents for pattern
 */
async function executeGrepFiles(
  toolCallId: string,
  toolName: string,
  projectId: string,
  pattern: string,
  globPattern?: string,
  caseSensitive: boolean = false
): Promise<ToolResult> {
  if (!pattern) {
    return {
      tool_call_id: toolCallId,
      name: toolName,
      content: '',
      error: 'pattern is required'
    };
  }

  let artifacts = await db.artifacts.getByProject(projectId);
  
  // Filter by glob pattern if provided (matches against title)
  if (globPattern) {
    const globRegex = globToRegex(globPattern);
    artifacts = artifacts.filter(a => {
      const title = a.versions[a.currentVersionIndex]?.title || '';
      return globRegex.test(title);
    });
  }

  const searchPattern = caseSensitive ? pattern : pattern.toLowerCase();
  
  const matches: Array<{
    file_id: string;
    file_title: string;
    line_number: number;
    excerpt: string;
  }> = [];

  for (const artifact of artifacts) {
    const currentVersion = artifact.versions[artifact.currentVersionIndex];
    if (!currentVersion?.content) continue;

    const content = currentVersion.content;
    const lines = content.split('\n');
    
    for (let i = 0; i < lines.length; i++) {
      const line = lines[i];
      const searchLine = caseSensitive ? line : line.toLowerCase();
      
      if (searchLine.includes(searchPattern)) {
        // Get context: line with surrounding context
        const startLine = Math.max(0, i - 1);
        const endLine = Math.min(lines.length - 1, i + 1);
        const excerpt = lines.slice(startLine, endLine + 1).join('\n');
        
        matches.push({
          file_id: artifact.id,
          file_title: currentVersion.title,
          line_number: i + 1,
          excerpt: excerpt.length > 300 ? excerpt.slice(0, 300) + '...' : excerpt
        });
        
        // Limit matches per file to avoid huge responses
        if (matches.filter(m => m.file_id === artifact.id).length >= 5) {
          break;
        }
      }
    }
  }

  // Limit total matches
  const limitedMatches = matches.slice(0, 50);

  return {
    tool_call_id: toolCallId,
    name: toolName,
    content: JSON.stringify({ 
      matches: limitedMatches,
      total_matches: matches.length,
      truncated: matches.length > 50
    })
  };
}

/**
 * glob_files(pattern) - Find files by name/title pattern
 */
async function executeGlobFiles(
  toolCallId: string,
  toolName: string,
  projectId: string,
  pattern: string
): Promise<ToolResult> {
  if (!pattern) {
    return {
      tool_call_id: toolCallId,
      name: toolName,
      content: '',
      error: 'pattern is required'
    };
  }

  const artifacts = await db.artifacts.getByProject(projectId);
  const globRegex = globToRegex(pattern);
  
  const matchingFiles: ProjectFile[] = [];
  
  for (const artifact of artifacts) {
    const title = artifact.versions[artifact.currentVersionIndex]?.title || 'Untitled';
    
    if (globRegex.test(title)) {
      matchingFiles.push({
        id: artifact.id,
        title: title,
        file_type: 'artifact',
      });
    }
  }

  return {
    tool_call_id: toolCallId,
    name: toolName,
    content: JSON.stringify(matchingFiles, null, 2)
  };
}

/**
 * Convert a glob pattern to a regular expression.
 * Supports: * (any chars), ? (single char)
 */
function globToRegex(pattern: string): RegExp {
  const escaped = pattern
    .replace(/[.+^${}()|[\]\\]/g, '\\$&') // Escape regex special chars
    .replace(/\*/g, '.*')                  // * -> .*
    .replace(/\?/g, '.');                  // ? -> .
  
  return new RegExp(`^${escaped}$`, 'i'); // Case-insensitive, full match
}

/**
 * create_source(url, title, content, ...) - Create a new source (web reference)
 */
function executeCreateSource(
  toolCallId: string,
  toolName: string,
  projectId: string,
  url: string,
  title: string,
  content: string,
  bibliography: {
    author?: string;
    publishedDate?: string;
    publisher?: string;
    resourceType?: string;
  }
): ToolResult {
  if (!url) {
    return {
      tool_call_id: toolCallId,
      name: toolName,
      content: '',
      error: 'url is required'
    };
  }

  if (!projectId) {
    return {
      tool_call_id: toolCallId,
      name: toolName,
      content: '',
      error: 'projectId is required for creating sources'
    };
  }

  // Build bibliography object, filtering out undefined values
  const bib: Bibliography = {};
  if (bibliography.author) bib.author = bibliography.author;
  if (bibliography.publishedDate) bib.publishedDate = bibliography.publishedDate;
  if (bibliography.publisher) bib.publisher = bibliography.publisher;
  if (bibliography.resourceType) bib.resourceType = bibliography.resourceType;

  // Create the source using the store
  const source = sourceStore.createSource(
    projectId,
    title || url,
    url,
    content || '',
    {
      bibliography: Object.keys(bib).length > 0 ? bib : undefined,
      scrapedAt: Date.now(),
    }
  );

  console.log(`[ToolExecutor] Created new source via store: ${title || url} (${source.id})`);

  return {
    tool_call_id: toolCallId,
    name: toolName,
    content: JSON.stringify({
      success: true,
      message: `Source "${title || url}" created successfully`,
      source_id: source.id,
      url: url
    })
  };
}

/**
 * Convert tool results to LangGraph ToolMessage format for resumption.
 */
export function toolResultsToMessages(results: ToolResult[]): Array<{
  type: 'tool';
  tool_call_id: string;
  name: string;
  content: string;
}> {
  return results.map(result => ({
    type: 'tool' as const,
    tool_call_id: result.tool_call_id,
    name: result.name,
    content: result.error ? JSON.stringify({ error: result.error }) : result.content
  }));
}
