"""ScratchFilesMiddleware for agent working memory.

Provides file tools for the agent's scratch space that:
- Store files in agent state (visible to frontend)
- Use /scratch/ prefix to separate from user files
- Do NOT require human approval (agent's own working memory)
- Are READ-ONLY from the user's perspective

The frontend can display these files for transparency, but users cannot edit them.
"""

from collections.abc import Awaitable, Callable
from typing import Annotated

from langchain.agents.middleware.types import (
    AgentMiddleware,
    AgentState,
    ModelRequest,
    ModelResponse,
)
from langchain.tools import ToolRuntime
from langchain.tools.tool_node import ToolCallRequest
from langchain_core.messages import ToolMessage
from langchain_core.tools import BaseTool, StructuredTool
from langgraph.types import Command
from typing_extensions import NotRequired, TypedDict

from deepagents.backends import StateBackend
from deepagents.backends.protocol import EditResult, WriteResult


# =============================================================================
# STATE EXTENSION
# =============================================================================

class ScratchFileData(TypedDict):
    """Data structure for storing file contents with metadata."""
    content: list[str]
    """Lines of the file."""
    created_at: str
    """ISO 8601 timestamp of file creation."""
    modified_at: str
    """ISO 8601 timestamp of last modification."""


def _scratch_file_reducer(
    left: dict[str, ScratchFileData] | None, 
    right: dict[str, ScratchFileData | None]
) -> dict[str, ScratchFileData]:
    """Merge scratch file updates with support for deletions."""
    if left is None:
        return {k: v for k, v in right.items() if v is not None}
    
    result = {**left}
    for key, value in right.items():
        if value is None:
            result.pop(key, None)
        else:
            result[key] = value
    return result


class ScratchFilesState(AgentState):
    """State extension for scratch files.
    
    The scratch_files field is separate from the user's project files.
    Frontend displays these for transparency but they are read-only to users.
    """
    scratch_files: Annotated[NotRequired[dict[str, ScratchFileData]], _scratch_file_reducer]


# =============================================================================
# SYSTEM PROMPT
# =============================================================================

SCRATCH_FILES_SYSTEM_PROMPT = """## Scratch Files (Your Working Memory)

You have access to a scratch filesystem for your working notes and intermediate analysis.
These files are visible to the user for transparency but they cannot edit them.

**Available Tools:**
- `scratch_ls(path)` - List files in scratch space
- `scratch_read(file_path)` - Read a scratch file
- `scratch_write(file_path, content)` - Create a new scratch file
- `scratch_edit(file_path, old_string, new_string)` - Edit a scratch file

**Guidelines:**
- Use `/scratch/` prefix for all paths (e.g., `/scratch/notes.md`)
- Use scratch files for:
  - Research notes and analysis
  - Intermediate drafts before final output
  - Tracking your thought process
  - Storing scraped content temporarily
- Scratch files persist within the conversation
- When you have a final deliverable, use user file tools to save it (requires approval)"""


# =============================================================================
# TOOL DEFINITIONS
# =============================================================================

def _create_scratch_ls_tool() -> BaseTool:
    """Create the scratch_ls tool."""
    
    def scratch_ls(
        path: str = "/scratch/",
        runtime: ToolRuntime = None,
    ) -> str:
        """List files in your scratch working memory.
        
        Args:
            path: Directory path to list (default: /scratch/)
        
        Returns:
            List of files in the scratch directory.
        """
        backend = StateBackend(runtime)
        # Ensure path is within scratch
        if not path.startswith("/scratch"):
            path = "/scratch" + (path if path.startswith("/") else "/" + path)
        
        infos = backend.ls_info(path)
        if not infos:
            return f"No files in {path}"
        
        lines = []
        for info in infos:
            if info.get("is_dir"):
                lines.append(f"[DIR]  {info['path']}")
            else:
                lines.append(f"[FILE] {info['path']}")
        
        return "\n".join(lines)
    
    return StructuredTool.from_function(
        name="scratch_ls",
        func=scratch_ls,
        description="""List files in your scratch working memory.

Args:
    path: Directory path to list (default: /scratch/)

Returns list of files and directories in your scratch space.""",
    )


def _create_scratch_read_tool() -> BaseTool:
    """Create the scratch_read tool."""
    
    def scratch_read(
        file_path: str,
        runtime: ToolRuntime,
        offset: int = 0,
        limit: int = 500,
    ) -> str:
        """Read a file from your scratch working memory.
        
        Args:
            file_path: Path to the file (should start with /scratch/)
            offset: Line offset to start reading from
            limit: Maximum lines to read
        
        Returns:
            File content with line numbers.
        """
        backend = StateBackend(runtime)
        # Ensure path is within scratch
        if not file_path.startswith("/scratch"):
            file_path = "/scratch" + (file_path if file_path.startswith("/") else "/" + file_path)
        
        return backend.read(file_path, offset=offset, limit=limit)
    
    return StructuredTool.from_function(
        name="scratch_read",
        func=scratch_read,
        description="""Read a file from your scratch working memory.

Args:
    file_path: Path to the file (e.g., /scratch/notes.md)
    offset: Line offset to start reading (default: 0)
    limit: Max lines to read (default: 500)

Returns file content with line numbers.""",
    )


