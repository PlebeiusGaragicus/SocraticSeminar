"""WebsearchMiddleware for URL discovery, scraping, and source creation.

Provides tools for the agent to:
1. Search the web using Tavily - auto-creates sources from results
2. Scrape specific URLs using Firecrawl - requires HITL approval (costs money)

All scraping is delegated to the backend /api/scrape endpoints which support
both markdownify and Firecrawl methods.

Key Patterns:
- Scraping (scrape_url) requires HITL approval since it costs money
- Web search (web_search) auto-creates sources via client tool calls
- All source creation goes through ClientToolsMiddleware's create_source
"""

import asyncio
import json
import os
from collections.abc import Awaitable, Callable
from typing import Any, Literal, TypedDict

import httpx
from langchain.agents.middleware.types import AgentMiddleware, AgentState, ModelRequest, ModelResponse
from langchain.tools import ToolRuntime
from langchain.tools.tool_node import ToolCallRequest
from langchain_core.messages import ToolMessage
from langchain_core.tools import StructuredTool
from langgraph.types import Command, interrupt
from tavily import TavilyClient
from typing_extensions import NotRequired

# Initialize Tavily client (requires TAVILY_API_KEY env var)
tavily_client = TavilyClient()

# Backend URL for scraping service
BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")


# =============================================================================
# TYPES
# =============================================================================

class Bibliography(TypedDict, total=False):
    """Bibliography metadata for citation purposes."""
    author: str
    title: str
    publishedDate: str
    publisher: str
    resourceType: str


class ScrapedSource(TypedDict):
    """Structured scraped source data."""
    url: str
    title: str
    content: str
    bibliography: Bibliography
    scraped_at: int


# =============================================================================
# BACKEND SCRAPING FUNCTIONS
# =============================================================================

async def scrape_url_via_backend(
    url: str,
    method: Literal["markdownify", "firecrawl"] = "firecrawl",
    timeout: float = 30.0,
    generate_pdf: bool = False,
) -> ScrapedSource:
    """Scrape URL via backend service (async).
    
    Args:
        url: URL to scrape
        method: Scraping method - 'firecrawl' (default) or 'markdownify'
        timeout: Request timeout
        generate_pdf: Whether to generate PDF preview
        
    Returns:
        Structured source data with title, content, bibliography
    """
    try:
        async with httpx.AsyncClient(timeout=timeout + 10.0, follow_redirects=True) as client:
            response = await client.post(
                f"{BACKEND_URL}/api/scrape/",
                json={
                    "url": url,
                    "timeout": timeout,
                    "method": method,
                    "generate_pdf": generate_pdf,
                },
            )
            response.raise_for_status()
            data = response.json()
        
        return ScrapedSource(
            url=data["url"],
            title=data["title"],
            content=data["content"],
            bibliography=Bibliography(
                author=data["bibliography"].get("author"),
                title=data["bibliography"].get("title"),
                publishedDate=data["bibliography"].get("publishedDate"),
                publisher=data["bibliography"].get("publisher"),
                resourceType=data["bibliography"].get("resourceType"),
            ),
            scraped_at=data.get("scraped_at", 0),
        )
        
    except httpx.TimeoutException:
        return ScrapedSource(
            url=url,
            title=url.split("/")[-1] or url,
            content=f"Error: Timeout scraping {url}",
            bibliography=Bibliography(publisher=url),
            scraped_at=0,
        )
    except httpx.HTTPStatusError as e:
        return ScrapedSource(
            url=url,
            title=url.split("/")[-1] or url,
            content=f"Error: HTTP {e.response.status_code} scraping {url}",
            bibliography=Bibliography(publisher=url),
            scraped_at=0,
        )
    except Exception as e:
        return ScrapedSource(
            url=url,
            title=url.split("/")[-1] or url,
            content=f"Error scraping {url}: {str(e)}",
            bibliography=Bibliography(publisher=url),
            scraped_at=0,
        )


async def fetch_webpage_content(url: str, timeout: float = 15.0) -> str:
    """Fetch webpage content via backend (async, simple markdown fetch).
    
    Uses markdownify for speed. For better quality, use scrape_url_via_backend with firecrawl.
    """
    try:
        async with httpx.AsyncClient(timeout=timeout + 5.0, follow_redirects=True) as client:
            response = await client.post(
                f"{BACKEND_URL}/api/scrape/",
                json={"url": url, "timeout": timeout, "method": "markdownify", "generate_pdf": False},
            )
            response.raise_for_status()
            data = response.json()
        return data.get("content", "")
    except Exception as e:
        return f"Error fetching {url}: {str(e)}"


