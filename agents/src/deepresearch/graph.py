"""DeepResearch Agent using deepagent middleware and shared payment middleware.

Architecture:
- Uses create_deep_agent() for built-in filesystem, todo, and subagent support
- Adds CashuPaymentMiddleware for streaming micropayments
- Adds ClarifyWithHumanMiddleware for user clarification
- Research tools: tavily_search, fetch_webpage, think_tool

The agent conducts thorough web research:
1. Plans research with todo list
2. Searches the web using Tavily
3. Fetches full webpage content
4. Saves findings to files
5. Generates comprehensive research reports
"""

import os
from datetime import datetime
from typing import Any

from langchain.agents.middleware import HumanInTheLoopMiddleware
from langchain.agents.middleware.types import AgentMiddleware
from langchain_openai import ChatOpenAI
from langgraph.graph.state import CompiledStateGraph
from langgraph.types import Checkpointer

from deepagents import create_deep_agent
from deepagents.backends import StateBackend

from src.middleware import CashuPaymentMiddleware, ClarifyWithHumanMiddleware

from .tools import RESEARCH_TOOLS, tavily_search, fetch_webpage, think_tool
from .prompts import get_research_system_prompt, RESEARCHER_INSTRUCTIONS
from .state import DeepResearchState, COST_PER_ITERATION_SATS


# =============================================================================
# CONFIGURATION
# =============================================================================

# LLM Configuration (OpenAI-compatible only, matching deeptutor)
LLM_MODEL = os.getenv("LLM_MODEL", "gpt-4o")
LLM_BASE_URL = os.getenv("LLM_BASE_URL")  # Optional: for OpenAI-compatible endpoints
LLM_API_KEY = os.getenv("LLM_API_KEY", os.getenv("OPENAI_API_KEY", ""))

LLM_PROVIDER = os.getenv("LLM_PROVIDER", "openai")  # "openai" or "anthropic"
LLM_MODEL = os.getenv("LLM_MODEL", "gpt-4o")
LLM_BASE_URL = os.getenv("LLM_BASE_URL")  # Optional: for OpenAI-compatible endpoints
LLM_API_KEY = os.getenv("LLM_API_KEY", os.getenv("OPENAI_API_KEY", ""))


# Research Configuration
MAX_CONCURRENT_RESEARCH_UNITS = int(os.getenv("MAX_CONCURRENT_RESEARCH_UNITS", "3"))
MAX_RESEARCHER_ITERATIONS = int(os.getenv("MAX_RESEARCHER_ITERATIONS", "3"))

# Payment Configuration
PAYMENT_COST_PER_ITERATION = int(os.getenv("COST_PER_ITERATION_SATS", str(COST_PER_ITERATION_SATS)))


# =============================================================================
# MODEL FACTORY
# =============================================================================

def get_model():
    """Get the configured chat model.
    
    Supports:
    - OpenAI (default): gpt-4o, gpt-4-turbo, etc.
    - OpenAI-compatible: Any endpoint with LLM_BASE_URL
    """
    kwargs = {
        "model": LLM_MODEL,
        "temperature": 0.0,
    }
    if LLM_BASE_URL:
        kwargs["base_url"] = LLM_BASE_URL
    if LLM_API_KEY:
        kwargs["api_key"] = LLM_API_KEY
    
    return ChatOpenAI(**kwargs)


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
        "tools": [tavily_search, fetch_webpage, think_tool],
    }


# =============================================================================
# AGENT FACTORY
# =============================================================================

def create_deepresearch_agent(
    *,
    checkpointer: Checkpointer | None = None,
    cost_per_iteration: int = PAYMENT_COST_PER_ITERATION,
    additional_middleware: list[AgentMiddleware] | None = None,
    include_payment: bool = True,
    include_subagents: bool = True,
    debug: bool = False,
) -> CompiledStateGraph:
    """Create the DeepResearch agent with all middleware.
    
    This agent uses create_deep_agent() from the deepagents package which provides:
    - FilesystemMiddleware: Server-side file storage for research notes/reports
    - TodoListMiddleware: Task planning and tracking
    - SubAgentMiddleware: Parallel research delegation
    - SummarizationMiddleware: Context management for long research sessions
    
    Additional middleware:
    - CashuPaymentMiddleware: Streaming micropayments (optional)
    - ClarifyWithHumanMiddleware: Ask user for clarification
    - HumanInTheLoopMiddleware: Approval for sensitive operations
    
    Args:
        checkpointer: Optional checkpointer for persistence
        cost_per_iteration: Satoshis per LLM iteration (default: 10)
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
            cost_per_iteration=10,
        )
        
        # Start a research session
        result = await agent.ainvoke({
            "messages": [HumanMessage(content="Research the history of Bitcoin")],
            "payment_token": "cashuA...",
        })
        ```
    """
    model = get_model()
    
    # Build system prompt
    system_prompt = get_research_system_prompt(
        include_workflow=True,
        include_subagent_instructions=include_subagents,
        max_concurrent_research_units=MAX_CONCURRENT_RESEARCH_UNITS,
        max_researcher_iterations=MAX_RESEARCHER_ITERATIONS,
    )
    
    # Build additional middleware stack
    middleware: list[AgentMiddleware] = []
    
    # Payment middleware (optional)
    if include_payment:
        middleware.append(CashuPaymentMiddleware(cost_per_iteration=cost_per_iteration))
    
    # Clarification tools
    middleware.append(ClarifyWithHumanMiddleware())
    
    # Human-in-the-loop for funding requests
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
    
    # Create sub-agents for parallel research
    subagents = []
    if include_subagents:
        subagents.append(create_research_subagent_config())
    
    # Create the deep agent using deepagents package
    # This provides: FilesystemMiddleware, TodoListMiddleware, SubAgentMiddleware
    agent = create_deep_agent(
        model=model,
        tools=RESEARCH_TOOLS,
        system_prompt=system_prompt,
        middleware=middleware,
        subagents=subagents if subagents else None,
        checkpointer=checkpointer,
        backend=StateBackend,  # Use state-based file storage
        debug=debug,
    )
    
    return agent


# =============================================================================
# GRAPH EXPORT
# =============================================================================

# Default graph for LangGraph deployment
# Uses in-memory checkpointing; production should use persistent checkpointer
graph = create_deepresearch_agent()

