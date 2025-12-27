/**
 * Tool Executor Service
 * 
 * Executes tool calls locally against IndexedDB.
 * This is the client-side counterpart to the stub tools defined in the agent.
 * 
 * Flow:
 * 1. Agent requests tool call (e.g., get_file)
 * 2. LangGraph interrupts before the tools node
 * 3. Frontend receives interrupt with pending tool calls
 * 4. This service executes tools against local IndexedDB
 * 5. Frontend resumes the graph with tool results
 */

import { db } from './indexeddb.js';
import type { ToolCall, ToolResult, ProjectFile } from '../stores/types.js';

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
        return await executeListFiles(toolCallId, name, projectId);

      case 'get_file':
        return await executeGetFile(toolCallId, name, args.file_id as string);

      case 'search_files':
        return await executeSearchFiles(
          toolCallId,
          name,
          projectId,
          args.query as string,
          (args.top_k as number) || 5
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
 * list_files() - List all files in the project
 */
async function executeListFiles(
  toolCallId: string,
  toolName: string,
  projectId: string
): Promise<ToolResult> {
  const artifacts = await db.artifacts.getByProject(projectId);
  
  const files: ProjectFile[] = artifacts.map(artifact => ({
    id: artifact.id,
    title: artifact.versions[artifact.currentVersionIndex]?.title || 'Untitled',
    file_type: 'artifact' as const
  }));

  return {
    tool_call_id: toolCallId,
    name: toolName,
    content: JSON.stringify(files, null, 2)
  };
}

/**
 * get_file(file_id) - Read full content of a file
 */
async function executeGetFile(
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
