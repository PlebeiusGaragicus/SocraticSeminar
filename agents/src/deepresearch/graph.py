"""DeepResearch Agent using proper middleware composition.

Architecture:
- Uses create_agent() with explicit middleware stack (like DeepTutor)
- CashuPaymentMiddleware: Streaming micropayments with per-iteration deduction
- TodoListMiddleware: Task tracking for complex multi-step research
- ClarifyWithHumanMiddleware: Ask user for intent clarification
- ScratchFilesMiddleware: Agent working memory (visible to user, read-only)
- ClientToolsMiddleware: Client-side file operations via HITL interrupts
- HumanInTheLoopMiddleware: Approval for funding requests

The agent operates with:
1. Two file systems: User's project files (client) and agent scratch files (visible)
2. Streaming Cashu payments (deducted per LLM iteration)
3. HITL approval for write operations to user files
4. Clarification tools when user intent is unclear
5. Research tools: tavily_search, fetch_webpage, think_tool
6. Sub-agent delegation for parallel research
"""

import os
from datetime import datetime
from typing import Any

from langchain.agents import create_agent
from langchain.agents.middleware import HumanInTheLoopMiddleware, TodoListMiddleware
from langchain.agents.middleware.types import AgentMiddleware
from langchain_openai import ChatOpenAI
from langgraph.graph.state import CompiledStateGraph
from langgraph.types import Checkpointer

from deepagents.middleware.subagents import SubAgentMiddleware

from src.middleware import (
    CashuPaymentMiddleware, 
    ClarifyWithHumanMiddleware,
    ClientToolsMiddleware,
    # ScratchFilesMiddleware,
    WebsearchMiddleware,
    ThinkingMiddleware,
)

from .tools import RESEARCH_TOOLS, tavily_search, fetch_webpage, think_tool
from .prompts import get_research_system_prompt, RESEARCHER_INSTRUCTIONS
from .state import DeepResearchState, COST_PER_ITERATION_SATS


# =============================================================================
# CONFIGURATION
# =============================================================================

# LLM Configuration (OpenAI-compatible only)
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
    """Create the DeepResearch agent with proper middleware composition.
    
    Middleware Stack (in order):
    1. CashuPaymentMiddleware - Payment validation and per-iteration deduction
    2. TodoListMiddleware - Task tracking for complex research operations
    3. ClarifyWithHumanMiddleware - Ask user for intent clarification
    4. ScratchFilesMiddleware - Agent scratch files (visible to user, read-only)
    5. ClientToolsMiddleware - Client-side file operations via HITL interrupts
    6. SubAgentMiddleware - Parallel research delegation
    7. HumanInTheLoopMiddleware - Approval for funding requests
    
    The agent operates with TWO file systems:
    
    1. Scratch Files (via ScratchFilesMiddleware):
       - Paths: /scratch/notes.md, /scratch/analysis/, etc.
       - Agent can write freely without user approval
       - Stored in agent state (visible to frontend for transparency)
       - READ-ONLY from user's perspective
       - Used for intermediate analysis, drafts, working memory
    
    2. User Files (via ClientToolsMiddleware):
       - User's project files stored in browser
       - Write operations require HITL approval
       - Used for: final reports, user documents
    
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
    
    # Build middleware stack
    #
    # NOTE: ClientToolsMiddleware handles ALL client file tool interrupts including approval.
    # Write operations (write_file, edit_file) have requires_approval=True which the
    # frontend uses to show approval UI before executing locally.
    # 
    # ScratchFilesMiddleware allows the agent to write freely to /scratch/ space.
    # These files are stored in state and visible to the frontend for transparency.
    #
    middleware: list[AgentMiddleware] = []
    
    # 1. Payment middleware (optional) - validates token, tracks balance, deducts per iteration
    if include_payment:
        middleware.append(CashuPaymentMiddleware(cost_per_iteration=cost_per_iteration))
    
    # 2. Todo list - task tracking for complex multi-step research
    middleware.append(TodoListMiddleware())
    
    # 3. Clarification tools - ask user for intent clarification
    middleware.append(ClarifyWithHumanMiddleware())
    
    # 4. Scratch files - agent working memory stored in state (visible to user, read-only)
    #    Agent can write to /scratch/ freely without approval
    #    Frontend can display these files for transparency
    # middleware.append(ScratchFilesMiddleware())
    
    # 5. Client tools - ALL client file operations interrupt for client-side execution
    #    Write tools include requires_approval=True for frontend approval UI
    middleware.append(ClientToolsMiddleware())

    # 6. Web Search - URL discovery and content fetching
    middleware.append(WebsearchMiddleware())

    # 7. Thinking - Strategic reflection
    middleware.append(ThinkingMiddleware())
    
    # 8. Sub-agent middleware (optional) - for parallel research delegation
    if include_subagents:
        subagent_config = create_research_subagent_config()
        middleware.append(
            SubAgentMiddleware(
                default_model=model,
                default_tools=RESEARCH_TOOLS,
                subagents=[subagent_config],
                default_middleware=[
                    TodoListMiddleware(),
                    # ScratchFilesMiddleware(),  # Sub-agents also use scratch files
                    ThinkingMiddleware(),      # Sub-agents also think
                ],
                general_purpose_agent=False,  # Research-specific sub-agent
            )
        )
    
    # 9. Human-in-the-loop - ONLY for payment funding requests
    #    Client file operations are handled by ClientToolsMiddleware above
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
    
    # Create the agent using create_agent (not create_deep_agent)
    # This gives us full control over the middleware stack
    agent = create_agent(
        model,
        system_prompt=system_prompt,
        tools=[],  # Tools provided by middleware (WebsearchMiddleware, ThinkingMiddleware, etc.)
        middleware=middleware,
        checkpointer=checkpointer,
        debug=debug,
    )
    
    return agent


# =============================================================================
# GRAPH EXPORT
# =============================================================================

# Default graph for LangGraph deployment
# Uses in-memory checkpointing; production should use persistent checkpointer
graph = create_deepresearch_agent()
