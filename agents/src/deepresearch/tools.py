"""Research Tools for the DeepResearch agent.

Note: Web search and scraping tools are now provided by WebsearchMiddleware.
This module exports the think_tool for backward compatibility and sub-agent use.
"""

from src.shared.middleware.thinking import think_tool

# The RESEARCH_TOOLS list is now minimal since WebsearchMiddleware provides the main tools.
# Sub-agents should include WebsearchMiddleware in their middleware stack to get search tools.
RESEARCH_TOOLS = [think_tool]
