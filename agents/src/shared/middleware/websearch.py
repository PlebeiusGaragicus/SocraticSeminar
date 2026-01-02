"""WebsearchMiddleware for URL discovery and content fetching.

Provides tools for the agent to search the web using Tavily and fetch full
webpage content converted to markdown.
"""

import re
import httpx
from collections.abc import Awaitable, Callable
from langchain_core.tools import InjectedToolArg, tool
from markdownify import markdownify
from tavily import TavilyClient
from typing import TypedDict
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


# =============================================================================
# BIBLIOGRAPHY EXTRACTION
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


def _extract_meta_content(html: str, *names: str) -> str | None:
    """Extract content from meta tag by name or property."""
    for name in names:
        # Check name attribute
        match = re.search(
            rf'<meta\s+[^>]*name=["\']?{re.escape(name)}["\']?\s+[^>]*content=["\']([^"\']+)["\']',
            html,
            re.IGNORECASE
        )
        if match:
            return match.group(1).strip()
        
        # Check property attribute (for Open Graph)
        match = re.search(
            rf'<meta\s+[^>]*property=["\']?{re.escape(name)}["\']?\s+[^>]*content=["\']([^"\']+)["\']',
            html,
            re.IGNORECASE
        )
        if match:
            return match.group(1).strip()
        
        # Check reversed order (content before name/property)
        match = re.search(
            rf'<meta\s+[^>]*content=["\']([^"\']+)["\']?\s+[^>]*(?:name|property)=["\']?{re.escape(name)}["\']?',
            html,
            re.IGNORECASE
        )
        if match:
            return match.group(1).strip()
    
    return None


def _extract_title(html: str) -> str:
    """Extract page title from HTML."""
    # Try Open Graph title first
    og_title = _extract_meta_content(html, "og:title")
    if og_title:
        return og_title
    
    # Fall back to <title> tag
    match = re.search(r'<title[^>]*>([^<]+)</title>', html, re.IGNORECASE)
    if match:
        return match.group(1).strip()
    
    return "Untitled"


def _extract_bibliography(html: str, url: str) -> Bibliography:
    """Extract bibliography metadata from HTML meta tags."""
    bib: Bibliography = {}
    
    # Author - try various meta tag formats
    author = _extract_meta_content(
        html,
        "author", "article:author", "og:author", 
        "twitter:creator", "dc.creator", "citation_author"
    )
    if author:
        bib["author"] = author
    
    # Title
    title = _extract_title(html)
    if title and title != "Untitled":
        bib["title"] = title
    
    # Published date
    date = _extract_meta_content(
        html,
        "article:published_time", "og:published_time",
        "publication_date", "date", "dc.date",
        "citation_publication_date", "datePublished"
    )
    if date:
        bib["publishedDate"] = date
    
    # Publisher/site name
    publisher = _extract_meta_content(
        html,
        "og:site_name", "publisher", "dc.publisher",
        "citation_journal_title", "application-name"
    )
    if publisher:
        bib["publisher"] = publisher
    else:
        # Extract domain as fallback publisher
        from urllib.parse import urlparse
        domain = urlparse(url).netloc
        if domain:
            # Remove www. prefix if present
            domain = re.sub(r'^www\.', '', domain)
            bib["publisher"] = domain
    
    # Resource type
    resource_type = _extract_meta_content(
        html,
        "og:type", "dc.type", "citation_type"
    )
    if resource_type:
        bib["resourceType"] = resource_type.capitalize()
    else:
        bib["resourceType"] = "Article"  # Default
    
    return bib


def fetch_and_extract_source(url: str, timeout: float = 15.0) -> ScrapedSource:
    """Fetch a webpage and extract structured source data with bibliography.
    
    Returns structured data suitable for creating a source in the frontend.
    """
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    try:
        response = httpx.get(url, headers=headers, timeout=timeout, follow_redirects=True)
        response.raise_for_status()
        html = response.text
        
        # Extract bibliography from raw HTML (before markdownification)
        bibliography = _extract_bibliography(html, url)
        title = bibliography.get("title") or _extract_title(html)
        
        # Convert to markdown
        content = markdownify(html)
        
        # Truncate if too long
        if len(content) > 50000:
            content = content[:50000] + "\n\n... [content truncated] ..."
        
        return ScrapedSource(
            url=url,
            title=title,
            content=content,
            bibliography=bibliography
        )
        
    except Exception as e:
        return ScrapedSource(
            url=url,
            title=url.split("/")[-1] or url,
            content=f"Error fetching content: {str(e)}",
            bibliography=Bibliography(publisher=url)
        )


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
    import json
    
    source_data = fetch_and_extract_source(url)
    
    # Return as JSON for the agent to parse and use with create_source
    return json.dumps(source_data, indent=2)


class WebsearchMiddleware(AgentMiddleware[AgentState, None]):
    """Middleware that provides web search and content fetching tools.
    
    Uses Tavily for discovery and httpx+markdownify for content retrieval.
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

