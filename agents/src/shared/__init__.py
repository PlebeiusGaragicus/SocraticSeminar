"""Shared utilities for Socratic Seminar agents.

This module contains shared code used by multiple agents:
- get_model: Factory for creating LLM instances
- State types: Common state definitions for payment, agent settings, etc.
- Config: Agent configuration patterns
- Middleware: Reusable middleware components
"""

from src.shared.models import (
    get_model,
    LLMModelType,
    DEFAULT_LLM_MODEL,
    QWEN3_MODEL,
    QWEN3_BASE_URL,
    GROK4_MODEL,
)

from src.shared.state import (
    DEFAULT_COST_PER_ITERATION_SATS,
    PaymentStatus,
    CashuPaymentState,
    BaseAgentState,
    # Agent settings types
    LLMModel,
    AgentSettings,
    DEFAULT_AGENT_SETTINGS,
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
    SourcesMiddleware,
    SourcesState,
    WebsearchMiddleware,
    ThinkingMiddleware,
    ToolValidationMiddleware,
)

__all__ = [
    # Models
    "get_model",
    "LLMModelType",
    "DEFAULT_LLM_MODEL",
    "QWEN3_MODEL",
    "QWEN3_BASE_URL",
    "GROK4_MODEL",
    # State
    "DEFAULT_COST_PER_ITERATION_SATS",
    "PaymentStatus",
    "CashuPaymentState",
    "BaseAgentState",
    # Agent settings
    "LLMModel",
    "AgentSettings",
    "DEFAULT_AGENT_SETTINGS",
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
    "SourcesMiddleware",
    "SourcesState",
    "WebsearchMiddleware",
    "ThinkingMiddleware",
    "ToolValidationMiddleware",
]
