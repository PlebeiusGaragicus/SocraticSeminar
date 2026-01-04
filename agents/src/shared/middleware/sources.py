"""SourcesMiddleware for accessing project sources.

Provides tools for agents to read and search project sources (web references,
PDFs, files) that are stored client-side. The source list is injected into
the system prompt on every invocation so agents always know what's available.

Key Patterns:
- Source list injected in system prompt (no need for list_sources tool)
- All source operations interrupt for client-side execution
- Operations are auto-approved (no HITL required)
"""

from collections.abc import Awaitable, Callable
from typing import Any

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

class SourcesState(AgentState):
    """State extension for project sources.
    
    The client provides the sources_list on every invocation.
    This allows the middleware to inject available sources into
    the system prompt without requiring a tool call.
    
    Fields:
        sources_list: List of source metadata from the client
            Each source has: id, title, url, sourceType ('url' or 'file')
    """
    
    # Injected by client on every invocation
    sources_list: NotRequired[list[dict] | None]


# =============================================================================
# SYSTEM PROMPT
# =============================================================================

SOURCES_SYSTEM_PROMPT = """## Project Sources

You have access to external sources (web references, PDFs, documents) that have been added to this project.

### Available Tools

- `list_sources(source_type?)` - List all sources, optionally filtered (returns from cached state)
- `read_source(source_id)` - Read the full markdown content of a source
- `search_sources(query, top_k?)` - Semantic search across all source contents

### Guidelines

1. **Sources are already listed** - You can see available sources below
2. **Use list_sources** to get the current list of sources (returns from cache)
3. **Use read_source** to get full content when you need details
4. **Use search_sources** for finding relevant information across sources
5. **Cite sources** using the source title when referencing content"""

SOURCES_LIST_HEADER = "\n\n### Available Sources\n\n"
NO_SOURCES_MESSAGE = "_No sources have been added to this project yet._"


# =============================================================================
# TOOL DEFINITIONS
# =============================================================================

def _create_list_sources_tool() -> StructuredTool:
    """Create the list_sources tool."""
    
    def list_sources(
        source_type: str | None = None,
        runtime: ToolRuntime = None,
    ) -> str:
        """List all sources in the current project, optionally filtered.
        
        Returns metadata about available sources including:
        - id: Unique source identifier
        - title: Source display name
        - url: Source URL (if applicable)
        - source_type: Type ('url' or 'file')
        
        This tool returns from cached state - no client query needed.
        
        Args:
            source_type: Optional filter by type ('url' or 'file')
        """
        # Handled by middleware - returns from state
        return "Tool execution pending"
    
    return StructuredTool.from_function(
        name="list_sources",
        func=list_sources,
        description="""List all sources in the project, optionally filtered.

Args:
    source_type: Optional filter by type ('url' or 'file')

Returns JSON array of source metadata with id, title, url, source_type.
This returns from cached state - use read_source to get full content.""",
    )


def _create_read_source_tool() -> StructuredTool:
    """Create the read_source tool."""
    
    def read_source(source_id: str, runtime: ToolRuntime = None) -> str:
        """Read the full markdown content of a source by its ID.
        
        Args:
            source_id: The unique identifier of the source to read.
                      Use the source IDs shown in "Available Sources".
        
        Returns:
            The source's markdown content, or an error if not found.
        """
        return "Tool execution pending - awaiting client response"
    
    return StructuredTool.from_function(
        name="read_source",
        func=read_source,
        description="""Read the full markdown content of a source by its ID.

Args:
    source_id: Unique identifier from the available sources list

Returns the source's markdown content or an error if not found.""",
    )


