"""Deeptutor Agent graph definition.

Architecture: Agent using create_agent() with client-executed tools
1. Payment validation node checks ecash token
2. create_agent() handles the agent loop with tool calling
3. Tools are stubs - execution happens on the client via interrupts
4. Graph uses interrupt_on to pause before tool execution
5. Client executes tools locally (against IndexedDB)
6. Client resumes graph with tool results
7. Payment redemption on completion
"""

import os
from typing import Literal

from langchain.agents import create_agent
from langchain.agents.middleware import HumanInTheLoopMiddleware
from langchain_core.messages import AIMessage
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, END

from .state import DeeptutorState
from .tools import CLIENT_TOOLS
from .nodes import (
    validate_payment_node,
    redeem_payment_node,
    route_after_validation,
    build_system_prompt,
)


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


def should_continue(state: DeeptutorState) -> Literal["tools", "redeem_payment"]:
    """Determine if the agent wants to call tools or is done.
    
    If the last message has tool calls, route to tools node.
    Otherwise, proceed to payment redemption and finish.
    """
    messages = state.get("messages", [])
    if not messages:
        return "redeem_payment"
    
    last_message = messages[-1]
    
    # Check if the last message has tool calls
    if isinstance(last_message, AIMessage) and last_message.tool_calls:
        return "tools"
    
    return "redeem_payment"


def create_deeptutor_agent():
    """Create the core agent using create_agent() with middleware.
    
    Uses HumanInTheLoopMiddleware to interrupt before client-executed tools,
    allowing the client to execute them locally and resume.
    """
    model = get_model()
    
    # Get project files from state to build dynamic system prompt
    # Note: The system prompt with project files will be built in the node
    system_prompt = build_system_prompt(None)
    
    # Create agent with middleware
    # HumanInTheLoopMiddleware handles interrupts for client-side tool execution
    agent = create_agent(
        model,
        system_prompt=system_prompt,
        tools=CLIENT_TOOLS,
        middleware=[
            HumanInTheLoopMiddleware(interrupt_on={
                "list_files": True,
                "get_file": True,
                "search_files": True,
            }),
        ],
    )
    
    return agent


def create_graph() -> StateGraph:
    """Create the Deeptutor Agent graph with payment wrapper.
    
    The graph embeds the create_agent() result as a node within
    a larger graph that handles payment validation/redemption.
    """
    
    builder = StateGraph(DeeptutorState)
    
    # Create the core agent (compiled graph from create_agent)
    deeptutor_agent = create_deeptutor_agent()
    
    # Add nodes
    builder.add_node("validate_payment", validate_payment_node)
    builder.add_node("agent", deeptutor_agent)  # Embed compiled agent as node
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
    # The interrupt_on in HumanInTheLoopMiddleware will pause before tools
    builder.add_edge("agent", "redeem_payment")
    
    # redeem_payment -> end
    builder.add_edge("redeem_payment", END)
    
    return builder


# Compile the graph
# The agent node internally handles tool interrupts via HumanInTheLoopMiddleware
graph = create_graph().compile()

