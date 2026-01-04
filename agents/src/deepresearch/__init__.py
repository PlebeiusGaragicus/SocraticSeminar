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

from src.shared.middleware.thinking import think_tool
from src.deepresearch.graph import graph, create_deepresearch_agent
from src.deepresearch.state import DeepResearchState, COST_PER_ITERATION_SATS

__all__ = [
    "graph",
    "create_deepresearch_agent",
    "DeepResearchState",
    "COST_PER_ITERATION_SATS",
    # Research tools (for external use)
    # Note: web search tools are now provided by WebsearchMiddleware
    "think_tool"
]
