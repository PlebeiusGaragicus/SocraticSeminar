"""DeepResearch Agent - Conducts thorough web research with file output.

This agent uses the deepagents package for filesystem, todo, and subagent support,
combined with shared payment middleware for Cashu micropayments.

Usage:
    from deepresearch import graph
    
    result = await graph.ainvoke({
        "messages": [HumanMessage(content="Research the history of Bitcoin")],
        "payment_token": "cashuA...",
    })
"""

from .graph import graph, create_deepresearch_agent
from src.middleware.websearch import tavily_search, fetch_webpage
from src.middleware.thinking import think_tool
from src.deepresearch.tools import RESEARCH_TOOLS
from src.deepresearch.state import DeepResearchState

__all__ = [
    "graph",
    "create_deepresearch_agent",
    "tavily_search",
    "fetch_webpage",
    "think_tool",
    "RESEARCH_TOOLS",
    "DeepResearchState",
]