# =============================================================================
# TOOL DEFINITIONS
# =============================================================================

def _create_scrape_url_tool() -> StructuredTool:
    """Create the scrape_url tool for scraping URLs with Firecrawl."""
    
    def scrape_url(
        url: str,
        method: Literal["firecrawl", "markdownify"] = "firecrawl",
        runtime: ToolRuntime = None,
) -> str:
        """Scrape a URL and extract content as markdown.

        This tool requires human approval as it costs money (Firecrawl API).
        After scraping, use `create_source` to save the result as a project source.

    Args:
            url: The URL to scrape
            method: Scraping method - 'firecrawl' (better quality, costs money) 
                   or 'markdownify' (free but lower quality). Default: firecrawl
        
        Returns:
            JSON with url, title, content (markdown), and bibliography metadata.
            Use this data with `create_source` to save to the project.
        """
        return "Tool execution pending - awaiting approval"
    
    return StructuredTool.from_function(
        name="scrape_url",
        func=scrape_url,
        description="""Scrape a URL to extract content as markdown.

REQUIRES HUMAN APPROVAL (costs money for Firecrawl).

Args:
    url: The URL to scrape
    method: 'firecrawl' (default, better quality) or 'markdownify' (free)

Returns JSON with title, content, and bibliography. 
After scraping, use `create_source` to save as a project source.""",
    )


def _create_web_search_tool() -> StructuredTool:
    """Create the web_search tool for searching with Tavily."""
    
    def web_search(
        query: str,
        max_results: int = 5,
        topic: Literal["general", "news", "finance"] = "general",
        runtime: ToolRuntime = None,
    ) -> str:
        """Search the web for information on a query.
        
        Uses Tavily to find relevant URLs and fetches their content.
        Search results are automatically added as project sources.
        
        Args:
            query: Search query to execute
            max_results: Maximum results to return (default: 5, max: 10)
            topic: Topic filter - 'general', 'news', or 'finance'
        
        Returns:
            Formatted search results with titles, URLs, and content excerpts.
            Sources are automatically saved to the project.
        """
        return "Tool execution pending - awaiting client response"
    
    return StructuredTool.from_function(
        name="web_search",
        func=web_search,
        description="""Search the web for information.

Uses Tavily to find relevant URLs and content.
Results are automatically saved as project sources.

Args:
    query: What to search for
    max_results: Max results (default 5, max 10)
    topic: 'general' (default), 'news', or 'finance'

Returns formatted results with titles, URLs, and content.""",
    )


def _create_fetch_webpage_tool() -> StructuredTool:
    """Create the fetch_webpage tool for quick content fetching."""
    
    def fetch_webpage(url: str, runtime: ToolRuntime = None) -> str:
        """Fetch a webpage and convert to markdown (quick, free method).
        
        Use this for quick reads. For permanent sources, use `scrape_url` instead.

    Args:
        url: URL of the webpage to fetch
    """
        return "Tool execution pending"
    
    return StructuredTool.from_function(
        name="fetch_webpage",
        func=fetch_webpage,
        description="""Fetch a webpage as markdown (quick, free method).

For quick reads only. To save as a source, use `scrape_url` instead.

Args:
    url: URL to fetch

Returns the page content as markdown.""",
    )


# Tools requiring HITL approval (cost money)
HITL_REQUIRED_TOOLS = {"scrape_url"}

# Tools that execute server-side but interrupt for source creation
AUTO_SOURCE_TOOLS = {"web_search"}

# Tools that execute server-side without interrupt
DIRECT_EXECUTE_TOOLS = {"fetch_webpage"}


# =============================================================================
# SYSTEM PROMPT
# =============================================================================

WEBSEARCH_SYSTEM_PROMPT = """## Web Search & Scraping Tools

You have tools to search the web and scrape URLs for research.

### Tools

**`web_search(query, max_results?, topic?)`**
- Search the web using Tavily
- Results are automatically saved as project sources
- Use for discovering information on a topic

**`scrape_url(url, method?)`**
- Scrape a specific URL with high-quality extraction
- **Requires human approval** (Firecrawl costs money)
- Default method is 'firecrawl' (better quality)
- After scraping, use `create_source` to save to project

**`fetch_webpage(url)`**
- Quick webpage fetch (free, lower quality)
- Good for one-time reads, not for saving as sources

### Workflow for Adding Sources

When a user asks to add a URL as a source:
1. Call `scrape_url(url)` - user will approve (costs money)
2. Call `create_source(...)` with the scraped data to save it

When researching a topic:
1. Call `web_search(query)` - sources are auto-saved
2. Use the results for your research"""


