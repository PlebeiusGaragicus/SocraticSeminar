"""Simple Agent graph definition - the most minimal LangGraph possible."""

from langgraph.graph import StateGraph, END

from .state import SimpleAgentState
from .nodes import chat_node


def create_graph() -> StateGraph:
    """Create the Simple Agent graph with a single node."""
    
    builder = StateGraph(SimpleAgentState)
    
    # Add single node
    builder.add_node("chat", chat_node)
    
    # Simple flow: start -> chat -> end
    builder.add_edge("__start__", "chat")
    builder.add_edge("chat", END)
    
    return builder


# Compile the graph
graph = create_graph().compile()

