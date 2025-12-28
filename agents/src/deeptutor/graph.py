"""Deeptutor Agent graph definition.

Architecture: Agent using create_agent() with client-executed tools
1. Payment validation node checks ecash token
2. create_agent() handles the agent loop with tool calling
3. Tools read project_files from config (passed by wrapper node)
4. Read-only tools (list_files, get_file, search_files) work server-side
5. Only edit_file requires human approval (when enabled)
6. Payment redemption on completion
"""

import os
from typing import Any

from langchain.agents import create_agent
from langchain.agents.middleware import HumanInTheLoopMiddleware
from langchain_openai import ChatOpenAI
from langgraph.config import RunnableConfig
from langgraph.graph import StateGraph, END

from .state import DeeptutorState
from .tools import CLIENT_TOOLS
from .nodes import (
    validate_payment_node,
    redeem_payment_node,
    route_after_validation,
    build_system_prompt,
)

# Tools that require human approval before execution (write operations)
HITL_TOOLS = {"edit_file"}


# Configuration
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "http://localhost:11434/v1")
LLM_MODEL = os.getenv("LLM_MODEL", "qwen3-coder-30b-a3b-instruct-mlx")
LLM_API_KEY = os.getenv("LLM_API_KEY", "not-needed")


def get_model():
    """Get the chat model configured for OpenAI-compatible endpoint."""
    return ChatOpenAI(
        model=LLM_MODEL,
        base_url=LLM_BASE_URL,
        api_key=LLM_API_KEY,
        temperature=0.7,
    )


def create_deeptutor_agent():
    """Create the core agent using create_agent() with middleware.
    
    Only uses HumanInTheLoopMiddleware for write operations (edit_file).
    Read-only tools (list_files, get_file, search_files) work server-side
    by reading project_files from the config.
    """
    model = get_model()
    system_prompt = build_system_prompt(None)
    
    # Build middleware list - only add HITL for write operations
    middleware = []
    
    # Check if any HITL tools are in CLIENT_TOOLS
    tool_names = {t.name for t in CLIENT_TOOLS}
    hitl_tools_enabled = tool_names & HITL_TOOLS
    
    if hitl_tools_enabled:
        # Only interrupt on write operations that require human approval
        middleware.append(
            HumanInTheLoopMiddleware(interrupt_on={
                tool_name: True for tool_name in hitl_tools_enabled
            })
        )
    
    # Create agent with conditional middleware
    agent = create_agent(
        model,
        system_prompt=system_prompt,
        tools=CLIENT_TOOLS,
        middleware=middleware,
    )
    
    return agent


# Store the compiled agent at module level
_deeptutor_agent = None


def get_deeptutor_agent():
    """Get or create the deeptutor agent singleton."""
    global _deeptutor_agent
    if _deeptutor_agent is None:
        _deeptutor_agent = create_deeptutor_agent()
    return _deeptutor_agent


async def agent_node(state: DeeptutorState, config: RunnableConfig) -> dict[str, Any]:
    """Wrapper node that invokes the agent with project_files in config.
    
    This is necessary because create_agent() creates an inner graph with its own
    state schema. The tools inside that graph can't see our outer state keys.
    We solve this by passing project_files through the config's 'configurable'.
    """
    agent = get_deeptutor_agent()
    
    # Extract project_files from our state and pass via config
    project_files = state.get("project_files", [])
    
    # Merge project_files into the configurable section of the config
    agent_config = {
        **config,
        "configurable": {
            **config.get("configurable", {}),
            "project_files": project_files,
        }
    }
    
    # Invoke the agent with only the keys it understands (messages)
    # The agent will return updated messages
    result = await agent.ainvoke(
        {"messages": state.get("messages", [])},
        agent_config
    )
    
    return {"messages": result.get("messages", [])}


def create_graph() -> StateGraph:
    """Create the Deeptutor Agent graph with payment wrapper.
    
    The graph uses a wrapper node (agent_node) that passes project_files
    through config to the inner agent's tools.
    """
    
    builder = StateGraph(DeeptutorState)
    
    # Add nodes
    builder.add_node("validate_payment", validate_payment_node)
    builder.add_node("agent", agent_node)  # Wrapper that passes project_files via config
    builder.add_node("redeem_payment", redeem_payment_node)
    
    # Define edges
    # Start -> validate_payment
    builder.add_edge("__start__", "validate_payment")
    
    # validate_payment -> agent (if valid) or end (if invalid)
    builder.add_conditional_edges(
        "validate_payment",
        route_after_validation,
        {"agent": "agent", "end": END},
    )
    
    # agent -> redeem_payment (agent handles its own tool loop internally)
    builder.add_edge("agent", "redeem_payment")
    
    # redeem_payment -> end
    builder.add_edge("redeem_payment", END)
    
    return builder


# Compile the graph
graph = create_graph().compile()

