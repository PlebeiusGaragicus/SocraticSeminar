"""State definition for the Seminar Agent."""

from typing import Annotated, Any, Optional, Sequence
from typing_extensions import TypedDict

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages


class PaymentInfo(TypedDict, total=False):
    """Payment information from the client."""
    ecash_token: str
    amount_sats: int


class ArtifactContent(TypedDict):
    """A single version of an artifact."""
    index: int
    title: str
    content: str
    language: Optional[str]
    type: str  # 'text' | 'code' | 'socratic'


class Artifact(TypedDict):
    """Artifact with version history."""
    id: str
    project_id: str
    current_index: int
    contents: list[ArtifactContent]


class ProjectFile(TypedDict):
    """Metadata about a project file (artifact) for tool context.
    
    This is injected into state on each invocation so the agent
    knows what files exist in the project. Actual content is fetched
    via tool calls that execute on the client.
    """
    id: str
    title: str
    file_type: str  # 'artifact' | 'document' | 'code'


class AgentState(TypedDict, total=False):
    """State for the Seminar Agent graph."""
    
    # Messages in the conversation
    messages: Annotated[Sequence[BaseMessage], add_messages]
    
    # Payment fields
    payment: Optional[PaymentInfo]
    payment_validated: bool
    payment_token: Optional[str]  # Token to redeem on success
    
    # Artifact context (legacy - for direct artifact passing)
    artifact: Optional[Artifact]
    highlighted_text: Optional[str]
    
    # Project files context - injected each invocation
    # Contains file metadata only; content fetched via tools
    project_files: Optional[list[ProjectFile]]
    current_project_id: Optional[str]
    
    # Control flow
    next: Optional[str]
    
    # Run metadata
    run_id: Optional[str]
    refund: bool

