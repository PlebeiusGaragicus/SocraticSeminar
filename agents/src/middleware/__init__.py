"""Shared middleware for Socratic Seminar agents.

This module contains middleware that can be used by multiple agents:
- CashuPaymentMiddleware: Streaming micropayments with Cashu tokens
- ClarifyWithHumanMiddleware: Tools for asking clarifying questions
- ClientToolsMiddleware: Client-side file operations via interrupts
- ScratchFilesMiddleware: Agent working memory (visible to users, read-only)
"""

from .payment import CashuPaymentMiddleware, CashuPaymentState
from .clarify import ClarifyWithHumanMiddleware, ClarifyState
from .client_tools import ClientToolsMiddleware, ClientToolsState
from .scratch_files import ScratchFilesMiddleware, ScratchFilesState
from .websearch import WebsearchMiddleware
from .thinking import ThinkingMiddleware

__all__ = [
    "CashuPaymentMiddleware",
    "CashuPaymentState",
    "ClarifyWithHumanMiddleware",
    "ClarifyState",
    "ClientToolsMiddleware",
    "ClientToolsState",
    "ScratchFilesMiddleware",
    "ScratchFilesState",
    "WebsearchMiddleware",
    "ThinkingMiddleware",
]
