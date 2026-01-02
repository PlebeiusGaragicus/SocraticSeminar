"""Shared model factory for Socratic Seminar agents.

Supports:
- OpenAI (default): gpt-4o, gpt-4-turbo, etc.
- XAI (Grok): grok-2, grok-2-mini, etc.
- OpenAI-compatible: Any endpoint with LLM_BASE_URL
"""

import os

from langchain_openai import ChatOpenAI


# =============================================================================
# CONFIGURATION
# =============================================================================

LLM_PROVIDER = os.getenv("LLM_PROVIDER", "openai")  # "openai" or "xai"
LLM_MODEL = os.getenv("LLM_MODEL", "qwen3-coder-30b-a3b-instruct-mlx")
LLM_BASE_URL = os.getenv("LLM_BASE_URL")
LLM_API_KEY = os.getenv("LLM_API_KEY", None)

# XAI-specific configuration
XAI_API_KEY = os.getenv("XAI_API_KEY", "")
XAI_BASE_URL = "https://api.x.ai/v1"
# NOTE: Current pricing as of 2026.01.02:  $0.20 per 1M input tokens / $0.50 per 1M output tokens
XAI_DEFAULT_MODEL = os.getenv("XAI_DEFAULT_MODEL", "grok-4-1-fast-non-reasoning")


# =============================================================================
# MODEL FACTORY
# =============================================================================

def get_model(temperature: float = 0.7):
    """Get the configured chat model.
    
    Supports:
    - OpenAI (default): gpt-4o, gpt-4-turbo, etc.
    - XAI (Grok): grok-2, grok-2-mini, etc.
    - OpenAI-compatible: Any endpoint with LLM_BASE_URL
    
    Args:
        temperature: Model temperature (default: 0.7)
        
    Returns:
        Configured ChatOpenAI instance
        
    Environment Variables:
        LLM_PROVIDER: "openai" (default) or "xai"
        LLM_MODEL: Model name (e.g., "gpt-4o", "grok-2")
        LLM_BASE_URL: Custom base URL for OpenAI-compatible endpoints
        LLM_API_KEY: API key (falls back to OPENAI_API_KEY)
        XAI_API_KEY: XAI-specific API key (used when LLM_PROVIDER="xai")
        XAI_DEFAULT_MODEL: Default XAI model (used when LLM_MODEL does not start with "grok")
    """
    if LLM_PROVIDER == "xai":
        # XAI's Grok uses OpenAI-compatible API
        return ChatOpenAI(
            model=LLM_MODEL if LLM_MODEL.startswith("grok") else XAI_DEFAULT_MODEL,
            base_url=XAI_BASE_URL,
            api_key=XAI_API_KEY or LLM_API_KEY,
            temperature=temperature,
        )
    else:
        # OpenAI or OpenAI-compatible
        kwargs = {
            "model": LLM_MODEL,
            "temperature": temperature,
        }
        if LLM_BASE_URL:
            kwargs["base_url"] = LLM_BASE_URL
        if LLM_API_KEY:
            kwargs["api_key"] = LLM_API_KEY
        
        return ChatOpenAI(**kwargs)

