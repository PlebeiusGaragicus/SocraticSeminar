"""Shared state definitions for Socratic Seminar agents.

This module contains common state types used across all agents:
- Payment state for Cashu micropayments
- Base agent state with common fields
"""

from typing import Annotated, Literal, Sequence
from typing_extensions import TypedDict, NotRequired

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages


# =============================================================================
# PAYMENT TYPES
# =============================================================================

# Default cost per agent iteration in satoshis
DEFAULT_COST_PER_ITERATION_SATS = 10

# Payment status values
PaymentStatus = Literal["pending", "active", "exhausted", "completed", "error", "refunded"]


class CashuPaymentState(TypedDict, total=False):
    """State for streaming Cashu micropayments.
    
    This TypedDict is used to compose agent states. All fields are optional
    (total=False) so agents can extend with their own required fields.
    
    Payment Flow:
    1. User sends token (e.g., 100 sats)
    2. Agent validates token without redeeming
    3. Each iteration deducts cost_per_iteration sats
    4. When balance exhausted, interrupt for additional funding
    5. On completion/error, generate refund token for unused balance
    6. Client can detect unredeemed tokens on thread reload for recovery
    
    Client Input Fields:
        payment_token: Cashu token from client
        payment_cost_per_iteration: Optional override for per-iteration cost
        
    Runtime Fields (managed by middleware):
        payment_balance_sats: Remaining balance
        payment_spent_sats: Total spent this session
        payment_refund_token: Token for unused balance
        payment_status: Current payment status
        payment_refund_claimed: Whether refund has been claimed
    """
    
    # Original token from client (not yet fully redeemed)
    payment_token: str | None
    
    # Optional: client can override cost per iteration
    # If not provided, uses agent's configured default
    payment_cost_per_iteration: int | None
    
    # Remaining balance in satoshis
    payment_balance_sats: int
    
    # Total spent this session
    payment_spent_sats: int
    
    # Refund token for unused balance (stored for session recovery)
    payment_refund_token: str | None
    
    # Current payment status
    payment_status: PaymentStatus
    
    # Whether the refund has been claimed by the client
    payment_refund_claimed: bool


# =============================================================================
# BASE AGENT STATE
# =============================================================================

class BaseAgentState(TypedDict, total=False):
    """Base state for all agents.
    
    Includes:
    - Message history (required for create_agent)
    - Cashu payment state fields
    - Common metadata fields
    
    Agents should extend this with their own specific fields.
    
    Example:
        class MyAgentState(BaseAgentState):
            # Agent-specific fields
            my_custom_field: str | None
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
    
    # Optional: client override for cost per iteration
    payment_cost_per_iteration: int | None
    
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
    # COMMON METADATA
    # ==========================================================================
    
    # Current project ID (used to scope file operations)
    current_project_id: str | None
    
    # Unique run identifier
    run_id: str | None

