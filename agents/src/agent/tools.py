"""Client-executed tool definitions for the Seminar Agent.

These tools are stubs - the actual execution happens on the client.
The graph uses interrupt_before=["tools"] to pause before execution,
allowing the client to:
1. Execute tools locally (against IndexedDB)
2. Resume the graph with tool results

This pattern is required because project files are stored client-side
in IndexedDB, not on a central server accessible to the agent.
"""

from langchain_core.tools import tool


@tool
def list_files() -> str:
    """List all files in the current project.
    
    Returns a JSON array of file metadata with:
    - id: Unique file identifier
    - title: File display name
    - file_type: Type of file ('artifact', 'document', 'code')
    
    Use this to discover what files exist before reading them.
    """
    return ""


@tool
def get_file(file_id: str) -> str:
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
    return ""


@tool
def search_files(query: str, top_k: int = 5) -> str:
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
    return ""


@tool
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
    return ""


# All tools that require client-side execution
CLIENT_TOOLS = [list_files, get_file, search_files, edit_file]

