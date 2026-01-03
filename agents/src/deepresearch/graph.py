"""DeepResearch Agent using proper middleware composition.

Architecture:
- Uses create_agent() with explicit middleware stack (like DeepTutor)
- CashuPaymentMiddleware: Streaming micropayments with per-iteration deduction
- TodoListMiddleware: Task tracking for complex multi-step research
- ClarifyWithHumanMiddleware: Ask user for intent clarification
- ClientToolsMiddleware: Client-side file operations via HITL interrupts
- SourcesMiddleware: Access to project sources
- WebsearchMiddleware: Web search (Tavily) and URL scraping (Firecrawl)
- HumanInTheLoopMiddleware: Approval for funding requests

The agent operates with:
1. Two file systems: User's project files (client) and agent scratch files (visible)
2. Streaming Cashu payments (deducted per LLM iteration)
3. HITL approval for write operations to user files and URL scraping
4. Clarification tools when user intent is unclear
5. Research tools: web_search, scrape_url, fetch_webpage, think_tool
6. Sub-agent delegation for parallel research
"""

import os
from datetime import datetime
from typing import Any

from langchain.agents import create_agent
from langchain.agents.middleware import HumanInTheLoopMiddleware, TodoListMiddleware
from langchain.agents.middleware.types import AgentMiddleware
from langgraph.graph.state import CompiledStateGraph
from langgraph.types import Checkpointer

from deepagents.middleware.subagents import SubAgentMiddleware

from src.shared.models import get_model
from src.shared.config import DEEPRESEARCH_CONFIG
from src.shared.middleware import (
    CashuPaymentMiddleware, 
    ClarifyWithHumanMiddleware,
    ClientToolsMiddleware,
    SourcesMiddleware,
    WebsearchMiddleware,
    ThinkingMiddleware,
    ToolValidationMiddleware,
)
from src.shared.middleware.thinking import think_tool

from src.deepresearch.behaviour import BehaviouralMiddleware
from src.deepresearch.tools import RESEARCH_TOOLS
from src.deepresearch.prompts import get_research_system_prompt, RESEARCHER_INSTRUCTIONS


# =============================================================================
# CONFIGURATION (from shared config)
# =============================================================================

MAX_CONCURRENT_RESEARCH_UNITS = DEEPRESEARCH_CONFIG.settings.get(
    "max_concurrent_research_units",
    int(os.getenv("MAX_CONCURRENT_RESEARCH_UNITS", "3"))
)
MAX_RESEARCHER_ITERATIONS = DEEPRESEARCH_CONFIG.settings.get(
    "max_researcher_iterations", 
    int(os.getenv("MAX_RESEARCHER_ITERATIONS", "3"))
)


# =============================================================================
# RESEARCH SUB-AGENT
# =============================================================================

def create_research_subagent_config() -> dict[str, Any]:
    """Create the configuration for the research sub-agent.
    
    This sub-agent is used for parallel research tasks when the main agent
    delegates work.
    """
    current_date = datetime.now().strftime("%Y-%m-%d")
    
    return {
        "name": "research-agent",
        "description": "Delegate research to the sub-agent researcher. Only give this researcher one topic at a time.",
        "system_prompt": RESEARCHER_INSTRUCTIONS.format(date=current_date),
        "tools": [think_tool],  # Web tools provided by WebsearchMiddleware
    }


# =============================================================================
# AGENT FACTORY
# =============================================================================

