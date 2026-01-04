"""DeepResearch Agent using middleware composition.

Architecture:
This is the single production agent for the Socratic Seminar project.
Uses create_agent() with an explicit middleware stack for modularity.

Middleware Stack (in order):
1. CashuPaymentMiddleware - Payment validation (TBD - not fully implemented)
2. ToolValidationMiddleware - Catch and correct malformed tool calls
3. BehaviouralMiddleware - Agent character and personality (prompt-only)
4. TodoListMiddleware - Task tracking pseudo-tool
5. ThinkingMiddleware - Strategic reflection pseudo-tool
6. ClarifyWithHumanMiddleware - HITL for ask_user, ask_choices
7. ClientToolsMiddleware - Client-side file operations (HITL for patch_file only)
8. SourcesMiddleware - Access to project sources (list returns from state)
9. WebsearchMiddleware - Web search and scraping (HITL for scrape_url)
10. SubAgentMiddleware - Parallel research delegation (optional, disabled by default)

The agent operates with:
1. A file system: The user's project files (stored client-side in browser)
2. Streaming Cashu payments (TBD - deducted per LLM iteration)
3. HITL approval for: patch_file, scrape_url, ask_user, ask_choices
4. State injection: Client injects files_list and sources_list each invocation
5. Research tools: web_search, scrape_url, fetch_webpage, think_tool

Agent Settings (passed via RunnableConfig):
- llm_model: Pass via config={"configurable": {"llm_model": "grok-4-1-fast-non-reasoning"}}
- max_concurrent_research_units: 1-10
- max_researcher_iterations: 1-10
"""

import os
from datetime import datetime
from typing import Any

from langchain.agents import create_agent
from langchain.agents.middleware import TodoListMiddleware
from langchain.agents.middleware.types import AgentMiddleware
from langgraph.graph.state import CompiledStateGraph
from langgraph.types import Checkpointer

from src.shared.models import get_configurable_model
from src.shared.config import DEEPRESEARCH_CONFIG
from src.shared.state import AgentSettings, DEFAULT_AGENT_SETTINGS
from src.shared.middleware import (
    CashuPaymentMiddleware, 
    ClarifyWithHumanMiddleware,
    ClientToolsMiddleware,
    SourcesMiddleware,
    WebsearchMiddleware,
    ThinkingMiddleware,
    ToolValidationMiddleware,
)

from src.deepresearch.behaviour import BehaviouralMiddleware
from src.deepresearch.prompts import get_research_system_prompt, RESEARCHER_INSTRUCTIONS


# =============================================================================
# CONFIGURATION
# =============================================================================

# Default settings (can be overridden via UI per-thread)
DEFAULT_MAX_CONCURRENT_RESEARCH_UNITS = DEEPRESEARCH_CONFIG.settings.get(
    "max_concurrent_research_units",
    int(os.getenv("MAX_CONCURRENT_RESEARCH_UNITS", "3"))
)
DEFAULT_MAX_RESEARCHER_ITERATIONS = DEEPRESEARCH_CONFIG.settings.get(
    "max_researcher_iterations", 
    int(os.getenv("MAX_RESEARCHER_ITERATIONS", "3"))
)


def get_agent_settings_from_state(state: dict[str, Any]) -> AgentSettings:
    """Extract agent settings from state, with defaults.
    
    The frontend passes agent_settings in the input state for each request.
    This function extracts those settings with safe defaults.
    """
    settings = state.get("agent_settings", {}) or {}
    return {
        "llm_model": settings.get("llm_model", DEFAULT_AGENT_SETTINGS["llm_model"]),
        "max_concurrent_research_units": settings.get(
            "max_concurrent_research_units", 
            DEFAULT_MAX_CONCURRENT_RESEARCH_UNITS
        ),
        "max_researcher_iterations": settings.get(
            "max_researcher_iterations", 
            DEFAULT_MAX_RESEARCHER_ITERATIONS
        ),
    }


# =============================================================================
# RESEARCH SUB-AGENT (optional)
# =============================================================================

