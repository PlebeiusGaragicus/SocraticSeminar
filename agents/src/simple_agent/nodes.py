"""Single node implementation for the Simple Test Agent."""

import os
from typing import Any

from langchain_core.messages import SystemMessage
from langchain_openai import ChatOpenAI
from langgraph.config import RunnableConfig

from .state import SimpleAgentState


# Configuration
WALLET_URL = os.getenv("WALLET_URL", "http://localhost:8000")

LLM_BASE_URL = os.getenv("LLM_BASE_URL", "http://localhost:11434/v1")
LLM_MODEL = os.getenv("LLM_MODEL", "qwen3-coder-30b-a3b-instruct-mlx")
LLM_API_KEY = os.getenv("LLM_API_KEY", "not-needed")

def get_model():
    """Get the chat model configured for OpenAI-compatible endpoint."""
    return ChatOpenAI(
        model=LLM_MODEL,
        base_url=LLM_BASE_URL,
        api_key=LLM_API_KEY,
        temperature=0.7,
    )


async def chat_node(
    state: SimpleAgentState,
    config: RunnableConfig
) -> dict[str, Any]:
    """
    Simple chat node that just calls the LLM and returns a response.
    This is the simplest possible agent node.
    """
    
    model = get_model()
    messages = list(state.get("messages", []))
    
    # Simple system prompt
    system_prompt = """You are a helpful AI assistant. 
Be concise and clear in your responses."""

    # Prepend system message if not already present
    if not messages or not isinstance(messages[0], SystemMessage):
        messages = [SystemMessage(content=system_prompt)] + messages
    
    # Invoke the model
    response = await model.ainvoke(messages)
    
    return {"messages": [response]}

