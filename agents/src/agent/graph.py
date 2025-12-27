"""Seminar Agent graph definition.

Architecture: Agent with Client-Executed Tools
1. Agent decides when to use tools (list_files, get_file, search_files, edit_file)
2. Tools are stubs - execution happens on the client
3. Graph uses interrupt_before=["tools"] to pause before tool execution
4. Client executes tools locally (against IndexedDB)
5. Client resumes graph with tool results
"""

from typing import Literal

from langchain_core.messages import AIMessage
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode

from .state import AgentState
from .tools import CLIENT_TOOLS
from .nodes import (
    validate_payment_node,
    agent_node,
    redeem_payment_node,
    route_after_validation,
)


def should_continue(state: AgentState) -> Literal["tools", "redeem_payment"]:
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


def create_graph() -> StateGraph:
    """Create the Seminar Agent graph with tool support."""
    
    builder = StateGraph(AgentState)
    
    # Create tool node with client-executed tools
    tool_node = ToolNode(CLIENT_TOOLS)
    
    # Add nodes
    builder.add_node("validate_payment", validate_payment_node)
    builder.add_node("agent", agent_node)
    builder.add_node("tools", tool_node)
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
    
    # agent -> tools (if tool calls) or redeem_payment (if done)
    builder.add_conditional_edges(
        "agent",
        should_continue,
        {"tools": "tools", "redeem_payment": "redeem_payment"},
    )
    
    # tools -> agent (process tool results)
    builder.add_edge("tools", "agent")
    
    # redeem_payment -> end
    builder.add_edge("redeem_payment", END)
    
    return builder


# Compile the graph WITH interrupt_before tools
# This causes the graph to pause before executing tools,
# allowing the client to execute them locally and resume
graph = create_graph().compile(interrupt_before=["tools"])

