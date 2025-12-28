"""State definition for the Deeptutor Agent."""

from typing import Annotated, Optional, Sequence
from typing_extensions import TypedDict, NotRequired

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages


class PaymentInfo(TypedDict, total=False):
    """Payment information from the client."""
    ecash_token: str
    amount_sats: int


class ProjectFile(TypedDict):
    """Metadata and content for a project file.
    
    This is injected into state on each invocation so the agent
    knows what files exist in the project and can read their content.
    Content is included by the frontend for server-side file reading.
    """
    id: str
    title: str
    file_type: str  # 'artifact' | 'document' | 'code'
    content: NotRequired[str]  # Optional: file content for reading


class DeeptutorState(TypedDict, total=False):
    """State for the Deeptutor Agent graph.
    
    Extends the base messaging pattern with payment validation
    and project file context fields.
    """
    
    # Messages in the conversation (required for create_agent)
    messages: Annotated[Sequence[BaseMessage], add_messages]
    
    # Payment fields
    payment: Optional[PaymentInfo]
    payment_validated: bool
    payment_token: Optional[str]  # Token to redeem on success
    
    # Project files context - injected each invocation
    # Contains file metadata and content for server-side reading
    project_files: Optional[list[ProjectFile]]
    current_project_id: Optional[str]
    
    # Run metadata
    run_id: Optional[str]
    refund: bool

