"""WebsearchMiddleware for URL discovery and content fetching.

Provides tools for the agent to search the web using Tavily and fetch full
webpage content converted to markdown.
"""

import httpx
from collections.abc import Awaitable, Callable
from langchain_core.tools import InjectedToolArg, tool
from markdownify import markdownify
from tavily import TavilyClient
from typing_extensions import Annotated, Literal
from langchain.agents.middleware.types import AgentMiddleware, AgentState, ModelRequest, ModelResponse

# Initialize Tavily client (requires TAVILY_API_KEY env var)
tavily_client = TavilyClient()


def fetch_webpage_content(url: str, timeout: float = 10.0) -> str:
    """Fetch and convert webpage content to markdown."""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }

    try:
        response = httpx.get(url, headers=headers, timeout=timeout, follow_redirects=True)
        response.raise_for_status()
        return markdownify(response.text)
    except Exception as e:
        return f"Error fetching content from {url}: {str(e)}"


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
            # Fetch full webpage content
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


class WebsearchMiddleware(AgentMiddleware[AgentState, None]):
    """Middleware that provides web search and content fetching tools.
    
    Uses Tavily for discovery and httpx+markdownify for content retrieval.
    """
    
    def __init__(self) -> None:
        """Initialize websearch middleware."""
        super().__init__()
        self.tools = [tavily_search, fetch_webpage]
    
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

