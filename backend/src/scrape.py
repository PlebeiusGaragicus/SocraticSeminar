"""
Web scraping service for Socratic Seminar.

Provides centralized URL scraping endpoints that:
- Fetch webpage content and convert to markdown
- Generate PDF preview of the webpage
- Extract bibliography metadata (author, title, date, publisher)
- Return structured data for source creation

Used by both the frontend and agent middleware for consistent scraping.
"""

import asyncio
import base64
import io
import logging
import os
import re
import time
from enum import Enum
from typing import Literal, Optional
from urllib.parse import urlparse

import httpx
from fastapi import APIRouter, HTTPException
from markdownify import markdownify
from pydantic import BaseModel, HttpUrl


class ContentMethod(str, Enum):
    """Method for extracting markdown content from a URL."""
    MARKDOWNIFY = "markdownify"  # Built-in markdownify
    FIRECRAWL = "firecrawl"      # Firecrawl API

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
    generate_pdf: bool = True  # Whether to generate PDF preview
    method: ContentMethod = ContentMethod.MARKDOWNIFY  # Content extraction method


class BatchScrapeRequest(BaseModel):
    """Request to scrape multiple URLs."""
    urls: list[HttpUrl]
    timeout: float = 15.0
    generate_pdf: bool = True


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
    # PDF preview fields
    preview_pdf: Optional[str] = None  # Base64-encoded PDF
    preview_error: Optional[str] = None  # Error message if PDF generation failed


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


# Firecrawl API key from environment
FIRECRAWL_API_KEY = os.environ.get("FIRECRAWL_API_KEY", "")
FIRECRAWL_API_URL = "https://api.firecrawl.dev/v1/scrape"


async def _scrape_with_firecrawl(url: str, timeout: float = 30.0) -> tuple[str, str, str]:
    """
    Scrape URL using Firecrawl API.
    
    Returns:
        Tuple of (markdown_content, title, html_content)
    """
    if not FIRECRAWL_API_KEY:
        raise HTTPException(
            status_code=503,
            detail="Firecrawl API key not configured. Set FIRECRAWL_API_KEY environment variable."
        )
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                FIRECRAWL_API_URL,
                headers={
                    "Authorization": f"Bearer {FIRECRAWL_API_KEY}",
                    "Content-Type": "application/json"
                },
                json={
                    "url": url,
                    "formats": ["markdown", "html"],
                    "onlyMainContent": True
                },
                timeout=timeout
            )
            response.raise_for_status()
            data = response.json()
            
            if not data.get("success"):
                raise HTTPException(
                    status_code=502,
                    detail=f"Firecrawl failed: {data.get('error', 'Unknown error')}"
                )
            
            result = data.get("data", {})
            markdown = result.get("markdown", "")
            html = result.get("html", "")
            metadata = result.get("metadata", {})
            title = metadata.get("title") or metadata.get("ogTitle") or "Untitled"
            
            return markdown, title, html
            
        except httpx.TimeoutException:
            raise HTTPException(
                status_code=504,
                detail=f"Firecrawl timeout for URL: {url}"
            )
        except httpx.HTTPStatusError as e:
            raise HTTPException(
                status_code=e.response.status_code,
                detail=f"Firecrawl error: {e.response.status_code}"
            )
        except Exception as e:
            raise HTTPException(
                status_code=502,
                detail=f"Firecrawl error: {str(e)}"
            )


def _generate_pdf_from_html(html: str, base_url: str) -> tuple[Optional[bytes], Optional[str]]:
    """
    Generate PDF from HTML using WeasyPrint.
    
    Returns:
        Tuple of (pdf_bytes, error_message)
        If successful, pdf_bytes contains the PDF and error_message is None.
        If failed, pdf_bytes is None and error_message contains the error.
    """
    try:
        from weasyprint import HTML, CSS
        from weasyprint.text.fonts import FontConfiguration
        
        # Configure fonts
        font_config = FontConfiguration()
        
        # Add base tag if not present for relative URLs
        if '<base' not in html.lower():
            # Insert base tag after <head>
            head_match = re.search(r'<head[^>]*>', html, re.IGNORECASE)
            if head_match:
                insert_pos = head_match.end()
                html = html[:insert_pos] + f'<base href="{base_url}">' + html[insert_pos:]
        
        # Create PDF with print-friendly CSS
        print_css = CSS(string="""
            @page {
                size: A4;
                margin: 1.5cm;
            }
            body {
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
                font-size: 11pt;
                line-height: 1.5;
                color: #333;
            }
            img {
                max-width: 100%;
                height: auto;
            }
            a {
                color: #0066cc;
            }
            nav, footer, aside, .sidebar, .comments, .ad, .advertisement {
                display: none !important;
            }
        """, font_config=font_config)
        
        # Generate PDF
        html_doc = HTML(string=html, base_url=base_url)
        pdf_buffer = io.BytesIO()
        html_doc.write_pdf(pdf_buffer, stylesheets=[print_css], font_config=font_config)
        
        return pdf_buffer.getvalue(), None
        
    except ImportError as e:
        logger.warning(f"WeasyPrint not available: {e}")
        return None, "PDF generation not available (WeasyPrint not installed)"
    except Exception as e:
        logger.warning(f"PDF generation failed: {e}")
        return None, f"PDF generation failed: {str(e)}"


