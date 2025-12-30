"""Research Tools for the DeepResearch agent.

This module now primarily exports tools from the shared websearch and thinking middlewares.
"""

from src.middleware.websearch import tavily_search, fetch_webpage, fetch_webpage_content
from src.middleware.thinking import think_tool

# Export all tools for backward compatibility if needed, 
# but agents should prefer using the middlewares directly.
RESEARCH_TOOLS = [tavily_search, fetch_webpage, think_tool]
