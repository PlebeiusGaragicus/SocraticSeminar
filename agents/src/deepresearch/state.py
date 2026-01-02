"""State definition for the DeepResearch Agent.

Extends the shared BaseAgentState with research-specific fields.
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

class DeepResearchState(BaseAgentState):
    """State for the DeepResearch Agent.
    
    Extends BaseAgentState with research-specific fields.
    
    Inherited from BaseAgentState:
    - messages: Message history
    - payment_*: Cashu payment state fields
    - current_project_id: Project context
    - run_id: Run metadata
    
    Note: Some state fields are added automatically by middleware:
    - `todos`: Task tracking list (TodoListMiddleware)
    """
    
    # ==========================================================================
    # RESEARCH STATE
    # ==========================================================================
    
    # The original research query/request
    research_query: NotRequired[str | None]
    
    # List of sources discovered during research
    research_sources: NotRequired[list[ResearchSource]]
    
    # Key findings from research
    research_findings: NotRequired[list[ResearchFinding]]
    
    # Current research phase: planning, researching, synthesizing, complete
    research_phase: NotRequired[Literal["planning", "researching", "synthesizing", "complete"] | None]
