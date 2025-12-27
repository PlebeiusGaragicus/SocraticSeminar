"""Seminar Agent graph definition."""

from langgraph.graph import StateGraph, END

from .state import AgentState
from .nodes import (
    validate_payment_node,
    agent_node,
    redeem_payment_node,
    route_after_validation,
)


def create_graph() -> StateGraph:
    """Create the Seminar Agent graph."""
    
    builder = StateGraph(AgentState)
    
    # Add nodes
    builder.add_node("validate_payment", validate_payment_node)
    builder.add_node("agent", agent_node)
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
    
    # agent -> redeem_payment
    builder.add_edge("agent", "redeem_payment")
    
    # redeem_payment -> end
    builder.add_edge("redeem_payment", END)
    
    return builder


# Compile the graph
graph = create_graph().compile()