async def scrape_url(
    url: str,
    timeout: float = 15.0,
    generate_pdf: bool = True,
    method: ContentMethod = ContentMethod.MARKDOWNIFY
) -> ScrapedResponse:
    """Fetch and scrape a single URL."""
    
    # Use Firecrawl if requested
    if method == ContentMethod.FIRECRAWL:
        logger.info(f"Using Firecrawl for: {url}")
        content, title, html = await _scrape_with_firecrawl(url, timeout=30.0)
        bibliography = _extract_bibliography(html, str(url)) if html else Bibliography()
    else:
        # Default: fetch with httpx and convert with markdownify
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
                    timeout=httpx.Timeout(timeout, connect=10.0),
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
    
    # Generate PDF preview
    preview_pdf_base64: Optional[str] = None
    preview_error: Optional[str] = None
    
    if generate_pdf:
        # Run PDF generation with timeout to prevent hanging on slow external resources
        try:
            loop = asyncio.get_event_loop()
            pdf_bytes, pdf_error = await asyncio.wait_for(
                loop.run_in_executor(None, _generate_pdf_from_html, html, str(url)),
                timeout=30.0  # 30 second timeout for PDF generation
            )
        except asyncio.TimeoutError:
            pdf_bytes, pdf_error = None, "PDF generation timed out (external resources slow)"
        if pdf_bytes:
            preview_pdf_base64 = base64.b64encode(pdf_bytes).decode('utf-8')
            logger.info(f"Generated PDF preview ({len(pdf_bytes)} bytes)")
        else:
            preview_error = pdf_error
            logger.warning(f"PDF preview failed: {pdf_error}")
    
    return ScrapedResponse(
        url=str(url),
        title=title,
        content=content,
        bibliography=bibliography,
        scraped_at=int(time.time() * 1000),  # Unix timestamp in ms
        preview_pdf=preview_pdf_base64,
        preview_error=preview_error
    )


async def scrape_urls_batch(
    urls: list[str],
    timeout: float = 15.0,
    generate_pdf: bool = True
) -> BatchScrapedResponse:
    """Scrape multiple URLs in parallel."""
    results: list[ScrapedResponse] = []
    errors: list[dict] = []
    
    async def scrape_one(url: str):
        try:
            result = await scrape_url(url, timeout, generate_pdf)
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
    
    Args:
        - url: The URL to scrape
        - timeout: Request timeout in seconds (default: 15.0)
        - generate_pdf: Whether to generate PDF preview (default: true)
        - method: Content extraction method - 'markdownify' or 'firecrawl'
    
    Returns:
        - url: The original URL
        - title: Page title extracted from og:title or <title>
        - content: Page content converted to Markdown
        - bibliography: Extracted metadata (author, date, publisher, etc.)
        - scraped_at: Unix timestamp in milliseconds
        - preview_pdf: Base64-encoded PDF of the page (if generate_pdf=true)
        - preview_error: Error message if PDF generation failed
    """
    logger.info(f"Scraping URL: {request.url} (PDF: {request.generate_pdf}, Method: {request.method.value})")
    result = await scrape_url(
        str(request.url),
        request.timeout,
        request.generate_pdf,
        request.method
    )
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
    logger.info(f"Batch scraping {len(request.urls)} URLs (PDF: {request.generate_pdf})")
    result = await scrape_urls_batch(
        [str(url) for url in request.urls],
        request.timeout,
        request.generate_pdf
    )
    logger.info(
        f"Batch complete: {len(result.results)} success, {len(result.errors)} errors"
    )
    return result


@scrape_router.get("/health")
async def scrape_health():
    """Health check for scrape service."""
    return {"status": "healthy", "service": "scrape"}
