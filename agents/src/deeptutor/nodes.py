"""Node implementations for the Deeptutor Agent.

Contains payment validation and redemption nodes that wrap
the core agent functionality.
"""

import os
import uuid
from typing import Any, Literal

from langgraph.config import RunnableConfig

from .state import DeeptutorState, ProjectFile


# Configuration
WALLET_URL = os.getenv("WALLET_URL", "http://localhost:8000")


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
        # System prompt doesn't have access to dynamic state, so instruct model to discover files
        base_prompt += "\n\n## Project Files\n\nUse list_files() to discover available files. The project may contain files that you should discover before attempting to answer file-related questions."

    return base_prompt


async def validate_payment_node(
    state: DeeptutorState, 
    config: RunnableConfig
) -> dict[str, Any]:
    """Validate the ecash token WITHOUT redeeming it.
    
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
    print("[Payment] DEV MODE - accepting token without validation")
    return {
        "payment_validated": True,
        "payment_token": token,
        "refund": False,
        "run_id": run_id,
    }


async def redeem_payment_node(
    state: DeeptutorState,
    config: RunnableConfig
) -> dict[str, Any]:
    """Redeem the payment token after successful agent execution."""
    
    payment_token = state.get("payment_token")
    
    if not payment_token:
        print("[Payment] No token to redeem")
        return {}
    
    print(f"[Payment] Redeeming token...")
    
    # TODO: In production, call backend wallet service
    print("[Payment] DEV MODE - token redemption skipped")
    return {"payment_token": None}


def route_after_validation(
    state: DeeptutorState
) -> Literal["agent", "end"]:
    """Route based on payment validation result."""
    
    if state.get("payment_validated", False):
        return "agent"
    else:
        print("[Payment] Validation failed, ending run")
        return "end"

