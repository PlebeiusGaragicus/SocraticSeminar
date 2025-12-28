"""Deeptutor Agent using proper deepagent middleware conventions.

Architecture:
- Uses create_agent() with middleware composition
- CashuPaymentMiddleware: Streaming micropayments with per-iteration deduction
- ClientToolsMiddleware: Client-side file operations via interrupts
- HumanInTheLoopMiddleware: Approval for write operations

The agent operates with:
1. Files stored in the browser (client provides via interrupts)
2. Streaming Cashu payments (deducted per LLM iteration)
3. Human approval for write operations and funding requests
"""

import os
from typing import Any

from langchain.agents import create_agent
from langchain.agents.middleware import HumanInTheLoopMiddleware
from langchain.agents.middleware.types import AgentMiddleware
from langchain_anthropic import ChatAnthropic
from langchain_openai import ChatOpenAI
from langgraph.graph.state import CompiledStateGraph
from langgraph.types import Checkpointer

from .middleware import CashuPaymentMiddleware, ClientToolsMiddleware
from .state import DeeptutorState, COST_PER_ITERATION_SATS


# =============================================================================
# CONFIGURATION
# =============================================================================

# LLM Configuration
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "openai")  # "openai" or "anthropic"
LLM_MODEL = os.getenv("LLM_MODEL", "gpt-4o")
LLM_BASE_URL = os.getenv("LLM_BASE_URL")  # Optional: for OpenAI-compatible endpoints
LLM_API_KEY = os.getenv("LLM_API_KEY", os.getenv("OPENAI_API_KEY", ""))

# Payment Configuration
PAYMENT_COST_PER_ITERATION = int(os.getenv("COST_PER_ITERATION_SATS", str(COST_PER_ITERATION_SATS)))


# =============================================================================
# MODEL FACTORY
# =============================================================================

def get_model():
    """Get the configured chat model.
    
    Supports:
    - OpenAI (default): gpt-4o, gpt-4-turbo, etc.
    - Anthropic: claude-3-5-sonnet, claude-3-opus, etc.
    - OpenAI-compatible: Any endpoint with LLM_BASE_URL
    """
    if LLM_PROVIDER == "anthropic":
        return ChatAnthropic(
            model_name=LLM_MODEL,
            max_tokens=8192,
        )
    else:
        # OpenAI or OpenAI-compatible
        kwargs = {
            "model": LLM_MODEL,
            "temperature": 0.7,
        }
        if LLM_BASE_URL:
            kwargs["base_url"] = LLM_BASE_URL
        if LLM_API_KEY:
            kwargs["api_key"] = LLM_API_KEY
        
        return ChatOpenAI(**kwargs)


# =============================================================================
# SYSTEM PROMPT
# =============================================================================

DEEPTUTOR_SYSTEM_PROMPT = """You are a Socratic dialogue assistant helping users develop and refine their arguments.

## Your Role

1. Help users develop arguments through thoughtful questioning
2. Assist with writing and editing documents, especially structured arguments
3. Create and modify artifacts (documents, code, structured seminars)

## Socratic Seminar Document Structure

When helping with Socratic Seminar documents, follow this structure:
- **Thesis**: A clear, arguable statement
- **Supporting Clauses**: Arguments with definitions, citations, and narratives
- **Refutations**: Counter-arguments addressed honestly
- **Replies**: Responses that strengthen the original argument

## Guidelines

- Be helpful, thoughtful, and encourage critical thinking
- Ask clarifying questions when the user's intent is unclear
- When editing files, explain your changes clearly
- Use list_files() first to discover available files
- Read files before attempting to edit them

## Citation Format

When referencing content from files, cite with the file title:
- "According to [[File Title]], the author argues..."
- Use quotes for direct excerpts"""


# =============================================================================
# AGENT FACTORY
# =============================================================================

def create_deeptutor_agent(
    *,
    checkpointer: Checkpointer | None = None,
    cost_per_iteration: int = PAYMENT_COST_PER_ITERATION,
    additional_middleware: list[AgentMiddleware] | None = None,
    debug: bool = False,
) -> CompiledStateGraph:
    """Create the Deeptutor agent with all middleware.
    
    Middleware Stack (in order):
    1. CashuPaymentMiddleware - Payment validation and per-iteration deduction
    2. ClientToolsMiddleware - File operations via client interrupts
    3. HumanInTheLoopMiddleware - Approval for writes and funding
    4. Any additional middleware
    
    Args:
        checkpointer: Optional checkpointer for persistence
        cost_per_iteration: Satoshis per LLM iteration (default: 10)
        additional_middleware: Extra middleware to add after standard ones
        debug: Enable debug logging
        
    Returns:
        Compiled agent graph ready for invoke/stream
        
    Example:
        ```python
        from langgraph.checkpoint.memory import MemorySaver
        
        agent = create_deeptutor_agent(
            checkpointer=MemorySaver(),
            cost_per_iteration=10,
        )
        
        # Start a session with payment
        result = await agent.ainvoke({
            "messages": [HumanMessage(content="Help me with my argument")],
            "payment_token": "cashuA...",
        })
        ```
    """
    model = get_model()
    
    # Build middleware stack
    #
    # NOTE: ClientToolsMiddleware handles ALL file tool interrupts including approval.
    # Write operations (write_file, edit_file) have requires_approval=True which the
    # frontend uses to show approval UI before executing locally.
    # 
    # DO NOT add write_file/edit_file to HumanInTheLoopMiddleware - it would cause
    # double interrupts (one for HITL approval, another for client execution).
    #
    middleware: list[AgentMiddleware] = [
        # 1. Payment middleware - validates token, tracks balance, deducts per iteration
        CashuPaymentMiddleware(cost_per_iteration=cost_per_iteration),
        
        # 2. Client tools - ALL file operations interrupt for client-side execution
        #    Write tools include requires_approval=True for frontend approval UI
        ClientToolsMiddleware(),
        
        # 3. Human-in-the-loop - ONLY for payment funding requests
        #    File operations are handled by ClientToolsMiddleware above
        HumanInTheLoopMiddleware(
            interrupt_on={
                "request_additional_funding": True,
            }
        ),
    ]
    
    # Add any additional middleware
    if additional_middleware:
        middleware.extend(additional_middleware)
    
    # Create the agent
    agent = create_agent(
        model,
        system_prompt=DEEPTUTOR_SYSTEM_PROMPT,
        tools=[],  # Tools provided by middleware
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
graph = create_deeptutor_agent()
