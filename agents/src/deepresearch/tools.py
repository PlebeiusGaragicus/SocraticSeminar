"""Research Tools for the DeepResearch agent.

This module now primarily exports tools from the shared websearch and thinking middlewares.
"""

from src.shared.middleware.websearch import (
    tavily_search,
    fetch_webpage,
    fetch_webpage_content,
    scrape_url_to_source,
    fetch_and_extract_source,
)
from src.shared.middleware.thinking import think_tool

# Export all tools for backward compatibility if needed, 
# but agents should prefer using the middlewares directly.
RESEARCH_TOOLS = [tavily_search, fetch_webpage, scrape_url_to_source, think_tool]
