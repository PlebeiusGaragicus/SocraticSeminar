"""Shared middleware for Socratic Seminar agents.

This module contains middleware that can be used by multiple agents:
- CashuPaymentMiddleware: Streaming micropayments with Cashu tokens
- ClarifyWithHumanMiddleware: Tools for asking clarifying questions
- ClientToolsMiddleware: Client-side file operations via interrupts
"""

from src.shared.middleware.payment import CashuPaymentMiddleware, CashuPaymentState
from src.shared.middleware.clarify import ClarifyWithHumanMiddleware, ClarifyState
from src.shared.middleware.client_tools import ClientToolsMiddleware, ClientToolsState
from src.shared.middleware.websearch import WebsearchMiddleware
from src.shared.middleware.thinking import ThinkingMiddleware
from src.shared.middleware.validation import ToolValidationMiddleware

__all__ = [
    "CashuPaymentMiddleware",
    "CashuPaymentState",
    "ClarifyWithHumanMiddleware",
    "ClarifyState",
    "ClientToolsMiddleware",
    "ClientToolsState",
    "WebsearchMiddleware",
    "ThinkingMiddleware",
    "ToolValidationMiddleware",
]

