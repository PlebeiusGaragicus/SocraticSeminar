"""WebsearchMiddleware for URL discovery and content fetching.

Provides tools for the agent to search the web using Tavily and fetch full
webpage content via the centralized backend scraping service.

All actual scraping is delegated to the backend /api/scrape endpoints for
consistency between agent and frontend scraping behavior.
"""

import json
import os
from collections.abc import Awaitable, Callable
from typing import TypedDict

import httpx
from langchain_core.tools import InjectedToolArg, tool
from tavily import TavilyClient
from typing_extensions import Annotated, Literal
from langchain.agents.middleware.types import AgentMiddleware, AgentState, ModelRequest, ModelResponse

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

def fetch_webpage_content(url: str, timeout: float = 15.0) -> str:
    """Fetch webpage content via backend scraping service.
    
    Delegates to the backend /api/scrape endpoint for consistent scraping.
    Returns markdown content.
    """
    try:
        response = httpx.post(
            f"{BACKEND_URL}/api/scrape",
            json={"url": url, "timeout": timeout},
            timeout=timeout + 5.0  # Add buffer for backend processing
        )
        response.raise_for_status()
        data = response.json()
        return data.get("content", "")
    except httpx.TimeoutException:
        return f"Error: Timeout fetching content from {url}"
    except httpx.HTTPStatusError as e:
        return f"Error: HTTP {e.response.status_code} fetching {url}"
    except Exception as e:
        return f"Error fetching content from {url}: {str(e)}"


def fetch_and_extract_source(url: str, timeout: float = 15.0) -> ScrapedSource:
    """Fetch a webpage via backend and extract structured source data.
    
    Delegates to the backend /api/scrape endpoint which handles:
    - HTML fetching with proper user agent
    - Markdown conversion
    - Bibliography metadata extraction
    
    Returns structured data suitable for creating a source in the frontend.
    """
    try:
        response = httpx.post(
            f"{BACKEND_URL}/api/scrape",
            json={"url": url, "timeout": timeout},
            timeout=timeout + 5.0
        )
        response.raise_for_status()
        data = response.json()
        
        # Convert backend response to ScrapedSource format
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
            scraped_at=data.get("scraped_at", 0)
        )
        
    except Exception as e:
        # Return error source on failure
        return ScrapedSource(
            url=url,
            title=url.split("/")[-1] or url,
            content=f"Error fetching content: {str(e)}",
            bibliography=Bibliography(publisher=url),
            scraped_at=0
        )


# =============================================================================
# AGENT TOOLS
# =============================================================================

@tool(parse_docstring=True)
def tavily_search(
    query: str,
    max_results: Annotated[int, InjectedToolArg] = 3,
    topic: Annotated[
        Literal["general", "news", "finance"], InjectedToolArg
    ] = "general",
    include_full_content: bool = True,
) -> str:
    """Search the web for information on a given query.

    Uses Tavily to discover relevant URLs and optionally fetches full webpage content as markdown.

    Args:
        query: Search query to execute
        max_results: Maximum number of results to return (default: 3)
        topic: Topic filter - 'general', 'news', or 'finance' (default: 'general')
        include_full_content: If True, fetch full webpage content; if False, use Tavily snippets
    """
    # Use Tavily to discover URLs
    search_results = tavily_client.search(
        query,
        max_results=max_results,
        topic=topic,
    )

    # Format results
    result_texts = []
    for result in search_results.get("results", []):
        url = result["url"]
        title = result["title"]
        snippet = result.get("content", "")

        if include_full_content:
            # Fetch full webpage content via backend
            content = fetch_webpage_content(url)
            # Truncate if too long to avoid context overflow
            if len(content) > 15000:
                content = content[:15000] + "\n\n... [content truncated] ..."
        else:
            content = snippet

        result_text = f"""## {title}
**URL:** {url}

{content}

---
"""
        result_texts.append(result_text)

    # Format final response
    response = f"""Found {len(result_texts)} result(s) for '{query}':

{"".join(result_texts)}"""

    return response


@tool(parse_docstring=True)
def fetch_webpage(url: str) -> str:
    """Fetch a specific webpage and convert it to markdown.

    Use this when you have a specific URL you want to read in full.

    Args:
        url: URL of the webpage to fetch
    """
    content = fetch_webpage_content(url)
    
    # Truncate if too long
    if len(content) > 20000:
        content = content[:20000] + "\n\n... [content truncated due to length] ..."
    
    return f"""# Content from: {url}

{content}"""


@tool(parse_docstring=True)
def scrape_url_to_source(url: str) -> str:
    """Scrape a URL and extract structured source data with bibliography metadata.
    
    This tool fetches a webpage, converts it to markdown, and extracts citation
    metadata (author, title, published date, publisher) from meta tags.
    
    Use this when the user wants to add a URL as a research source. After calling
    this tool, use the `create_source` tool to save the source to the user's project.
    
    The result is a JSON object with title, content (markdown), and bibliography metadata.
    
    Args:
        url: The URL to scrape and extract source data from
    """
    source_data = fetch_and_extract_source(url)
    
    # Return as JSON for the agent to parse and use with create_source
    return json.dumps(dict(source_data), indent=2)


# =============================================================================
# MIDDLEWARE
# =============================================================================

class WebsearchMiddleware(AgentMiddleware[AgentState, None]):
    """Middleware that provides web search and content fetching tools.
    
    Uses Tavily for URL discovery and the backend /api/scrape service for
    consistent content fetching and metadata extraction.
    """
    
    def __init__(self) -> None:
        """Initialize websearch middleware."""
        super().__init__()
        self.tools = [tavily_search, fetch_webpage, scrape_url_to_source]
    
    async def awrap_model_call(
        self,
        request: ModelRequest,
        handler: Callable[[ModelRequest], Awaitable[ModelResponse]],
    ) -> ModelResponse:
        """Add websearch tools instructions to system prompt."""
        websearch_instructions = "## Web Search Tools\n\nYou have tools to search the web and fetch webpage content. Use `tavily_search` for discovery and `fetch_webpage` when you have a specific URL to read."
        
        new_system_prompt = (
            request.system_prompt + "\n\n" + websearch_instructions
            if request.system_prompt
            else websearch_instructions
        )
        
        return await handler(request.override(system_prompt=new_system_prompt))
    
    def wrap_model_call(
        self,
        request: ModelRequest,
        handler: Callable[[ModelRequest], ModelResponse],
    ) -> ModelResponse:
        """Synchronous version - add websearch tools instructions."""
        websearch_instructions = "## Web Search Tools\n\nYou have tools to search the web and fetch webpage content. Use `tavily_search` for discovery and `fetch_webpage` when you have a specific URL to read."
        
        new_system_prompt = (
            request.system_prompt + "\n\n" + websearch_instructions
            if request.system_prompt
            else websearch_instructions
        )
        
        return handler(request.override(system_prompt=new_system_prompt))