# =============================================================================
# MIDDLEWARE
# =============================================================================

class WebsearchMiddleware(AgentMiddleware[AgentState, None]):
    """Middleware for web search and URL scraping.
    
    Provides three tools with different behaviors:
    
    1. scrape_url - HITL approval required, uses Firecrawl by default
    2. web_search - Tavily search, auto-creates sources via client interrupt
    3. fetch_webpage - Quick fetch, no interrupt, no source creation
    
    Example:
        ```python
        agent = create_agent(
            model,
            middleware=[
                WebsearchMiddleware(),
            ],
        )
        ```
    """
    
    def __init__(self) -> None:
        """Initialize websearch middleware."""
        super().__init__()
        self.tools = [
            _create_scrape_url_tool(),
            _create_web_search_tool(),
            _create_fetch_webpage_tool(),
        ]
    
    async def awrap_model_call(
        self,
        request: ModelRequest,
        handler: Callable[[ModelRequest], Awaitable[ModelResponse]],
    ) -> ModelResponse:
        """Add websearch instructions to system prompt."""
        new_system_prompt = (
            request.system_prompt + "\n\n" + WEBSEARCH_SYSTEM_PROMPT
            if request.system_prompt
            else WEBSEARCH_SYSTEM_PROMPT
        )
        
        return await handler(request.override(system_prompt=new_system_prompt))
    
    def wrap_model_call(
        self,
        request: ModelRequest,
        handler: Callable[[ModelRequest], ModelResponse],
    ) -> ModelResponse:
        """Synchronous version - add websearch instructions."""
        new_system_prompt = (
            request.system_prompt + "\n\n" + WEBSEARCH_SYSTEM_PROMPT
            if request.system_prompt
            else WEBSEARCH_SYSTEM_PROMPT
        )
        
        return handler(request.override(system_prompt=new_system_prompt))
    
    async def awrap_tool_call(
        self,
        request: ToolCallRequest,
        handler: Callable[[ToolCallRequest], Awaitable[ToolMessage | Command]],
    ) -> ToolMessage | Command:
        """Handle tool calls with appropriate interrupt/execution patterns."""
        tool_name = request.tool_call.get("name", "")
        tool_call_id = request.tool_call.get("id", "")
        tool_args = request.tool_call.get("args", {})
        
        # Handle HITL-required tools (scrape_url)
        if tool_name in HITL_REQUIRED_TOOLS:
            return await self._handle_scrape_url(tool_call_id, tool_args)
        
        # Handle auto-source tools (web_search)
        if tool_name in AUTO_SOURCE_TOOLS:
            return await self._handle_web_search(tool_call_id, tool_args)
        
        # Handle direct execute tools (fetch_webpage)
        if tool_name in DIRECT_EXECUTE_TOOLS:
            return await self._handle_fetch_webpage(tool_call_id, tool_args)
        
        # Not our tool, pass through
        return await handler(request)
    
    async def _handle_scrape_url(
        self,
        tool_call_id: str,
        tool_args: dict[str, Any],
    ) -> ToolMessage:
        """Handle scrape_url with HITL approval.
        
        Flow:
        1. Interrupt for human approval (show URL and cost warning)
        2. If approved, scrape with specified method
        3. Return scraped content for agent to use with create_source
        """
        url = tool_args.get("url", "")
        method = tool_args.get("method", "firecrawl")
        
        # Build HITL interrupt data
        interrupt_data = {
            "type": "human_approval_required",
            "tool_calls": [
                {
                    "id": tool_call_id,
                    "name": "scrape_url",
                    "args": tool_args,
                }
            ],
            "auto_approve": False,
            "requires_approval": True,
            "action_requests": [
                {
                    "name": "scrape_url",
                    "args": tool_args,
                    "description": f"Scrape URL using {method}:\n\n{url}\n\n⚠️ This will use the Firecrawl API which costs money.",
                }
            ],
            "review_configs": [
                {
                    "action_name": "scrape_url",
                    "allowed_decisions": ["approve", "reject"],
                }
            ],
        }
        
        print(f"[Websearch] HITL interrupt for scrape_url: {url}")
        
        # Interrupt for approval
        resume_value = interrupt(interrupt_data)
        
        print(f"[Websearch] HITL resumed with: {type(resume_value)}")
        
        # Check if approved
        if isinstance(resume_value, dict):
            decisions = resume_value.get("decisions", [])
            if decisions and decisions[0].get("type") == "reject":
                return ToolMessage(
                    content="Scraping rejected by user.",
                    tool_call_id=tool_call_id,
                    name="scrape_url",
                )
        
        # Approved - execute the scrape
        print(f"[Websearch] Scraping approved, using {method}: {url}")
        source_data = await scrape_url_via_backend(url, method=method)
        
        # Return as JSON for agent to use with create_source
        result = json.dumps({
            "url": source_data["url"],
            "title": source_data["title"],
            "content": source_data["content"],
            "bibliography": dict(source_data["bibliography"]),
            "scraped_at": source_data["scraped_at"],
        }, indent=2)
        
        return ToolMessage(
            content=f"Successfully scraped: {source_data['title']}\n\n{result}\n\n**Next step**: Use `create_source` with this data to save it to your project.",
            tool_call_id=tool_call_id,
            name="scrape_url",
        )
    
    async def _handle_web_search(
        self,
        tool_call_id: str,
        tool_args: dict[str, Any],
    ) -> ToolMessage:
        """Handle web_search with Tavily and auto-create sources.
        
        Flow:
        1. Execute Tavily search
        2. For each result, fetch content
        3. Batch interrupt to create all sources via client
        4. Return formatted results to agent
        """
        query = tool_args.get("query", "")
        max_results = min(tool_args.get("max_results", 5), 10)
        topic = tool_args.get("topic", "general")
        
        print(f"[Websearch] Tavily search: '{query}' (max: {max_results}, topic: {topic})")
        
        # Execute Tavily search (run sync SDK in thread pool to avoid blocking)
        try:
            search_results = await asyncio.to_thread(
                tavily_client.search,
                query,
                max_results=max_results,
                topic=topic,
            )
        except Exception as e:
            return ToolMessage(
                content=f"Error searching: {str(e)}",
                tool_call_id=tool_call_id,
                name="web_search",
            )
        
        results = search_results.get("results", [])
        if not results:
            return ToolMessage(
                content=f"No results found for '{query}'",
                tool_call_id=tool_call_id,
                name="web_search",
            )
        
        # Fetch content and build source data for each result
        sources_to_create = []
        result_texts = []
        
        for result in results:
            url = result["url"]
            title = result["title"]
            snippet = result.get("content", "")
            
            # Fetch full content via backend (using markdownify for speed)
            content = await fetch_webpage_content(url)
            
            # Truncate if too long
            if len(content) > 15000:
                content = content[:15000] + "\n\n... [content truncated] ..."
            
            # Build source data for create_source
            sources_to_create.append({
                "url": url,
                "title": title,
                "content": content,
                "author": None,
                "published_date": None,
                "publisher": None,
                "resource_type": "Article",
            })
            
            # Build result text
            result_texts.append(f"""## {title}
**URL:** {url}

{content[:3000]}{"..." if len(content) > 3000 else ""}

---
""")
        
        # Batch interrupt to create all sources via client
        print(f"[Websearch] Creating {len(sources_to_create)} sources via client")
        
        create_source_calls = [
            {
                "id": f"{tool_call_id}_source_{i}",
                "name": "create_source",
                "args": source,
            }
            for i, source in enumerate(sources_to_create)
        ]
        
        interrupt_data = {
            "type": "client_tool_execution",
            "tool_calls": create_source_calls,
            "auto_approve": True,
            "requires_approval": False,
            "batch_description": f"Creating {len(sources_to_create)} sources from web search: '{query}'",
        }
        
        # Interrupt to create sources
        resume_value = interrupt(interrupt_data)
        
        print(f"[Websearch] Sources created, building response")
        
        # Format final response
        response = f"""Found {len(results)} result(s) for '{query}':

{chr(10).join(result_texts)}

✅ **{len(sources_to_create)} sources have been added to your project.**
Use `read_source(source_id)` or `search_sources(query)` to access them."""
        
        return ToolMessage(
            content=response,
            tool_call_id=tool_call_id,
            name="web_search",
        )
    
    async def _handle_fetch_webpage(
        self,
        tool_call_id: str,
        tool_args: dict[str, Any],
    ) -> ToolMessage:
        """Handle fetch_webpage - direct execution, no interrupt."""
        url = tool_args.get("url", "")
        
        print(f"[Websearch] Fetching webpage: {url}")
        
        content = await fetch_webpage_content(url)
        
        # Truncate if too long
        if len(content) > 20000:
            content = content[:20000] + "\n\n... [content truncated] ..."
        
        return ToolMessage(
            content=f"# Content from: {url}\n\n{content}",
            tool_call_id=tool_call_id,
            name="fetch_webpage",
        )
    
    def wrap_tool_call(
        self,
        request: ToolCallRequest,
        handler: Callable[[ToolCallRequest], ToolMessage | Command],
    ) -> ToolMessage | Command:
        """Synchronous version of tool call handling."""
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