def create_deepresearch_agent(
    *,
    checkpointer: Checkpointer | None = None,
    cost_per_iteration: int | None = None,
    additional_middleware: list[AgentMiddleware] | None = None,
    include_payment: bool = True,
    include_subagents: bool = True,
    debug: bool = False,
) -> CompiledStateGraph:
    """Create the DeepResearch agent with proper middleware composition.
    
    Middleware Stack (in order):
    1. CashuPaymentMiddleware - Payment validation and per-iteration deduction
    2. ToolValidationMiddleware - Catch and correct malformed tool calls
    3. BehaviouralMiddleware - Agent character and personality
    4. TodoListMiddleware - Task tracking for complex research operations
    5. ClarifyWithHumanMiddleware - Ask user for intent clarification
    6. ClientToolsMiddleware - Client-side file operations via HITL interrupts
    7. SourcesMiddleware - Access to project sources (auto-approved)
    8. WebsearchMiddleware - Web search and content fetching
    9. ThinkingMiddleware - Strategic reflection
    10. SubAgentMiddleware - Parallel research delegation
    11. HumanInTheLoopMiddleware - Approval for funding requests
    
    Args:
        checkpointer: Optional checkpointer for persistence
        cost_per_iteration: Override cost per iteration (default: from DEEPRESEARCH_CONFIG)
        additional_middleware: Extra middleware to add
        include_payment: Whether to include payment middleware (default: True)
        include_subagents: Whether to include research sub-agents (default: True)
        debug: Enable debug logging
        
    Returns:
        Compiled agent graph ready for invoke/stream
        
    Example:
        ```python
        from langgraph.checkpoint.memory import MemorySaver
        
        agent = create_deepresearch_agent(
            checkpointer=MemorySaver(),
            cost_per_iteration=15,
        )
        
        # Start a research session
        result = await agent.ainvoke({
            "messages": [HumanMessage(content="Research the history of Bitcoin")],
            "payment_token": "cashuA...",
            # Optional: client can override cost
            "payment_cost_per_iteration": 20,
        })
        ```
    """
    model = get_model(temperature=0.0)
    
    # Get effective cost per iteration
    # Priority: function arg > env var > agent config default
    effective_cost = DEEPRESEARCH_CONFIG.get_cost_per_iteration(cost_per_iteration)
    
    # Build system prompt
    system_prompt = get_research_system_prompt(
        include_workflow=True,
        include_subagent_instructions=include_subagents,
        max_concurrent_research_units=MAX_CONCURRENT_RESEARCH_UNITS,
        max_researcher_iterations=MAX_RESEARCHER_ITERATIONS,
    )
    
    # Build middleware stack
    middleware: list[AgentMiddleware] = []
    
    # 1. Payment middleware (optional)
    if include_payment:
        middleware.append(CashuPaymentMiddleware(cost_per_iteration=effective_cost))
    
    # 2. Tool Validation - catch and correct malformed tool calls immediately
    middleware.append(ToolValidationMiddleware())
    
    # 3. Behavioural - control the agent's character and personality
    middleware.append(BehaviouralMiddleware())
    
    # 4. Todo list - task tracking for complex multi-step research
    middleware.append(TodoListMiddleware())
    
    # 5. Clarification tools - ask user for intent clarification
    middleware.append(ClarifyWithHumanMiddleware())

    # 6. Client tools - ALL client file operations interrupt for client-side execution
    middleware.append(ClientToolsMiddleware())

    # 7. Sources - Access to project sources (auto-approved, no HITL)
    middleware.append(SourcesMiddleware())

    # 8. Web Search - URL discovery and content fetching
    middleware.append(WebsearchMiddleware())

    # 9. Thinking - Strategic reflection
    middleware.append(ThinkingMiddleware())
    
    # 10. Sub-agent middleware (optional) - for parallel research delegation
    if include_subagents:
        subagent_config = create_research_subagent_config()
        middleware.append(
            SubAgentMiddleware(
                default_model=model,
                default_tools=RESEARCH_TOOLS,
                subagents=[subagent_config],
                default_middleware=[
                    ToolValidationMiddleware(),
                    TodoListMiddleware(),
                    WebsearchMiddleware(),  # Provides web_search, scrape_url, fetch_webpage
                    ThinkingMiddleware(),
                ],
                general_purpose_agent=False,
            )
        )

    # 11. Human-in-the-loop - ONLY for payment funding requests
    if include_payment:
        middleware.append(
            HumanInTheLoopMiddleware(
                interrupt_on={
                    "request_additional_funding": True,
                }
            )
        )
    
    # Add any additional middleware
    if additional_middleware:
        middleware.extend(additional_middleware)
    
    # Create the agent
    agent = create_agent(
        model,
        system_prompt=system_prompt,
        tools=[],  # Tools provided by middleware
        middleware=middleware,
        checkpointer=checkpointer,
        debug=debug
    )
    
    return agent


# =============================================================================
# GRAPH EXPORT
# =============================================================================

# Default graph for LangGraph deployment
graph = create_deepresearch_agent()