def _create_scratch_write_tool() -> BaseTool:
    """Create the scratch_write tool."""
    
    def scratch_write(
        file_path: str,
        content: str,
        runtime: ToolRuntime,
    ) -> Command | str:
        """Create a new file in your scratch working memory.
        
        Args:
            file_path: Path for the new file (should start with /scratch/)
            content: Content to write
        
        Returns:
            Success message or error.
        """
        backend = StateBackend(runtime)
        # Ensure path is within scratch
        if not file_path.startswith("/scratch"):
            file_path = "/scratch" + (file_path if file_path.startswith("/") else "/" + file_path)
        
        result: WriteResult = backend.write(file_path, content)
        
        if result.error:
            return result.error
        
        # Return Command to update state
        if result.files_update is not None:
            return Command(
                update={
                    "scratch_files": result.files_update,
                    "messages": [
                        ToolMessage(
                            content=f"Created scratch file: {result.path}",
                            tool_call_id=runtime.tool_call_id,
                        )
                    ],
                }
            )
        
        return f"Created scratch file: {result.path}"
    
    return StructuredTool.from_function(
        name="scratch_write",
        func=scratch_write,
        description="""Create a new file in your scratch working memory.

Args:
    file_path: Path for the file (e.g., /scratch/notes.md)
    content: Content to write

Creates a new scratch file. These files are visible to the user for transparency.""",
    )


def _create_scratch_edit_tool() -> BaseTool:
    """Create the scratch_edit tool."""
    
    def scratch_edit(
        file_path: str,
        old_string: str,
        new_string: str,
        runtime: ToolRuntime,
        replace_all: bool = False,
    ) -> Command | str:
        """Edit a file in your scratch working memory.
        
        Args:
            file_path: Path to the file to edit
            old_string: Text to find and replace
            new_string: Replacement text
            replace_all: Replace all occurrences (default: False)
        
        Returns:
            Success message or error.
        """
        backend = StateBackend(runtime)
        # Ensure path is within scratch
        if not file_path.startswith("/scratch"):
            file_path = "/scratch" + (file_path if file_path.startswith("/") else "/" + file_path)
        
        result: EditResult = backend.edit(file_path, old_string, new_string, replace_all=replace_all)
        
        if result.error:
            return result.error
        
        # Return Command to update state
        if result.files_update is not None:
            return Command(
                update={
                    "scratch_files": result.files_update,
                    "messages": [
                        ToolMessage(
                            content=f"Edited scratch file: {result.path} ({result.occurrences} replacement(s))",
                            tool_call_id=runtime.tool_call_id,
                        )
                    ],
                }
            )
        
        return f"Edited scratch file: {result.path}"
    
    return StructuredTool.from_function(
        name="scratch_edit",
        func=scratch_edit,
        description="""Edit a file in your scratch working memory.

Args:
    file_path: Path to the file (e.g., /scratch/notes.md)
    old_string: Text to find and replace
    new_string: Replacement text
    replace_all: Replace all occurrences (default: False)

Performs string replacement in the scratch file.""",
    )


# =============================================================================
# MIDDLEWARE
# =============================================================================

class ScratchFilesMiddleware(AgentMiddleware[ScratchFilesState, None]):
    """Middleware for agent scratch/working memory files.
    
    Provides tools for the agent to maintain its own working notes that are:
    - Stored in agent state (visible to frontend for transparency)
    - Separate from user files (use /scratch/ prefix)
    - No human approval required (agent's own working memory)
    - Read-only from user's perspective
    
    Example:
        ```python
        agent = create_agent(
            model,
            middleware=[
                ScratchFilesMiddleware(),
                ClientToolsMiddleware(),  # User files with HITL
            ],
        )
        ```
    """
    
    state_schema = ScratchFilesState
    
    def __init__(self) -> None:
        """Initialize scratch files middleware."""
        super().__init__()
        self.tools = [
            _create_scratch_ls_tool(),
            _create_scratch_read_tool(),
            _create_scratch_write_tool(),
            _create_scratch_edit_tool(),
        ]
    
    async def awrap_model_call(
        self,
        request: ModelRequest,
        handler: Callable[[ModelRequest], Awaitable[ModelResponse]],
    ) -> ModelResponse:
        """Add scratch files system prompt."""
        new_system_prompt = (
            request.system_prompt + "\n\n" + SCRATCH_FILES_SYSTEM_PROMPT
            if request.system_prompt
            else SCRATCH_FILES_SYSTEM_PROMPT
        )
        
        return await handler(request.override(system_prompt=new_system_prompt))
    
    def wrap_model_call(
        self,
        request: ModelRequest,
        handler: Callable[[ModelRequest], ModelResponse],
    ) -> ModelResponse:
        """Synchronous version - add scratch files system prompt."""
        new_system_prompt = (
            request.system_prompt + "\n\n" + SCRATCH_FILES_SYSTEM_PROMPT
            if request.system_prompt
            else SCRATCH_FILES_SYSTEM_PROMPT
        )
        
        return handler(request.override(system_prompt=new_system_prompt))

