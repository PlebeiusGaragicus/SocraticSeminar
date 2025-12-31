"""Shared middleware for Socratic Seminar agents.

This module contains middleware that can be used by multiple agents:
- CashuPaymentMiddleware: Streaming micropayments with Cashu tokens
- ClarifyWithHumanMiddleware: Tools for asking clarifying questions
- ClientToolsMiddleware: Client-side file operations via interrupts
"""

from .payment import CashuPaymentMiddleware, CashuPaymentState
from .clarify import ClarifyWithHumanMiddleware, ClarifyState
from .client_tools import ClientToolsMiddleware, ClientToolsState
from .websearch import WebsearchMiddleware
from .thinking import ThinkingMiddleware
from .validation import ToolValidationMiddleware

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
