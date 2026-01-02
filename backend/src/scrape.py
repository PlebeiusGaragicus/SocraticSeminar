"""
Web scraping service for Socratic Seminar.

Provides centralized URL scraping endpoints that:
- Fetch webpage content and convert to markdown
- Extract bibliography metadata (author, title, date, publisher)
- Return structured data for source creation

Used by both the frontend and agent middleware for consistent scraping.
"""

import asyncio
import logging
import re
import time
from typing import Optional
from urllib.parse import urlparse

import httpx
from fastapi import APIRouter, HTTPException
from markdownify import markdownify
from pydantic import BaseModel, HttpUrl

# Configure logging
logger = logging.getLogger("scrape")
logger.setLevel(logging.INFO)

if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter(
        "[%(asctime)s] %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    ))
    logger.addHandler(handler)


# =============================================================================
# REQUEST/RESPONSE MODELS
# =============================================================================

class ScrapeRequest(BaseModel):
    """Request to scrape a single URL."""
    url: HttpUrl
    timeout: float = 15.0


class BatchScrapeRequest(BaseModel):
    """Request to scrape multiple URLs."""
    urls: list[HttpUrl]
    timeout: float = 15.0


class Bibliography(BaseModel):
    """Bibliography metadata for citation purposes."""
    author: Optional[str] = None
    title: Optional[str] = None
    publishedDate: Optional[str] = None
    publisher: Optional[str] = None
    resourceType: Optional[str] = None


class ScrapedResponse(BaseModel):
    """Response containing scraped content and metadata."""
    url: str
    title: str
    content: str  # Markdown
    bibliography: Bibliography
    scraped_at: int  # Unix timestamp in milliseconds


class BatchScrapedResponse(BaseModel):
    """Response for batch scraping."""
    results: list[ScrapedResponse]
    errors: list[dict]  # {url: str, error: str}


# =============================================================================
# SCRAPING LOGIC
# =============================================================================

# User agent to mimic a real browser
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)


def _extract_meta_content(html: str, *names: str) -> Optional[str]:
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
    # Author - try various meta tag formats
    author = _extract_meta_content(
        html,
        "author", "article:author", "og:author", 
        "twitter:creator", "dc.creator", "citation_author"
    )
    
    # Title
    title = _extract_title(html)
    
    # Published date
    published_date = _extract_meta_content(
        html,
        "article:published_time", "og:published_time",
        "publication_date", "date", "dc.date",
        "citation_publication_date", "datePublished"
    )
    
    # Publisher/site name
    publisher = _extract_meta_content(
        html,
        "og:site_name", "publisher", "dc.publisher",
        "citation_journal_title", "application-name"
    )
    if not publisher:
        # Extract domain as fallback publisher
        domain = urlparse(url).netloc
        if domain:
            # Remove www. prefix if present
            domain = re.sub(r'^www\.', '', domain)
            publisher = domain
    
    # Resource type
    resource_type = _extract_meta_content(
        html,
        "og:type", "dc.type", "citation_type"
    )
    if resource_type:
        resource_type = resource_type.capitalize()
    else:
        resource_type = "Article"  # Default
    
    return Bibliography(
        author=author,
        title=title if title != "Untitled" else None,
        publishedDate=published_date,
        publisher=publisher,
        resourceType=resource_type
    )


def _html_to_markdown(html: str) -> str:
    """Convert HTML to clean markdown."""
    # Remove script and style elements first
    cleaned = re.sub(r'<script[^>]*>[\s\S]*?</script>', '', html, flags=re.IGNORECASE)
    cleaned = re.sub(r'<style[^>]*>[\s\S]*?</style>', '', cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r'<noscript[^>]*>[\s\S]*?</noscript>', '', cleaned, flags=re.IGNORECASE)
    
    # Convert to markdown
    markdown = markdownify(cleaned, heading_style="ATX", strip=['script', 'style'])
    
    # Clean up excessive whitespace
    markdown = re.sub(r'\n{3,}', '\n\n', markdown)
    markdown = markdown.strip()
    
    return markdown


async def scrape_url(url: str, timeout: float = 15.0) -> ScrapedResponse:
    """Fetch and scrape a single URL."""
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
    }
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(
                str(url),
                headers=headers,
                timeout=timeout,
                follow_redirects=True
            )
            response.raise_for_status()
            html = response.text
        except httpx.TimeoutException:
            raise HTTPException(
                status_code=504,
                detail=f"Timeout fetching URL: {url}"
            )
        except httpx.HTTPStatusError as e:
            raise HTTPException(
                status_code=e.response.status_code,
                detail=f"HTTP error fetching URL: {url} - {e.response.status_code}"
            )
        except Exception as e:
            raise HTTPException(
                status_code=502,
                detail=f"Error fetching URL: {url} - {str(e)}"
            )
    
    # Extract metadata
    title = _extract_title(html)
    bibliography = _extract_bibliography(html, str(url))
    
    # Convert to markdown
    content = _html_to_markdown(html)
    
    # Truncate if too long (avoid massive responses)
    if len(content) > 50000:
        content = content[:50000] + "\n\n... [content truncated due to length] ..."
    
    return ScrapedResponse(
        url=str(url),
        title=title,
        content=content,
        bibliography=bibliography,
        scraped_at=int(time.time() * 1000)  # Unix timestamp in ms
    )


async def scrape_urls_batch(
    urls: list[str],
    timeout: float = 15.0
) -> BatchScrapedResponse:
    """Scrape multiple URLs in parallel."""
    results: list[ScrapedResponse] = []
    errors: list[dict] = []
    
    async def scrape_one(url: str):
        try:
            result = await scrape_url(url, timeout)
            results.append(result)
        except HTTPException as e:
            errors.append({"url": url, "error": e.detail})
        except Exception as e:
            errors.append({"url": url, "error": str(e)})
    
    # Run all scrapes concurrently with a semaphore to limit parallelism
    semaphore = asyncio.Semaphore(5)  # Max 5 concurrent requests
    
    async def scrape_with_semaphore(url: str):
        async with semaphore:
            await scrape_one(url)
    
    await asyncio.gather(*[scrape_with_semaphore(str(url)) for url in urls])
    
    return BatchScrapedResponse(results=results, errors=errors)


# =============================================================================
# API ROUTER
# =============================================================================

scrape_router = APIRouter()


@scrape_router.post("/", response_model=ScrapedResponse)
async def scrape_single_url(request: ScrapeRequest):
    """
    Scrape a single URL and return structured content.
    
    Returns:
        - url: The original URL
        - title: Page title extracted from og:title or <title>
        - content: Page content converted to Markdown
        - bibliography: Extracted metadata (author, date, publisher, etc.)
        - scraped_at: Unix timestamp in milliseconds
    """
    logger.info(f"Scraping URL: {request.url}")
    result = await scrape_url(str(request.url), request.timeout)
    logger.info(f"Successfully scraped: {result.title}")
    return result


@scrape_router.post("/batch", response_model=BatchScrapedResponse)
async def scrape_multiple_urls(request: BatchScrapeRequest):
    """
    Scrape multiple URLs in parallel.
    
    Returns:
        - results: List of successfully scraped responses
        - errors: List of {url, error} for failed URLs
    """
    logger.info(f"Batch scraping {len(request.urls)} URLs")
    result = await scrape_urls_batch(
        [str(url) for url in request.urls],
        request.timeout
    )
    logger.info(
        f"Batch complete: {len(result.results)} success, {len(result.errors)} errors"
    )
    return result


@scrape_router.get("/health")
async def scrape_health():
    """Health check for scrape service."""
    return {"status": "healthy", "service": "scrape"}

