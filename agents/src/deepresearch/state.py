"""State definition for the DeepResearch Agent.

Includes payment state for streaming Cashu micropayments and
research-specific fields for tracking research progress.
"""

from typing import Annotated, Literal, Sequence
from typing_extensions import TypedDict, NotRequired

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages


# =============================================================================
# PAYMENT TYPES (from shared middleware)
# =============================================================================

# Cost per agent iteration in satoshis
COST_PER_ITERATION_SATS = 10

# Payment status values
PaymentStatus = Literal["pending", "active", "exhausted", "completed", "error", "refunded"]


# =============================================================================
# RESEARCH TYPES
# =============================================================================

class ResearchSource(TypedDict):
    """A source discovered during research."""
    url: str
    title: str
    content_preview: NotRequired[str]
    fetched: bool


class ResearchFinding(TypedDict):
    """A finding from research."""
    content: str
    source_urls: list[str]


# =============================================================================
# MAIN STATE
# =============================================================================

class DeepResearchState(TypedDict, total=False):
    """State for the DeepResearch Agent.
    
    Combines:
    - Message history (required for create_agent)
    - Cashu payment state for streaming micropayments
    - Research-specific fields
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
    # RESEARCH STATE
    # ==========================================================================
    
    # The original research query/request
    research_query: str | None
    
    # List of sources discovered during research
    research_sources: list[ResearchSource]
    
    # Key findings from research
    research_findings: list[ResearchFinding]
    
    # Current research phase: planning, researching, synthesizing, complete
    research_phase: Literal["planning", "researching", "synthesizing", "complete"] | None
    
    # ==========================================================================
    # RUN METADATA
    # ==========================================================================
    
    # Unique run identifier
    run_id: str | None

