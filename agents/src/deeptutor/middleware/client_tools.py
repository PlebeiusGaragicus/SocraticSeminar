"""ClientToolsMiddleware for client-side file operations.

Provides file tools that always interrupt for client-side execution.
Files are stored in the browser (IndexedDB) and the client provides
file contents when the agent needs them.

Key Patterns:
- ALL file operations interrupt (reads AND writes)
- Client executes tools locally and returns results
- Write operations require explicit human approval
- Read operations can be auto-approved by client
"""

from collections.abc import Awaitable, Callable
from typing import Any, Literal

from langchain.agents.middleware.types import AgentMiddleware, AgentState, ModelRequest, ModelResponse
from langchain.tools import ToolRuntime
from langchain.tools.tool_node import ToolCallRequest
from langchain_core.messages import ToolMessage
from langchain_core.tools import StructuredTool
from langgraph.types import Command, interrupt
from typing_extensions import NotRequired, TypedDict


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

CLIENT_TOOLS_SYSTEM_PROMPT = """## File Operations

You have access to tools for working with project files. These files are stored
locally on the user's device and will be provided when you request them.

Available tools:
- `list_files()` - List all files in the current project
- `read_file(file_id)` - Read the full content of a file by ID
- `search_files(query)` - Search files by content
- `write_file(title, content, file_type)` - Create a new file (requires approval)
- `edit_file(file_id, new_content, description)` - Edit an existing file (requires approval)

### Guidelines

1. **Use list_files first** to discover what files exist before reading
2. **Read files before editing** to understand current content
3. **Provide clear descriptions** when creating/editing files
4. **Write operations require approval** - explain your changes clearly
5. **Be specific** with file IDs when reading or editing"""


# =============================================================================
# TOOL DEFINITIONS
# =============================================================================

def _create_list_files_tool() -> StructuredTool:
    """Create the list_files tool."""
    
    def list_files(runtime: ToolRuntime) -> str:
        """List all files in the current project.
        
        Returns metadata about available files including:
        - id: Unique file identifier
        - title: File display name
        - file_type: Type ('artifact', 'document', 'code')
        
        Use this to discover files before reading them.
        """
        # This will be handled by the middleware's wrap_tool_call
        # which interrupts for client execution
        return "Tool execution pending - awaiting client response"
    
    return StructuredTool.from_function(
        name="list_files",
        func=list_files,
        description="""List all files in the current project.

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
        
        This action requires user approval before the file is created.
        
        Args:
            title: Title/name for the new file
            content: Initial content for the file
            file_type: Type of file ('artifact', 'document', 'code')
        
        Returns:
            Success message with new file ID, or error
        """
        return "Tool execution pending - awaiting user approval"
    
    return StructuredTool.from_function(
        name="write_file",
        func=write_file,
        description="""Create a new file (requires user approval).

Args:
    title: File name/title
    content: File content
    file_type: 'artifact', 'document', or 'code'

User will see the content and must approve creation.""",
    )


def _create_edit_file_tool() -> StructuredTool:
    """Create the edit_file tool."""
    
    def edit_file(
        file_id: str,
        new_content: str,
        description: str = "",
        runtime: ToolRuntime = None,
    ) -> str:
        """Edit an existing file's content.
        
        This action requires user approval. The user will see a diff
        of the proposed changes before approving.
        
        Args:
            file_id: ID of the file to edit
            new_content: Complete new content for the file
            description: Description of changes (helps user understand)
        
        Returns:
            Success message, or error if file not found
        """
        return "Tool execution pending - awaiting user approval"
    
    return StructuredTool.from_function(
        name="edit_file",
        func=edit_file,
        description="""Edit a file's content (requires user approval).

Args:
    file_id: File ID from list_files()
    new_content: Complete new content
    description: What changed (optional but helpful)

User will see a diff and must approve changes.""",
    )


# Tools that can be auto-approved by the client (read-only)
AUTO_APPROVE_TOOLS = {"list_files", "read_file", "search_files"}

# Tools that require explicit human approval (write operations)
REQUIRE_APPROVAL_TOOLS = {"write_file", "edit_file"}


# =============================================================================
# MIDDLEWARE
# =============================================================================

class ClientToolsMiddleware(AgentMiddleware[ClientToolsState, None]):
    """Middleware for client-side file operations.
    
    All file tools interrupt execution and wait for the client to:
    1. Execute the operation locally (files in browser storage)
    2. Return the result
    
    For write operations, the client also shows approval UI.
    
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
            "auto_approve": true  // false for write operations
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
            _create_edit_file_tool(),
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
    
    elif tool_name == "edit_file":
        file_id = args.get("file_id", "unknown")
        description = args.get("description", "No description provided")
        new_content = args.get("new_content", "")
        preview = new_content[:200] + "..." if len(new_content) > 200 else new_content
        return f"Edit file '{file_id}'\n\n{description}\n\nNew content preview:\n{preview}"
    
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
                return result.get("content", "No content provided")
        
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

