"""State definition for the Simple Test Agent."""

from typing import Annotated, Sequence
from typing_extensions import TypedDict

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages


class SimpleAgentState(TypedDict, total=False):
    """Minimal state for the Simple Agent graph."""
    
    # Messages in the conversation
    messages: Annotated[Sequence[BaseMessage], add_messages]