def create_research_subagent_config() -> dict[str, Any]:
    """Create the configuration for the research sub-agent.
    
    This sub-agent is used for parallel research tasks when the main agent
    delegates work. Currently disabled by default until SubAgentMiddleware
    spec is finalized.
    """
    current_date = datetime.now().strftime("%Y-%m-%d")
    
    return {
        "name": "research-agent",
        "description": "Delegate research to the sub-agent researcher. Only give this researcher one topic at a time.",
        "system_prompt": RESEARCHER_INSTRUCTIONS.format(date=current_date),
        # Note: SubAgentMiddleware provides its own tools from middleware
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
    include_subagents: bool = False,  # Disabled by default until spec finalized
    max_concurrent_research_units: int | None = None,
    max_researcher_iterations: int | None = None,
    debug: bool = False,
) -> CompiledStateGraph:
    """Create the DeepResearch agent with proper middleware composition.
    
    Middleware Stack (in order):
    1. CashuPaymentMiddleware - Payment validation (TBD)
    2. ToolValidationMiddleware - Catch and correct malformed tool calls
    3. BehaviouralMiddleware - Agent character and personality (prompt-only)
    4. TodoListMiddleware - Task tracking pseudo-tool
    5. ThinkingMiddleware - Strategic reflection pseudo-tool
    6. ClarifyWithHumanMiddleware - HITL for ask_user, ask_choices
    7. ClientToolsMiddleware - Client-side file ops (HITL for patch_file only)
    8. SourcesMiddleware - Access to project sources (list returns from state)
    9. WebsearchMiddleware - Web search and scraping (HITL for scrape_url)
    10. SubAgentMiddleware - Parallel research delegation (optional)
    
    Args:
        checkpointer: Optional checkpointer for persistence
        cost_per_iteration: Override cost per iteration (default: from DEEPRESEARCH_CONFIG)
        additional_middleware: Extra middleware to add
        include_payment: Whether to include payment middleware (default: True)
        include_subagents: Whether to include research sub-agents (default: False)
        max_concurrent_research_units: Max parallel research tasks (1-10)
        max_researcher_iterations: Max iterations per research task (1-10)
        debug: Enable debug logging
        
    Returns:
        Compiled agent graph ready for invoke/stream
        
    Note:
        Model selection is dynamic via RunnableConfig. Pass the model at invocation time:
        config={"configurable": {"llm_model": "grok-4-1-fast-non-reasoning"}}
        
    Example:
        ```python
        from langgraph.checkpoint.memory import MemorySaver
        
        agent = create_deepresearch_agent(
            checkpointer=MemorySaver(),
            cost_per_iteration=15,
        )
        
        # Start a research session with dynamic model selection
        result = await agent.ainvoke(
            {
                "messages": [HumanMessage(content="Research the history of Bitcoin")],
                "files_list": [...],      # Injected by client
                "sources_list": [...],    # Injected by client
                "payment_token": "cashuA...",  # Optional payment
            },
            config={"configurable": {"llm_model": "grok-4-1-fast-non-reasoning"}},
        )
        ```
    """
    # Use provided settings or fall back to defaults
    effective_concurrent = max_concurrent_research_units or DEFAULT_MAX_CONCURRENT_RESEARCH_UNITS
    effective_iterations = max_researcher_iterations or DEFAULT_MAX_RESEARCHER_ITERATIONS
    
    # Use configurable model - selection happens at runtime via config
    model = get_configurable_model(temperature=0.0)
    
    # Get effective cost per iteration
    # Priority: function arg > env var > agent config default
    effective_cost = DEEPRESEARCH_CONFIG.get_cost_per_iteration(cost_per_iteration)
    
    # Build system prompt with research settings
    system_prompt = get_research_system_prompt(
        include_workflow=True,
        include_subagent_instructions=include_subagents,
        max_concurrent_research_units=effective_concurrent,
        max_researcher_iterations=effective_iterations,
    )
    
    # Build middleware stack in order
    middleware: list[AgentMiddleware] = []
    
    # 1. Payment middleware (TBD - not fully implemented)
    if include_payment:
        middleware.append(CashuPaymentMiddleware(cost_per_iteration=effective_cost))
    
    # 2. Tool Validation - catch and correct malformed tool calls immediately
    middleware.append(ToolValidationMiddleware())
    
    # 3. Behavioural - control the agent's character and personality (prompt-only)
    middleware.append(BehaviouralMiddleware())
    
    # 4. Todo list - task tracking pseudo-tool
    middleware.append(TodoListMiddleware())
    
    # 5. Thinking - strategic reflection pseudo-tool
    middleware.append(ThinkingMiddleware())
    
    # 6. Clarification tools - HITL for ask_user, ask_choices
    middleware.append(ClarifyWithHumanMiddleware())

    # 7. Client tools - file operations (HITL for patch_file only)
    #    list_files returns from state, others auto-approve
    middleware.append(ClientToolsMiddleware())

    # 8. Sources - access to project sources
    #    list_sources returns from state, read/search auto-approve
    middleware.append(SourcesMiddleware())

    # 9. Web Search - URL discovery and content fetching
    #    web_search auto-creates sources, scrape_url requires HITL
    middleware.append(WebsearchMiddleware())
    
    # 10. Sub-agent middleware (optional, disabled by default)
    if include_subagents:
        # Lazy import to avoid circular dependencies
        from deepagents.middleware.subagents import SubAgentMiddleware
        
        subagent_config = create_research_subagent_config()
        middleware.append(
            SubAgentMiddleware(
                default_model=model,
                subagents=[subagent_config],
                default_middleware=[
                    ToolValidationMiddleware(),
                    WebsearchMiddleware(),
                    ThinkingMiddleware(),
                ],
                general_purpose_agent=False,
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
