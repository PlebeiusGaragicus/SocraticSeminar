"""Node implementations for the Seminar Agent."""

import os
import uuid
from typing import Any, Literal

import httpx
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from langgraph.config import RunnableConfig

from .state import AgentState


# Configuration
WALLET_URL = os.getenv("WALLET_URL", "http://localhost:8000")
OPENAI_API_BASE = os.getenv("OPENAI_API_BASE", "http://localhost:11434/v1")
MODEL_NAME = os.getenv("MODEL_NAME", "llama3.2")


def get_model():
    """Get the chat model configured for OpenAI-compatible endpoint."""
    return ChatOpenAI(
        model=MODEL_NAME,
        base_url=OPENAI_API_BASE,
        api_key=os.getenv("OPENAI_API_KEY", "not-needed"),  # For local models
        temperature=0.7,
    )


async def validate_payment_node(
    state: AgentState, 
    config: RunnableConfig
) -> dict[str, Any]:
    """
    Validate the ecash token WITHOUT redeeming it.
    
    Development mode: Accept all tokens without validation.
    Production: Call backend wallet service to validate.
    """
    run_id = state.get("run_id") or str(uuid.uuid4())
    payment = state.get("payment")
    
    # Development mode: no payment required
    if not payment or not payment.get("ecash_token"):
        print("[Payment] No payment token provided, skipping validation (free mode)")
        return {
            "payment_validated": True,
            "payment_token": None,
            "refund": False,
            "run_id": run_id,
        }
    
    token = payment["ecash_token"]
    amount_sats = payment.get("amount_sats", 0)
    
    # Debug mode: accept fake tokens for testing
    if token.startswith("cashu_debug_") or token == "debug":
        print("[Payment] DEBUG MODE - accepting fake token for testing")
        return {
            "payment_validated": True,
            "payment_token": None,
            "refund": False,
            "run_id": run_id,
        }
    
    print(f"[Payment] Validating token for {amount_sats} sats")
    
    # Development: Accept all tokens without actually validating
    # TODO: In production, call backend wallet service
    # try:
    #     async with httpx.AsyncClient() as client:
    #         response = await client.post(
    #             f"{WALLET_URL}/api/wallet/validate",
    #             json={"token": token},
    #             timeout=30.0,
    #         )
    #         if response.status_code == 200:
    #             result = response.json()
    #             if result.get("valid"):
    #                 return {
    #                     "payment_validated": True,
    #                     "payment_token": token,
    #                     "refund": False,
    #                     "run_id": run_id,
    #                 }
    # except Exception as e:
    #     print(f"[Payment] Validation error: {e}")
    
    # For now, accept all tokens
    print("[Payment] DEV MODE - accepting token without validation")
    return {
        "payment_validated": True,
        "payment_token": token,
        "refund": False,
        "run_id": run_id,
    }


async def agent_node(
    state: AgentState,
    config: RunnableConfig
) -> dict[str, Any]:
    """Main agent node that processes user messages."""
    
    model = get_model()
    messages = list(state.get("messages", []))
    
    # Build system prompt
    system_prompt = """You are a Socratic dialogue assistant. Your role is to:

1. Help users develop and refine their arguments through thoughtful questioning
2. Assist with writing and editing documents, especially structured arguments
3. Help create and modify artifacts (documents, code, structured seminars)

When helping with Socratic Seminar documents, follow the structure:
- Thesis: A clear, arguable statement
- Supporting Clauses: Arguments with definitions, citations, and narratives
- Refutations: Counter-arguments addressed honestly
- Replies: Responses that strengthen the original argument

Be helpful, thoughtful, and encourage critical thinking."""

    # Prepend system message if not already present
    if not messages or not isinstance(messages[0], SystemMessage):
        messages = [SystemMessage(content=system_prompt)] + messages
    
    # Get artifact context if available
    artifact = state.get("artifact")
    if artifact:
        current_content = None
        if artifact.get("contents") and artifact.get("current_index") is not None:
            idx = artifact["current_index"]
            if 0 <= idx < len(artifact["contents"]):
                current_content = artifact["contents"][idx]
        
        if current_content:
            context_msg = f"\n\nCurrent artifact ({current_content['type']}):\nTitle: {current_content['title']}\n\n{current_content['content']}"
            # Add context to last human message or system
            if messages and isinstance(messages[-1], HumanMessage):
                messages[-1] = HumanMessage(
                    content=str(messages[-1].content) + context_msg
                )
    
    # Invoke the model
    response = await model.ainvoke(messages)
    
    return {"messages": [response]}


async def redeem_payment_node(
    state: AgentState,
    config: RunnableConfig
) -> dict[str, Any]:
    """Redeem the payment token after successful agent execution."""
    
    payment_token = state.get("payment_token")
    
    if not payment_token:
        print("[Payment] No token to redeem")
        return {}
    
    print(f"[Payment] Redeeming token...")
    
    # TODO: In production, call backend wallet service
    # try:
    #     async with httpx.AsyncClient() as client:
    #         response = await client.post(
    #             f"{WALLET_URL}/api/wallet/receive",
    #             json={"token": payment_token},
    #             timeout=30.0,
    #         )
    #         if response.status_code == 200:
    #             result = response.json()
    #             print(f"[Payment] Redeemed {result.get('amount', 0)} sats")
    # except Exception as e:
    #     print(f"[Payment] Redemption error: {e}")
    
    # For now, just log
    print("[Payment] DEV MODE - token redemption skipped")
    return {"payment_token": None}


def route_after_validation(
    state: AgentState
) -> Literal["agent", "end"]:
    """Route based on payment validation result."""
    
    if state.get("payment_validated", False):
        return "agent"
    else:
        print("[Payment] Validation failed, ending run")
        return "end"

