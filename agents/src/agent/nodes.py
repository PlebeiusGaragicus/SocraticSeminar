"""Node implementations for the Seminar Agent."""

import os
import uuid
from typing import Any, Literal

import httpx
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from langgraph.config import RunnableConfig

from .state import AgentState, ProjectFile
from .tools import CLIENT_TOOLS


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


def build_system_prompt(project_files: list[ProjectFile] | None = None) -> str:
    """Build the system prompt with available tools and project files.
    
    Args:
        project_files: List of file metadata from the current project.
                       Injected on each invocation so it's always current.
    """
    base_prompt = """You are a Socratic dialogue assistant with access to the user's project files.

## Your Role

1. Help users develop and refine their arguments through thoughtful questioning
2. Assist with writing and editing documents, especially structured arguments
3. Help create and modify artifacts (documents, code, structured seminars)

## Socratic Seminar Document Structure

When helping with Socratic Seminar documents, follow this structure:
- **Thesis**: A clear, arguable statement
- **Supporting Clauses**: Arguments with definitions, citations, and narratives
- **Refutations**: Counter-arguments addressed honestly
- **Replies**: Responses that strengthen the original argument

## Available Tools

You have access to tools for working with project files:

- **list_files()**: List all files in the current project. Returns file metadata (id, title, type).
- **get_file(file_id)**: Read the full content of a file by its ID.
- **search_files(query, top_k)**: Semantic search across all project files. Returns relevant excerpts.
- **edit_file(file_id, new_content, edit_description)**: Propose edits to a file. User must approve changes.

## How to Use Tools

1. **Before reading files**: Check if file content is needed to answer the question
2. **Use get_file()**: When you need the full content of a specific file
3. **Use search_files()**: When looking for specific topics or content across files
4. **Use edit_file()**: Only when the user explicitly asks for changes to a file

## Citation Format

When referencing content from files, cite with the file title:
- "According to [[File Title]], the author argues..."
- Use quotes for direct excerpts

## Guidelines

- Be helpful, thoughtful, and encourage critical thinking
- Ask clarifying questions when the user's intent is unclear
- When editing files, explain your changes clearly
- Don't read files unless necessary - use the file list below first"""

    # Add project files list if available
    if project_files and len(project_files) > 0:
        files_section = "\n\n## Project Files\n\nThe following files are available in this project:\n\n"
        for f in project_files:
            files_section += f"- **{f['title']}** (id: `{f['id']}`, type: {f['file_type']})\n"
        files_section += "\nUse the file IDs above with get_file() to read content."
        base_prompt += files_section
    else:
        base_prompt += "\n\n## Project Files\n\nNo files are currently in this project. The user can create files which will then be available via tools."

    return base_prompt


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
    """Main agent node that processes user messages.
    
    Binds tools to the model and builds a dynamic system prompt
    that includes the list of available project files.
    """
    model = get_model()
    
    # Bind tools to the model
    model_with_tools = model.bind_tools(CLIENT_TOOLS)
    
    messages = list(state.get("messages", []))
    
    # Build dynamic system prompt with project files
    project_files = state.get("project_files")
    system_prompt = build_system_prompt(project_files)
    
    # Prepend system message if not already present
    if not messages or not isinstance(messages[0], SystemMessage):
        messages = [SystemMessage(content=system_prompt)] + messages
    else:
        # Update existing system message with current file list
        messages[0] = SystemMessage(content=system_prompt)
    
    # Get artifact context if available (legacy support)
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
    
    # Log tool availability
    has_files = bool(project_files and len(project_files) > 0)
    print(f"[Agent] Invoking LLM with tools. Project files: {len(project_files) if project_files else 0}")
    
    # Invoke the model with tools
    response = await model_with_tools.ainvoke(messages)
    
    # Log if tool calls were made
    if hasattr(response, 'tool_calls') and response.tool_calls:
        tool_names = [tc['name'] for tc in response.tool_calls]
        print(f"[Agent] Tool calls requested: {tool_names}")
    
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

