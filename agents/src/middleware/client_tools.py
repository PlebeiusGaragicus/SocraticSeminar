"""ClientToolsMiddleware for client-side file operations.

Provides file tools that always interrupt for client-side execution.
Files are stored in the browser (IndexedDB) and the client provides
file contents when the agent needs them.

Key Patterns:
- ALL file operations interrupt (reads AND writes)
- Client executes tools locally and returns results
- Operations are typically auto-approved but client can still show UI
"""

from collections.abc import Awaitable, Callable
from typing import Any, Literal

from langchain.agents.middleware.types import AgentMiddleware, AgentState, ModelRequest, ModelResponse
from langchain.tools import ToolRuntime
from langchain.tools.tool_node import ToolCallRequest
from langchain_core.messages import ToolMessage
from langchain_core.tools import StructuredTool
from langgraph.types import Command, interrupt
from typing_extensions import NotRequired


# =============================================================================
# STATE EXTENSION
# =============================================================================

class ClientToolsState(AgentState):
    """State extension for client tools.
    
    Note: Project files are NOT stored in agent state.
    The client provides file contents via tool execution interrupts.
    """
    
    # Current project ID for scoping file operations
    current_project_id: NotRequired[str | None]


# =============================================================================
# SYSTEM PROMPT
# =============================================================================

CLIENT_TOOLS_SYSTEM_PROMPT = """## Project File Operations

You have access to tools for working with the user's project files. These files are
stored locally on the user's device (browser) and will be provided when you request them.

### Available Tools

**Discovery & Reading:**
- `list_files(file_type?)` - List files, optionally filtered by type
- `read_file(file_id)` - Read the full content of a file by ID
- `search_files(query, top_k?)` - Semantic search across file contents
- `grep_files(pattern, glob_pattern?, case_sensitive?)` - Pattern search in file contents
- `glob_files(pattern)` - Find files by title/name pattern (e.g., "*.md", "*bitcoin*")

**Writing:**
- `write_file(title, content, file_type)` - Create a new file
- `patch_file(file_id, patches, description)` - Edit a file with one or more patches. `patches` is a list of `{search, replace}` objects. Each `search` string must match exactly.

### Guidelines

1. **Use list_files first** to discover what files exist before reading
2. **Use grep_files** when searching for specific text patterns across files
3. **Use glob_files** when looking for files by name pattern
4. **Read files before editing** to understand current content
5. **Use patch_file** for all edits to existing files. You can provide multiple patches in one call - prefer this for complex edits to avoid multiple user approvals.
6. **Explain your changes** clearly when writing or patching files"""


# =============================================================================
# TOOL DEFINITIONS
# =============================================================================

def _create_list_files_tool() -> StructuredTool:
    """Create the list_files tool."""
    
    def list_files(
        file_type: Literal["artifact", "document", "code"] | None = None,
        runtime: ToolRuntime = None,
    ) -> str:
        """List all files in the current project, optionally filtered.
        
        Returns metadata about available files including:
        - id: Unique file identifier
        - title: File display name
        - file_type: Type ('artifact', 'document', 'code')
        
        Use this to discover files before reading them.
        
        Args:
            file_type: Optional file type filter
        """
        # This will be handled by the middleware's wrap_tool_call
        # which interrupts for client execution
        return "Tool execution pending - awaiting client response"
    
    return StructuredTool.from_function(
        name="list_files",
        func=list_files,
        description="""List all files in the current project, optionally filtered.

Args:
    file_type: Optional filter by type ('artifact', 'document', 'code')

Returns JSON array of file metadata with id, title, and file_type.
Use this first to discover what files are available.""",
    )


def _create_read_file_tool() -> StructuredTool:
    """Create the read_file tool."""
    
    def read_file(file_id: str, runtime: ToolRuntime) -> str:
        """Read the full content of a file by its ID.
        
        Args:
            file_id: The unique identifier of the file to read.
                     Use list_files() first to get available file IDs.
        
        Returns:
            The file's full text content, or an error if not found.
        """
        return "Tool execution pending - awaiting client response"
    
    return StructuredTool.from_function(
        name="read_file",
        func=read_file,
        description="""Read the full content of a file by its ID.

Args:
    file_id: Unique identifier from list_files()

Returns the file's content or an error if not found.""",
    )


