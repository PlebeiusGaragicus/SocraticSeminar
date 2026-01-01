"""State definition for the Deeptutor Agent.

Includes payment state for streaming Cashu micropayments and
project file context for client-side tool execution.
"""

from typing import Annotated, Literal, Sequence
from typing_extensions import TypedDict, NotRequired

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages


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
# PAYMENT TYPES
# =============================================================================

# Cost per agent iteration in satoshis
COST_PER_ITERATION_SATS = 10

# Payment status values
PaymentStatus = Literal["pending", "active", "exhausted", "completed", "error", "refunded"]


class CashuPaymentState(TypedDict, total=False):
    """State for streaming Cashu micropayments.
    
    Payment Flow:
    1. User sends token (e.g., 100 sats)
    2. Agent validates token without redeeming
    3. Each iteration deducts COST_PER_ITERATION_SATS
    4. When balance exhausted, interrupt for additional funding
    5. On completion/error, generate refund token for unused balance
    6. Client can detect unredeemed tokens on thread reload for recovery
    """
    
    # Original token from client (not yet fully redeemed)
    payment_token: str | None
    
    # Remaining balance in satoshis
    payment_balance_sats: int
    
    # Total spent this session
    payment_spent_sats: int
    
    # Refund token for unused balance (stored for session recovery)
    # Format: Cashu token string representing unredeemed proofs
    payment_refund_token: str | None
    
    # Current payment status
    payment_status: PaymentStatus
    
    # Whether the refund has been claimed by the client
    # Used for session recovery - if False on thread load, client should claim
    payment_refund_claimed: bool


# =============================================================================
# MAIN STATE
# =============================================================================

class DeeptutorState(TypedDict, total=False):
    """State for the Deeptutor Agent.
    
    Combines:
    - Message history (required for create_agent)
    - Cashu payment state for streaming micropayments
    - Project context for client-side file operations
    - Todo list (added by TodoListMiddleware)
    
    Note: Some state fields are added automatically by middleware:
    - `todos`: Task tracking list (TodoListMiddleware)
    """
    
    # ==========================================================================
    # MESSAGES (required for create_agent)
    # ==========================================================================
    messages: Annotated[Sequence[BaseMessage], add_messages]
    
    # ==========================================================================
    # CASHU PAYMENT STATE
    # ==========================================================================
    
    # Original token from client
    payment_token: str | None
    
    # Remaining balance in satoshis (decremented each iteration)
    payment_balance_sats: int
    
    # Total spent this session
    payment_spent_sats: int
    
    # Refund token for unused balance
    payment_refund_token: str | None
    
    # Current payment status
    payment_status: PaymentStatus
    
    # Whether refund has been claimed (for session recovery)
    payment_refund_claimed: bool
    
    # ==========================================================================
    # PROJECT CONTEXT
    # ==========================================================================
    
    # Current project ID (used to scope file operations)
    current_project_id: str | None
    
    # ==========================================================================
    # RUN METADATA
    # ==========================================================================
    
    # Unique run identifier
    run_id: str | None
