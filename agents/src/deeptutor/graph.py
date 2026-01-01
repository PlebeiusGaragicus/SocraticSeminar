"""Deeptutor Agent using proper deepagent middleware conventions.

Architecture:
- Uses create_agent() with middleware composition
- CashuPaymentMiddleware: Streaming micropayments with per-iteration deduction
- TodoListMiddleware: Task tracking for complex multi-step operations
- ClarifyWithHumanMiddleware: Ask user for intent clarification
- ClientToolsMiddleware: Client-side file operations via interrupts
- HumanInTheLoopMiddleware: Approval for funding requests

The agent operates with:
1. Two file systems: User's project files (client) and agent working memory (server)
2. Streaming Cashu payments (deducted per LLM iteration)
3. Human approval for funding requests
4. Clarification tools when user intent is unclear
"""

import os
from typing import Any

from langchain.agents import create_agent
from langchain.agents.middleware import HumanInTheLoopMiddleware, TodoListMiddleware
from langchain.agents.middleware.types import AgentMiddleware
from langchain_anthropic import ChatAnthropic
from langchain_openai import ChatOpenAI
from langgraph.graph.state import CompiledStateGraph
from langgraph.types import Checkpointer

from src.middleware import (
    CashuPaymentMiddleware, 
    ClientToolsMiddleware, 
    ClarifyWithHumanMiddleware,
    ThinkingMiddleware,
    ToolValidationMiddleware,
)
from .state import DeeptutorState, COST_PER_ITERATION_SATS


# =============================================================================
# CONFIGURATION
# =============================================================================

# LLM Configuration
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "openai")  # "openai" or "anthropic"
LLM_MODEL = os.getenv("LLM_MODEL", "gpt-4o")
LLM_BASE_URL = os.getenv("LLM_BASE_URL")  # Optional: for OpenAI-compatible endpoints
LLM_API_KEY = os.getenv("LLM_API_KEY", os.getenv("OPENAI_API_KEY", ""))

# Payment Configuration
PAYMENT_COST_PER_ITERATION = int(os.getenv("COST_PER_ITERATION_SATS", str(COST_PER_ITERATION_SATS)))


# =============================================================================
# MODEL FACTORY
# =============================================================================

def get_model():
    """Get the configured chat model.
    
    Supports:
    - OpenAI (default): gpt-4o, gpt-4-turbo, etc.
    - Anthropic: claude-3-5-sonnet, claude-3-opus, etc.
    - OpenAI-compatible: Any endpoint with LLM_BASE_URL
    """
    if LLM_PROVIDER == "anthropic":
        return ChatAnthropic(
            model_name=LLM_MODEL,
            max_tokens=8192,
        )
    else:
        # OpenAI or OpenAI-compatible
        kwargs = {
            "model": LLM_MODEL,
            "temperature": 0.7,
        }
        if LLM_BASE_URL:
            kwargs["base_url"] = LLM_BASE_URL
        if LLM_API_KEY:
            kwargs["api_key"] = LLM_API_KEY
        
        return ChatOpenAI(**kwargs)


# =============================================================================
# SYSTEM PROMPT
# =============================================================================

DEEPTUTOR_SYSTEM_PROMPT = """You are a Socratic dialogue assistant helping users develop and refine their arguments.

## Your Role

1. Help users develop arguments through thoughtful questioning
2. Assist with writing and editing documents, especially structured arguments
3. Create and modify artifacts (documents, code, structured seminars)

## Autonomous Execution

When you have a clear task, work through it autonomously:
- If you create a todo list, continue working through it immediately
- Don't stop to ask questions unless genuinely blocked
- Provide drafts and outputs, then ask for feedback
- Prefer action over clarification when the path forward is reasonably clear

### When to Stop vs Continue

**Continue working** when:
- You have todos and can make progress on the next one
- You can produce a draft or output
- The user's intent is reasonably clear

**Stop and ask** (using `ask_user` or `ask_choices` tools) when:
- You genuinely cannot proceed without user input
- Multiple fundamentally different approaches exist
- The user's request is truly ambiguous

**IMPORTANT**: If you need to ask a question, use the `ask_user()` or `ask_choices()` tools.
Do NOT ask questions in your text response - this ends your turn and interrupts your workflow.

## Socratic Seminar Document Structure

When helping with Socratic Seminar documents, follow this structure:
- **Thesis**: A clear, arguable statement
- **Supporting Clauses**: Arguments with definitions, citations, and narratives
- **Refutations**: Counter-arguments addressed honestly
- **Replies**: Responses that strengthen the original argument

## Two File Systems

You have access to TWO separate file systems:

### 1. User's Project Files (Client-side)
These are the user's actual documents stored in their browser. Use these tools:
- `list_files(file_type?)` - List user's files, optionally filtered
- `read_file(file_id)` - Read a user file
- `search_files(query)` - Semantic search across user files
- `grep_files(pattern)` - Pattern search in file contents
- `glob_files(pattern)` - Find files by name pattern
- `write_file(title, content)` - Create new file
- `patch_file(file_id, search, replace)` - Edit a specific portion of a file

### 2. Your Working Memory (Server-side)
Ephemeral storage for your notes, analysis, and drafts. Use these tools:
- `ls(path)` - List files in your working memory
- `read_file(file_path)` - Read from working memory
- `write_file(file_path, content)` - Write to working memory (no approval needed)
- `edit_file(file_path, old_string, new_string)` - Edit working memory files
- `grep(pattern)` / `glob(pattern)` - Search working memory

Use working memory at paths like `/scratch/`, `/summaries/`, `/analysis/` to:
- Store intermediate analysis and notes
- Draft content before presenting to user
- Keep track of research findings within a session

## Guidelines

- Be helpful, thoughtful, and encourage critical thinking
- Use `ask_user()` or `ask_choices()` tools when you need user input - don't ask in text
- When editing user files, explain your changes clearly
- Use `list_files()` first to discover available files
- Read files before attempting to edit them

## Citation Format

When referencing content from files, cite with the file title:
- "According to [[File Title]], the author argues..."
- Use quotes for direct excerpts"""