def _create_search_files_tool() -> StructuredTool:
    """Create the search_files tool."""
    
    def search_files(
        query: str,
        top_k: int = 5,
        runtime: ToolRuntime = None,
    ) -> str:
        """Search across all project files by content.
        
        Args:
            query: Search query describing what you're looking for
            top_k: Maximum results to return (default 5, max 10)
        
        Returns:
            JSON array of search results with file_id, title, excerpt, score
        """
        return "Tool execution pending - awaiting client response"
    
    return StructuredTool.from_function(
        name="search_files",
        func=search_files,
        description="""Search files by content.

Args:
    query: What to search for
    top_k: Max results (default 5)

Returns matching excerpts with relevance scores.""",
    )


def _create_write_file_tool() -> StructuredTool:
    """Create the write_file tool."""
    
    def write_file(
        title: str,
        content: str,
        file_type: Literal["artifact", "document", "code"] = "artifact",
        runtime: ToolRuntime = None,
    ) -> str:
        """Create a new file in the project.
        
        This action executes on the client-side.
        
        Args:
            title: Title/name for the new file
            content: Initial content for the file
            file_type: Type of file ('artifact', 'document', 'code')
        
        Returns:
            Success message with new file ID, or error
        """
        return "Tool execution pending - awaiting client response"
    
    return StructuredTool.from_function(
        name="write_file",
        func=write_file,
        description="""Create a new file.

Args:
    title: File name/title
    content: File content
    file_type: 'artifact', 'document', or 'code'

Returns success message with new file ID.""",
    )


def _create_grep_files_tool() -> StructuredTool:
    """Create the grep_files tool for pattern search in file contents."""
    
    def grep_files(
        pattern: str,
        glob_pattern: str | None = None,
        case_sensitive: bool = False,
        runtime: ToolRuntime = None,
    ) -> str:
        """Search for a text pattern across all project files.
        
        Searches file contents for the given pattern and returns
        matching excerpts with file context.
        
        Args:
            pattern: Text pattern to search for (e.g., "Bitcoin", "monetary policy")
            glob_pattern: Optional glob to filter files (e.g., "*.md", "article-*")
            case_sensitive: Whether search is case-sensitive (default: False)
        
        Returns:
            JSON array of matches with file_id, title, line_number, excerpt
        """
        return "Tool execution pending - awaiting client response"
    
    return StructuredTool.from_function(
        name="grep_files",
        func=grep_files,
        description="""Search for a text pattern across all project files.

Args:
    pattern: Text to search for (e.g., "Bitcoin", "monetary policy")
    glob_pattern: Optional filter (e.g., "*.md", "article-*")
    case_sensitive: Case-sensitive search (default: False)

Returns matches with file_id, title, line_number, and excerpt.""",
    )


def _create_glob_files_tool() -> StructuredTool:
    """Create the glob_files tool for finding files by name pattern."""
    
    def glob_files(
        pattern: str,
        runtime: ToolRuntime = None,
    ) -> str:
        """Find files matching a glob pattern.
        
        Use glob patterns to find files by title/name.
        
        Args:
            pattern: Glob pattern (e.g., "*.md", "article-*", "*bitcoin*")
        
        Returns:
            JSON array of matching file metadata
        """
        return "Tool execution pending - awaiting client response"
    
    return StructuredTool.from_function(
        name="glob_files",
        func=glob_files,
        description="""Find files matching a glob pattern.

Args:
    pattern: Glob pattern (e.g., "*.md", "article-*", "*bitcoin*")

Returns array of matching files with id, title, file_type.""",
    )


def _create_patch_file_tool() -> StructuredTool:
    """Create the patch_file tool."""
    
    def patch_file(
        file_id: str,
        patches: list[dict[str, str]] | None = None,
        description: str = "",
        # Legacy support
        search: str | None = None,
        replace: str | None = None,
        runtime: ToolRuntime = None,
    ) -> str:
        """Patch an existing file by replacing specific strings.
        
        This tool allows you to change specific portions of a file.
        You can provide multiple patches in a single call.
        Each 'search' string must match EXACTLY (including whitespace) in the file.
        
        Args:
            file_id: ID of the file to patch
            patches: List of {'search': '...', 'replace': '...'} objects
            description: Description of what is being changed
            search: (Legacy) The exact text to find in the file
            replace: (Legacy) The text to replace it with
        
        Returns:
            Success message, or error if any search string not found
        """
        return "Tool execution pending - awaiting client response"
    
    return StructuredTool.from_function(
        name="patch_file",
        func=patch_file,
        description="""Patch a file with one or more string replacements.
        
Args:
    file_id: File ID from list_files()
    patches: List of {'search': '...', 'replace': '...'} objects
    description: What changed (optional but helpful)

Returns success message or error if search text not found.""",
    )


