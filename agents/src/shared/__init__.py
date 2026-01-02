"""Shared utilities for Socratic Seminar agents.

This module contains shared code used by multiple agents:
- get_model: Factory for creating LLM instances
- State types: Common state definitions for payment, etc.
- Config: Agent configuration patterns
- Middleware: Reusable middleware components
"""

from src.shared.models import get_model, LLM_PROVIDER, LLM_MODEL, LLM_BASE_URL, LLM_API_KEY

from src.shared.state import (
    DEFAULT_COST_PER_ITERATION_SATS,
    PaymentStatus,
    CashuPaymentState,
    BaseAgentState,
)

from src.shared.config import (
    AgentConfig,
    DEEPTUTOR_CONFIG,
    DEEPRESEARCH_CONFIG,
)

from src.shared.middleware import (
    CashuPaymentMiddleware,
    CashuPaymentState as CashuPaymentMiddlewareState,  # Middleware's state schema
    ClarifyWithHumanMiddleware,
    ClarifyState,
    ClientToolsMiddleware,
    ClientToolsState,
    WebsearchMiddleware,
    ThinkingMiddleware,
    ToolValidationMiddleware,
)

__all__ = [
    # Models
    "get_model",
    "LLM_PROVIDER",
    "LLM_MODEL",
    "LLM_BASE_URL",
    "LLM_API_KEY",
    # State
    "DEFAULT_COST_PER_ITERATION_SATS",
    "PaymentStatus",
    "CashuPaymentState",
    "BaseAgentState",
    # Config
    "AgentConfig",
    "DEEPTUTOR_CONFIG",
    "DEEPRESEARCH_CONFIG",
    # Middleware
    "CashuPaymentMiddleware",
    "CashuPaymentMiddlewareState",
    "ClarifyWithHumanMiddleware",
    "ClarifyState",
    "ClientToolsMiddleware",
    "ClientToolsState",
    "WebsearchMiddleware",
    "ThinkingMiddleware",
    "ToolValidationMiddleware",
]