def _create_search_sources_tool() -> StructuredTool:
    """Create the search_sources tool."""
    
    def search_sources(
        query: str,
        top_k: int = 5,
        runtime: ToolRuntime = None,
    ) -> str:
        """Search across all project sources by content.
        
        Performs semantic search to find relevant excerpts from sources.
        
        Args:
            query: Search query describing what you're looking for
            top_k: Maximum results to return (default 5, max 10)
        
        Returns:
            JSON array of search results with source_id, title, excerpt, score
        """
        return "Tool execution pending - awaiting client response"
    
    return StructuredTool.from_function(
        name="search_sources",
        func=search_sources,
        description="""Search across all project sources by content.

Args:
    query: What to search for
    top_k: Max results (default 5)

Returns matching excerpts with relevance scores.""",
    )


# Tools that return from state (no interrupt)
STATE_RETURN_TOOLS = {"list_sources"}

# Tools that are auto-approved (interrupt but no HITL required)
AUTO_APPROVE_TOOLS = {"read_source", "search_sources"}


# =============================================================================
# MIDDLEWARE
# =============================================================================

class SourcesMiddleware(AgentMiddleware[SourcesState, None]):
    """Middleware for accessing project sources.
    
    The client injects sources_list on each invocation so list_sources can
    return data directly without interrupting. The sources list is also
    injected into the system prompt for LLM context.
    
    Tool Behavior:
    - list_sources: Returns from state (no interrupt)
    - read_source, search_sources: Auto-approved interrupt for client execution
    
    Example:
        ```python
        agent = create_agent(
            model,
            middleware=[
                SourcesMiddleware(),
            ],
        )
        
        # Invoke with sources list from client
        agent.invoke({
            "messages": [...],
            "sources_list": [
                {"id": "abc123", "title": "Bitcoin Whitepaper", "url": "https://...", "sourceType": "url"},
                {"id": "def456", "title": "Research Notes.pdf", "url": "notes.pdf", "sourceType": "file"},
            ]
        })
        ```
    
    Client Integration:
        When the agent calls read_source or search_sources, execution interrupts with:
        ```json
        {
            "type": "client_tool_execution",
            "tool_calls": [
                {"id": "...", "name": "read_source", "args": {"source_id": "..."}}
            ],
            "auto_approve": true
        }
        ```
        
        Client should resume with:
        ```json
        {
            "tool_results": [
                {"tool_call_id": "...", "content": "markdown content..."}
            ]
        }
        ```
    """
    
    state_schema = SourcesState
    
    def __init__(self) -> None:
        """Initialize sources middleware."""
        super().__init__()
        self.tools = [
            _create_list_sources_tool(),
            _create_read_source_tool(),
            _create_search_sources_tool(),
        ]
    
    def _format_sources_list(self, sources_list: list[dict] | None) -> str:
        """Format the sources list for the system prompt."""
        if not sources_list:
            return NO_SOURCES_MESSAGE
        
        lines = []
        for source in sources_list:
            source_id = source.get("id", "unknown")
            title = source.get("title", "Untitled")
            source_type = source.get("sourceType", "url")
            url = source.get("url", "")
            
            # Format: - [id: abc123] Bitcoin Whitepaper (url) - https://...
            type_label = "file" if source_type == "file" else "url"
            url_display = f" - {url}" if url and source_type == "url" else ""
            lines.append(f"- **[{source_id}]** {title} ({type_label}){url_display}")
        
        return "\n".join(lines)
    
    async def awrap_model_call(
        self,
        request: ModelRequest,
        handler: Callable[[ModelRequest], Awaitable[ModelResponse]],
    ) -> ModelResponse:
        """Inject sources list into system prompt."""
        # Get sources from state (passed in by client)
        sources_list = getattr(request, 'state', {}).get('sources_list') if hasattr(request, 'state') else None
        
        # Build sources section
        sources_section = SOURCES_SYSTEM_PROMPT + SOURCES_LIST_HEADER + self._format_sources_list(sources_list)
        
        new_system_prompt = (
            request.system_prompt + "\n\n" + sources_section
            if request.system_prompt
            else sources_section
        )
        
        return await handler(request.override(system_prompt=new_system_prompt))
    
    def wrap_model_call(
        self,
        request: ModelRequest,
        handler: Callable[[ModelRequest], ModelResponse],
    ) -> ModelResponse:
        """Synchronous version - inject sources list into system prompt."""
        # Get sources from state (passed in by client)
        sources_list = getattr(request, 'state', {}).get('sources_list') if hasattr(request, 'state') else None
        
        # Build sources section
        sources_section = SOURCES_SYSTEM_PROMPT + SOURCES_LIST_HEADER + self._format_sources_list(sources_list)
        
        new_system_prompt = (
            request.system_prompt + "\n\n" + sources_section
            if request.system_prompt
            else sources_section
        )
        
        return handler(request.override(system_prompt=new_system_prompt))
    
    async def awrap_tool_call(
        self,
        request: ToolCallRequest,
        handler: Callable[[ToolCallRequest], Awaitable[ToolMessage | Command]],
    ) -> ToolMessage | Command:
        """Intercept source tool calls.
        
        Flow:
        1. list_sources: Returns from state directly (no interrupt)
        2. read_source, search_sources: Interrupt for client-side execution (auto-approved)
        """
        tool_name = request.tool_call.get("name", "")
        tool_call_id = request.tool_call.get("id", "")
        tool_args = request.tool_call.get("args", {})
        
        # Handle list_sources specially - return from state, no interrupt
        if tool_name in STATE_RETURN_TOOLS:
            return self._handle_list_sources(request, tool_call_id, tool_args)
        
        # Check if this is a source tool that needs interrupt
        if tool_name not in AUTO_APPROVE_TOOLS:
            # Not our tool, pass through
            return await handler(request)
        
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
            "auto_approve": True,
            "requires_approval": False,
        }
        
        print(f"[Sources] Interrupting for {tool_name} (auto-approved)")
        
        # Interrupt and wait for client response
        resume_value = interrupt(interrupt_data)
        
        print(f"[Sources] Resumed with: {type(resume_value)}")
        
        # Extract result from client response
        result_content = _extract_tool_result(resume_value, tool_call_id)
        
        return ToolMessage(
            content=result_content,
            tool_call_id=tool_call_id,
            name=tool_name,
        )
    
    def _handle_list_sources(
        self,
        request: ToolCallRequest,
        tool_call_id: str,
        tool_args: dict,
    ) -> ToolMessage:
        """Handle list_sources by returning from state (no interrupt).
        
        The sources_list is injected by the client on each invocation,
        so we can return it directly without interrupting.
        """
        import json
        
        # Get sources_list from state
        state = request.runtime.state if hasattr(request, 'runtime') and request.runtime else {}
        sources_list = state.get("sources_list", []) or []
        
        # Apply optional source_type filter
        source_type_filter = tool_args.get("source_type")
        if source_type_filter:
            sources_list = [s for s in sources_list if s.get("sourceType") == source_type_filter or s.get("source_type") == source_type_filter]
        
        if not sources_list:
            result = "No sources found in project." if not source_type_filter else f"No sources of type '{source_type_filter}' found."
        else:
            # Format as JSON for the model
            result = json.dumps(sources_list, indent=2)
        
        print(f"[Sources] list_sources returned {len(sources_list)} sources from state")
        
        return ToolMessage(
            content=result,
            tool_call_id=tool_call_id,
            name="list_sources",
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
        
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(
                self.awrap_tool_call(request, async_handler)
            )
        finally:
            loop.close()


def _extract_tool_result(resume_value: Any, tool_call_id: str) -> str:
    """Extract tool result from client's resume response.
    
    Expected formats:
    1. { "tool_results": [{"tool_call_id": "...", "content": "..."}] }
    2. Direct string content
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
        
        # Check for direct content
        if "content" in resume_value:
            return resume_value["content"]
        
        # Check for error
        if "error" in resume_value:
            return f"Error: {resume_value['error']}"
    
    return f"Unexpected response format: {resume_value}"

