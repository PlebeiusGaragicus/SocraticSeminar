"""State definition for the Deeptutor Agent.

Extends the shared BaseAgentState with Deeptutor-specific fields.
"""

from typing import Annotated, Literal, Sequence
from typing_extensions import TypedDict, NotRequired

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages

from src.shared.state import (
    DEFAULT_COST_PER_ITERATION_SATS,
    PaymentStatus,
    BaseAgentState,
)

# Re-export for backward compatibility
COST_PER_ITERATION_SATS = DEFAULT_COST_PER_ITERATION_SATS


# =============================================================================
# PROJECT FILE TYPES
# =============================================================================

class ProjectFile(TypedDict):
    """Metadata and content for a project file.
    
    Files are stored in the browser (IndexedDB) and provided to the agent
    via client-side tool execution. When the agent calls read_file or
    list_files, execution is interrupted and the client provides the data.
    """
    id: str
    title: str
    file_type: Literal["artifact", "document", "code"]
    content: NotRequired[str]  # Optional: included when client provides file content


# =============================================================================
# MAIN STATE
# =============================================================================

class DeeptutorState(BaseAgentState):
    """State for the Deeptutor Agent.
    
    Extends BaseAgentState with Deeptutor-specific fields.
    
    Inherited from BaseAgentState:
    - messages: Message history
    - payment_*: Cashu payment state fields
    - current_project_id: Project context
    - run_id: Run metadata
    
    Note: Some state fields are added automatically by middleware:
    - `todos`: Task tracking list (TodoListMiddleware)
    """
    pass  # Currently no additional fields beyond BaseAgentState
