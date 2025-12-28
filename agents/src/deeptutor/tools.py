"""Tool definitions for the Deeptutor Agent.

These tools read project_files from the config (passed by the agent_node wrapper).
The config approach is necessary because create_agent() creates an inner graph
with its own state schema that doesn't include our custom state keys.

Note: For full content access, the frontend must include file contents in the
project_files array.
"""

import json
from langchain_core.tools import StructuredTool
from langchain.tools import ToolRuntime


def _get_project_files(runtime: ToolRuntime) -> list:
    """Extract project_files from runtime config.
    
    The agent_node wrapper passes project_files via config['configurable'].
    """
    configurable = runtime.config.get("configurable", {})
    return configurable.get("project_files", [])


def list_files(runtime: ToolRuntime) -> str:
    """List all files in the current project.
    
    Returns a JSON array of file metadata with:
    - id: Unique file identifier
    - title: File display name
    - file_type: Type of file ('artifact', 'document', 'code')
    
    Use this to discover what files exist before reading them.
    """
    project_files = _get_project_files(runtime)
    
    if not project_files:
        return json.dumps({"files": [], "message": "No files in project"})
    
    files = [
        {
            "id": f.get("id"),
            "title": f.get("title"),
            "file_type": f.get("file_type", "artifact")
        }
        for f in project_files
    ]
    return json.dumps(files, indent=2)


def get_file(file_id: str, runtime: ToolRuntime) -> str:
    """Read the full content of a file by its ID.
    
    Args:
        file_id: The unique identifier of the file to read.
                 Use list_files() first to get available file IDs.
    
    Returns:
        The file's full text content, or an error if not found.
        
    Errors:
        - "not found": The file_id doesn't exist
        - "empty": The file has no content
    """
    project_files = _get_project_files(runtime)
    
    if not project_files:
        return json.dumps({"error": "No files in project"})
    
    # Find the file by ID
    file_data = next((f for f in project_files if f.get("id") == file_id), None)
    
    if not file_data:
        return json.dumps({"error": f"File not found: {file_id}"})
    
    # Check if content is available
    content = file_data.get("content")
    if content:
        return json.dumps({
            "id": file_data.get("id"),
            "title": file_data.get("title"),
            "content": content
        }, indent=2)
    else:
        # Content not available - return metadata with note
        return json.dumps({
            "id": file_data.get("id"),
            "title": file_data.get("title"),
            "content": None,
            "note": "File content not available. The frontend needs to include content in project_files."
        }, indent=2)


def search_files(query: str, top_k: int = 5, *, runtime: ToolRuntime) -> str:
    """Semantic search across all project files.
    
    Searches file contents using semantic similarity to find
    relevant passages matching the query.
    
    Args:
        query: Natural language search query describing what you're looking for.
               Be specific and descriptive for best results.
        top_k: Maximum number of results to return (default 5, max 10).
    
    Returns:
        JSON array of search results, each containing:
        - file_id: ID of the file containing the match
        - file_title: Title of the file
        - excerpt: Relevant text excerpt
        - score: Relevance score (0-1)
        
    Errors:
        - "no results": No matching content found
        - "not indexed": Files haven't been indexed yet
    """
    project_files = _get_project_files(runtime)
    
    if not project_files:
        return json.dumps({"results": [], "message": "No files in project"})
    
    # Simple text search across file contents
    query_lower = query.lower()
    query_terms = [t for t in query_lower.split() if len(t) > 2]
    
    results = []
    for f in project_files:
        content = f.get("content", "")
        title = f.get("title", "")
        
        if not content:
            continue
            
        content_lower = content.lower()
        
        # Score based on term matches
        score = sum(1 for term in query_terms if term in content_lower)
        
        if score > 0:
            # Find excerpt around first match
            excerpt_start = 0
            for term in query_terms:
                idx = content_lower.find(term)
                if idx != -1:
                    excerpt_start = max(0, idx - 50)
                    break
            
            excerpt = content[excerpt_start:excerpt_start + 200]
            
            results.append({
                "file_id": f.get("id"),
                "file_title": title,
                "excerpt": excerpt.strip() + ("..." if len(excerpt) == 200 else ""),
                "score": score / max(len(query_terms), 1)
            })
    
    # Sort by score and limit
    results.sort(key=lambda x: x["score"], reverse=True)
    results = results[:min(top_k, 10)]
    
    if not results:
        # If no content matches, return file list as fallback
        return json.dumps({
            "results": [],
            "message": "No matching content found. File contents may not be indexed.",
            "available_files": [{"id": f.get("id"), "title": f.get("title")} for f in project_files]
        })
    
    return json.dumps({"results": results}, indent=2)


def edit_file(file_id: str, new_content: str, edit_description: str = "") -> str:
    """Propose edits to a file's content.
    
    This creates a pending edit that the user must approve.
    The edit will be shown as a diff for user review.
    
    Args:
        file_id: The unique identifier of the file to edit.
        new_content: The complete new content for the file.
                     This replaces the entire file content.
        edit_description: Optional description of what was changed
                          (helps user understand the edit).
    
    Returns:
        Success message if edit was queued for approval,
        or error message if the file doesn't exist.
        
    Note:
        Edits are NOT applied immediately. The user sees a diff
        and must explicitly accept or reject the changes.
    """
    # This is still a stub - edit requires client-side execution
    # since the actual file storage is in IndexedDB
    return json.dumps({
        "status": "pending",
        "message": "Edit proposal created. Waiting for user approval.",
        "file_id": file_id,
        "edit_description": edit_description
    })


# Build tools using StructuredTool to properly handle runtime injection
list_files_tool = StructuredTool.from_function(
    func=list_files,
    name="list_files",
    description="""List all files in the current project.

Returns a JSON array of file metadata with:
- id: Unique file identifier
- title: File display name
- file_type: Type of file ('artifact', 'document', 'code')

Use this to discover what files exist before reading them."""
)

get_file_tool = StructuredTool.from_function(
    func=get_file,
    name="get_file",
    description="""Read the full content of a file by its ID.

Args:
    file_id: The unique identifier of the file to read.
             Use list_files() first to get available file IDs.

Returns the file's full text content, or an error if not found."""
)

search_files_tool = StructuredTool.from_function(
    func=search_files,
    name="search_files",
    description="""Semantic search across all project files.

Args:
    query: Natural language search query describing what you're looking for.
    top_k: Maximum number of results to return (default 5, max 10).

Returns JSON array of search results with file_id, file_title, excerpt, and score."""
)

edit_file_tool = StructuredTool.from_function(
    func=edit_file,
    name="edit_file",
    description="""Propose edits to a file's content. User must approve changes.

Args:
    file_id: The unique identifier of the file to edit.
    new_content: The complete new content for the file.
    edit_description: Optional description of what was changed."""
)


# All tools that can read from state
# Note: edit_file is commented out for now - focusing on read-only operations
CLIENT_TOOLS = [list_files_tool, get_file_tool, search_files_tool]
# CLIENT_TOOLS = [list_files_tool, get_file_tool, search_files_tool, edit_file_tool]  # Uncomment to enable editing