# Tools that can be auto-approved by the client
AUTO_APPROVE_TOOLS = {
    "list_files", 
    "read_file", 
    "search_files", 
    "grep_files", 
    "glob_files",
    "write_file",
    "patch_file",
}

# Tools that require explicit human approval (e.g. non-file tools)
REQUIRE_APPROVAL_TOOLS = set()


# =============================================================================
# MIDDLEWARE
# =============================================================================

class ClientToolsMiddleware(AgentMiddleware[ClientToolsState, None]):
    """Middleware for client-side file operations.
    
    All file tools interrupt execution and wait for the client to:
    1. Execute the operation locally (files in browser storage)
    2. Return the result
    
    Example:
        ```python
        agent = create_agent(
            model,
            middleware=[
                ClientToolsMiddleware(),
            ],
        )
        ```
    
    Client Integration:
        When the agent calls a file tool, execution interrupts with:
        ```json
        {
            "type": "client_tool_execution",
            "tool_calls": [
                {"id": "...", "name": "read_file", "args": {"file_id": "..."}}
            ],
            "auto_approve": true
        }
        ```
        
        Client should resume with:
        ```json
        {
            "tool_results": [
                {"tool_call_id": "...", "content": "file contents..."}
            ]
        }
        ```
    """
    
    state_schema = ClientToolsState
    
    def __init__(self) -> None:
        """Initialize client tools middleware."""
        super().__init__()
        self.tools = [
            _create_list_files_tool(),
            _create_read_file_tool(),
            _create_search_files_tool(),
            _create_write_file_tool(),
            _create_patch_file_tool(),
            _create_grep_files_tool(),
            _create_glob_files_tool(),
        ]
    
    async def awrap_model_call(
        self,
        request: ModelRequest,
        handler: Callable[[ModelRequest], Awaitable[ModelResponse]],
    ) -> ModelResponse:
        """Add client tools system prompt."""
        new_system_prompt = (
            request.system_prompt + "\n\n" + CLIENT_TOOLS_SYSTEM_PROMPT
            if request.system_prompt
            else CLIENT_TOOLS_SYSTEM_PROMPT
        )
        
        return await handler(request.override(system_prompt=new_system_prompt))
    
    def wrap_model_call(
        self,
        request: ModelRequest,
        handler: Callable[[ModelRequest], ModelResponse],
    ) -> ModelResponse:
        """Synchronous version - add client tools system prompt."""
        new_system_prompt = (
            request.system_prompt + "\n\n" + CLIENT_TOOLS_SYSTEM_PROMPT
            if request.system_prompt
            else CLIENT_TOOLS_SYSTEM_PROMPT
        )
        
        return handler(request.override(system_prompt=new_system_prompt))
    
    async def awrap_tool_call(
        self,
        request: ToolCallRequest,
        handler: Callable[[ToolCallRequest], Awaitable[ToolMessage | Command]],
    ) -> ToolMessage | Command:
        """Intercept file tool calls for client-side execution.
        
        Flow:
        1. Check if this is a client tool
        2. If yes, interrupt with tool call details
        3. When resumed, extract client's result
        4. Return the result as a ToolMessage
        """
        tool_name = request.tool_call.get("name", "")
        tool_call_id = request.tool_call.get("id", "")
        tool_args = request.tool_call.get("args", {})
        
        # Check if this is a client tool
        is_client_tool = tool_name in AUTO_APPROVE_TOOLS or tool_name in REQUIRE_APPROVAL_TOOLS
        
        if not is_client_tool:
            # Not our tool, pass through
            return await handler(request)
        
        # Determine if this requires human approval
        requires_approval = tool_name in REQUIRE_APPROVAL_TOOLS
        
        # Build interrupt data for client
        interrupt_data = {
            "type": "client_tool_execution",
            "tool_calls": [
                {
                    "id": tool_call_id,
                    "name": tool_name,
                    "args": tool_args,
                }
            ],
            "auto_approve": not requires_approval,
            "requires_approval": requires_approval,
        }
        
        # For write operations, add HITL-style data
        if requires_approval:
            interrupt_data["action_requests"] = [
                {
                    "name": tool_name,
                    "args": tool_args,
                    "description": _format_tool_description(tool_name, tool_args),
                }
            ]
            interrupt_data["review_configs"] = [
                {
                    "action_name": tool_name,
                    "allowed_decisions": ["approve", "edit", "reject"],
                }
            ]
        
        print(f"[ClientTools] Interrupting for {tool_name} (approval: {requires_approval})")
        
        # Interrupt and wait for client response
        resume_value = interrupt(interrupt_data)
        
        print(f"[ClientTools] Resumed with: {type(resume_value)}")
        
        # Extract result from client response
        result_content = _extract_tool_result(resume_value, tool_call_id)
        
        return ToolMessage(
            content=result_content,
            tool_call_id=tool_call_id,
            name=tool_name,
        )
    
    def wrap_tool_call(
        self,
        request: ToolCallRequest,
        handler: Callable[[ToolCallRequest], ToolMessage | Command],
    ) -> ToolMessage | Command:
        """Synchronous version of tool call interception."""
        import asyncio
        
        async def async_handler(req: ToolCallRequest) -> ToolMessage | Command:
            return handler(req)
        
        return asyncio.get_event_loop().run_until_complete(
            self.awrap_tool_call(request, async_handler)
        )


