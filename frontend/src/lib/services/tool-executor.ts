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
 * Read operations (list_files, read_file, search_files, grep_files, glob_files) are auto-approved.
 * Write operations (write_file, edit_file, tag_file) require human approval first.
 */

import { db } from './indexeddb.js';
import type { ToolCall, ToolResult, ProjectFile, Artifact, ArtifactVersion } from '../stores/types.js';
import { nanoid } from 'nanoid';

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
          args.tag as string | undefined,
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
        return await executeWriteFile(
          toolCallId,
          name,
          projectId,
          args.title as string,
          args.content as string,
          (args.file_type as 'artifact' | 'document' | 'code') || 'artifact'
        );

      case 'edit_file':
        return await executeEditFile(
          toolCallId,
          name,
          args.file_id as string,
          args.new_content as string,
          args.description as string || ''
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

      case 'tag_file':
        return await executeTagFile(
          toolCallId,
          name,
          args.file_id as string,
          args.tags as string[],
          (args.replace as boolean) || false
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
 * list_files(tag?, file_type?) - List files in the project, optionally filtered
 */
async function executeListFiles(
  toolCallId: string,
  toolName: string,
  projectId: string,
  filterTag?: string,
  filterFileType?: 'artifact' | 'document' | 'code'
): Promise<ToolResult> {
  let artifacts = await db.artifacts.getByProject(projectId);
  
  // Filter by tag if provided
  if (filterTag) {
    const tagLower = filterTag.toLowerCase();
    artifacts = artifacts.filter(a => 
      a.tags?.some(t => t.toLowerCase() === tagLower)
    );
  }
  
  // Filter by file_type if provided (for now all are 'artifact')
  // This filter is a placeholder for when we support different types
  
  const files: ProjectFile[] = artifacts.map(artifact => ({
    id: artifact.id,
    title: artifact.versions[artifact.currentVersionIndex]?.title || 'Untitled',
    file_type: 'artifact' as const,
    tags: artifact.tags || []
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
  
  if (!currentVersion || !currentVersion.content) {
    return {
      tool_call_id: toolCallId,
      name: toolName,
      content: '',
      error: 'File is empty'
    };
  }

  // Return structured response
  const result = {
    id: artifact.id,
    title: currentVersion.title,
    content: currentVersion.content,
    version: artifact.currentVersionIndex,
    totalVersions: artifact.versions.length
  };

  return {
    tool_call_id: toolCallId,
    name: toolName,
    content: JSON.stringify(result, null, 2)
  };
}

/**
 * write_file(title, content, file_type) - Create a new file
 * 
 * This should only be called after human approval.
 */
async function executeWriteFile(
  toolCallId: string,
  toolName: string,
  projectId: string,
  title: string,
  content: string,
  fileType: 'artifact' | 'document' | 'code'
): Promise<ToolResult> {
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

  const now = Date.now();
  const fileId = nanoid();

  // Create new artifact
  const newArtifact: Artifact = {
    id: fileId,
    projectId: projectId,
    currentVersionIndex: 0,
    versions: [{
      index: 0,
      title: title,
      content: content || '',
      createdAt: now
    }],
    createdAt: now,
    updatedAt: now
  };

  await db.artifacts.save(newArtifact);

  console.log(`[ToolExecutor] Created new file: ${title} (${fileId})`);

  return {
    tool_call_id: toolCallId,
    name: toolName,
    content: JSON.stringify({
      success: true,
      message: `File "${title}" created successfully`,
      file_id: fileId,
      file_type: fileType
    })
  };
}

/**
 * edit_file(file_id, new_content, description) - Edit an existing file
 * 
 * Creates a new version of the file. Should only be called after human approval.
 */
async function executeEditFile(
  toolCallId: string,
  toolName: string,
  fileId: string,
  newContent: string,
  description: string
): Promise<ToolResult> {
  if (!fileId) {
    return {
      tool_call_id: toolCallId,
      name: toolName,
      content: '',
      error: 'file_id is required'
    };
  }

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
  const now = Date.now();

  // Create new version
  const newVersion: ArtifactVersion = {
    index: artifact.versions.length,
    title: currentVersion?.title || 'Untitled',
    content: newContent,
    createdAt: now
  };

  // Update artifact with new version
  const updatedArtifact: Artifact = {
    ...artifact,
    versions: [...artifact.versions, newVersion],
    currentVersionIndex: artifact.versions.length,
    updatedAt: now
  };

  await db.artifacts.save(updatedArtifact);

  console.log(`[ToolExecutor] Edited file: ${currentVersion?.title || fileId} (new version ${newVersion.index})`);

  return {
    tool_call_id: toolCallId,
    name: toolName,
    content: JSON.stringify({
      success: true,
      message: `File edited successfully${description ? `: ${description}` : ''}`,
      file_id: fileId,
      version: newVersion.index,
      previous_version: artifact.currentVersionIndex
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
        tags: artifact.tags || []
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
 * tag_file(file_id, tags, replace?) - Add or update tags on a file
 */
async function executeTagFile(
  toolCallId: string,
  toolName: string,
  fileId: string,
  tags: string[],
  replace: boolean = false
): Promise<ToolResult> {
  if (!fileId) {
    return {
      tool_call_id: toolCallId,
      name: toolName,
      content: '',
      error: 'file_id is required'
    };
  }

  if (!tags || !Array.isArray(tags)) {
    return {
      tool_call_id: toolCallId,
      name: toolName,
      content: '',
      error: 'tags must be an array of strings'
    };
  }

  const artifact = await db.artifacts.get(fileId);
  
  if (!artifact) {
    return {
      tool_call_id: toolCallId,
      name: toolName,
      content: '',
      error: `File not found: ${fileId}`
    };
  }

  // Normalize tags (lowercase, trim, dedupe)
  const normalizedNewTags = tags.map(t => t.toLowerCase().trim()).filter(t => t.length > 0);
  
  let updatedTags: string[];
  if (replace) {
    updatedTags = normalizedNewTags;
  } else {
    // Merge with existing, avoiding duplicates
    const existingTags = artifact.tags || [];
    const combined = new Set([...existingTags.map(t => t.toLowerCase()), ...normalizedNewTags]);
    updatedTags = Array.from(combined);
  }

  // Update artifact
  const updatedArtifact: Artifact = {
    ...artifact,
    tags: updatedTags,
    updatedAt: Date.now()
  };

  await db.artifacts.save(updatedArtifact);

  const title = artifact.versions[artifact.currentVersionIndex]?.title || 'Untitled';
  console.log(`[ToolExecutor] Tagged file "${title}": ${updatedTags.join(', ')}`);

  return {
    tool_call_id: toolCallId,
    name: toolName,
    content: JSON.stringify({
      success: true,
      message: `Tags updated for "${title}"`,
      file_id: fileId,
      tags: updatedTags
    })
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