# =============================================================================
# AGENT FACTORY
# =============================================================================

def create_deeptutor_agent(
    *,
    checkpointer: Checkpointer | None = None,
    cost_per_iteration: int = PAYMENT_COST_PER_ITERATION,
    additional_middleware: list[AgentMiddleware] | None = None,
    debug: bool = False,
) -> CompiledStateGraph:
    """Create the Deeptutor agent with all middleware.
    
    Middleware Stack (in order):
    1. CashuPaymentMiddleware - Payment validation and per-iteration deduction
    2. TodoListMiddleware - Task tracking for complex operations
    3. ClarifyWithHumanMiddleware - Ask user for intent clarification
    5. ClientToolsMiddleware - File operations via client interrupts
    6. HumanInTheLoopMiddleware - Approval for writes and funding
    7. Any additional middleware
    
    Args:
        checkpointer: Optional checkpointer for persistence
        cost_per_iteration: Satoshis per LLM iteration (default: 10)
        additional_middleware: Extra middleware to add after standard ones
        debug: Enable debug logging
        
    Returns:
        Compiled agent graph ready for invoke/stream
        
    Example:
        ```python
        from langgraph.checkpoint.memory import MemorySaver
        
        agent = create_deeptutor_agent(
            checkpointer=MemorySaver(),
            cost_per_iteration=10,
        )
        
        # Start a session with payment
        result = await agent.ainvoke({
            "messages": [HumanMessage(content="Help me with my argument")],
            "payment_token": "cashuA...",
        })
        ```
    """
    model = get_model()
    
    # Build middleware stack
    #
    # NOTE: ClientToolsMiddleware handles ALL file tool interrupts.
    # 
    middleware: list[AgentMiddleware] = [
        # 1. Payment middleware - validates token, tracks balance, deducts per iteration
        CashuPaymentMiddleware(cost_per_iteration=cost_per_iteration),
        
        # 2. Tool Validation - catch and correct malformed tool calls immediately
        ToolValidationMiddleware(),
        
        # 3. Todo list - task tracking for complex multi-step operations
        TodoListMiddleware(),

        # 3. Clarification tools - ask user for intent clarification
        ClarifyWithHumanMiddleware(),

        # 5. Client tools - ALL file operations interrupt for client-side execution
        ClientToolsMiddleware(),

        # 6. Thinking - Strategic reflection
        ThinkingMiddleware(),
        
        # 7. Human-in-the-loop - ONLY for payment funding requests
        #    File operations are handled by ClientToolsMiddleware above
        HumanInTheLoopMiddleware(
            interrupt_on={
                "request_additional_funding": True,
            }
        ),
    ]
    
    # Add any additional middleware
    if additional_middleware:
        middleware.extend(additional_middleware)
    
    # Create the agent
    agent = create_agent(
        model,
        system_prompt=DEEPTUTOR_SYSTEM_PROMPT,
        tools=[],  # Tools provided by middleware
        middleware=middleware,
        checkpointer=checkpointer,
        debug=debug,
    )
    
    return agent


# =============================================================================
# GRAPH EXPORT
# =============================================================================

# Default graph for LangGraph deployment
# Uses in-memory checkpointing; production should use persistent checkpointer
graph = create_deeptutor_agent()