def _format_tool_description(tool_name: str, args: dict[str, Any]) -> str:
    """Format a human-readable description of a tool call."""
    if tool_name == "write_file":
        title = args.get("title", "Untitled")
        content = args.get("content", "")
        preview = content[:200] + "..." if len(content) > 200 else content
        return f"Create new file '{title}'\n\nContent preview:\n{preview}"
    
    elif tool_name == "patch_file":
        file_id = args.get("file_id", "unknown")
        description = args.get("description", "No description provided")
        patches = args.get("patches", [])
        
        if patches:
            patch_summaries = []
            for i, p in enumerate(patches[:3]):
                search = p.get("search", "")[:50]
                replace = p.get("replace", "")[:50]
                patch_summaries.append(f"  {i+1}. '{search}' -> '{replace}'")
            
            summary = "\n".join(patch_summaries)
            if len(patches) > 3:
                summary += f"\n  ... and {len(patches)-3} more"
            
            return f"Patch file '{file_id}'\n\n{description}\n\nChanges:\n{summary}"
        else:
            # Legacy single patch
            search = args.get("search", "")
            replace = args.get("replace", "")
            return f"Patch file '{file_id}'\n\n{description}\n\nSearch:\n{search}\n\nReplace:\n{replace}"
    
    else:
        return f"Execute {tool_name} with args: {args}"


def _extract_tool_result(resume_value: Any, tool_call_id: str) -> str:
    """Extract tool result from client's resume response.
    
    Expected formats:
    1. { "tool_results": [{"tool_call_id": "...", "content": "..."}] }
    2. { "decisions": [{"type": "approve", ...}] }  (for HITL)
    3. Direct string content
    """
    if isinstance(resume_value, str):
        return resume_value
    
    if isinstance(resume_value, dict):
        # Check for tool_results format
        tool_results = resume_value.get("tool_results", [])
        for result in tool_results:
            if result.get("tool_call_id") == tool_call_id:
                # Client tool results use 'output' or 'content'
                return result.get("output") or result.get("content") or "Success"
        
        # Check for HITL decisions format
        decisions = resume_value.get("decisions", [])
        if decisions:
            decision = decisions[0]
            decision_type = decision.get("type", "reject")
            
            if decision_type == "approve":
                return "Operation approved and executed successfully"
            elif decision_type == "edit":
                # User edited the args
                edited_args = decision.get("args", {})
                return f"Operation executed with modified args: {edited_args}"
            elif decision_type == "reject":
                return "Operation rejected by user"
        
        # Check for direct content
        if "content" in resume_value:
            return resume_value["content"]
        
        # Check for error
        if "error" in resume_value:
            return f"Error: {resume_value['error']}"
    
    return f"Unexpected response format: {resume_value}"

