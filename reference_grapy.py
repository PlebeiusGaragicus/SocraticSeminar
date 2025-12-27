"""LangGraph agent for the SvelteReader AI chat assistant.

This agent helps users discuss and analyze passages from their ebooks.
It receives context about highlighted text and user notes, then provides
intelligent responses about the content.

Architecture: Agent-Driven RAG with Client-Side Tool Execution
1. Agent decides when to search/retrieve from the book
2. Tools are defined as stubs - execution happens on the client
3. Graph uses interrupt_before=["tools"] to pause before tool execution
4. Client executes tools locally (EPUB access, vector search)
5. Client resumes graph with tool results

Payment flow (validate-then-redeem-on-success):
1. Client sends ecash token with message
2. validate_payment node checks token is UNSPENT (doesn't redeem)
3. agent node processes the LLM request (may call tools)
4. On SUCCESS: redeem token to wallet
5. On FAILURE: don't redeem, return refund flag so client can self-recover

See docs/ecash-payment-flow.md for full payment design.
"""

from __future__ import annotations

import os
import httpx
import json
import base64
import uuid
from typing import Annotated, Literal, TypedDict

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from langgraph.graph import END, StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode

from agent.logging import agent_logger


def get_thread_id(config: RunnableConfig | None) -> str:
    """Extract thread_id from LangGraph config."""
    if config is None:
        return "unknown"
    configurable = config.get("configurable", {})
    return configurable.get("thread_id", "unknown")


# =============================================================================
# TOOL DEFINITIONS (Client-Executed)
# These tools are stubs - the actual execution happens on the client.
# The graph interrupts before the tools node, client executes, then resumes.
# =============================================================================

@tool
def get_chapter(chapter_id: str) -> str:
    """Read a chapter's full text content.
    
    IMPORTANT: Use the EXACT chapter_id from the Table of Contents in your system prompt.
    The chapter_id is shown in parentheses after each chapter title.
    
    Args:
        chapter_id: The exact chapter_id from the Table of Contents (e.g., "np-5", "chapter-1")
    
    Returns: 
        The chapter's full text content. Long chapters may be truncated.
        
    Errors:
        - "not found": The chapter_id doesn't exist - check the TOC for valid IDs
        - "empty content": This chapter has no text (may be a cover or title page) - try a different chapter
        - "not loaded": The book needs to be re-opened in the reader
    """
    return ""


@tool
def search_book(queries: list[str], top_k: int = 5) -> str:
    """Semantic search across the entire book to find relevant passages.
    
    IMPORTANT: Provide multiple search queries (2-4) to maximize chances of finding relevant content.
    Each query should approach the topic from a different angle.
    
    Best for finding:
    - Specific topics or themes
    - Key concepts and arguments
    - Particular discussions or examples
    
    Args:
        queries: List of 2-4 search queries approaching the topic from different angles.
                 Example: ["propaganda techniques", "disinformation tactics", "online manipulation methods"]
        top_k: Number of results per query (default 5, max 10)
    
    Returns: 
        Relevant text passages with chapter locations and relevance scores.
        Results are deduplicated across queries.
        
    Errors:
        - "no results": No matching passages found - try different search terms
        - "not indexed": The book hasn't been indexed yet - use get_chapter() instead
    """
    return ""


@tool
def get_current_page() -> str:
    """Get what the user is currently reading.
    
    Returns the user's current reading position including:
    - Current chapter title
    - Progress through the book (percentage)
    - The visible text on the current page
    
    Use this to understand what the user is currently looking at,
    especially when they ask questions like "what does this mean?"
    or refer to "this page" or "this part".
    """
    return ""


# All tools that require client-side execution
CLIENT_TOOLS = [get_chapter, search_book, get_current_page]


# =============================================================================
# STATE DEFINITIONS
# =============================================================================

class PaymentInfo(TypedDict, total=False):
    """Payment information from client."""
    ecash_token: str  # Cashu ecash token
    amount_sats: int  # Expected amount in sats
    mint: str | None  # Mint URL


class PassageContext(TypedDict, total=False):
    """Context about the passage being discussed."""
    text: str  # The highlighted text from the book
    note: str | None  # User's note about the passage
    book_title: str | None  # Title of the book
    chapter: str | None  # Current chapter


class AgentState(TypedDict):
    """State for the reader assistant agent."""
    messages: Annotated[list[BaseMessage], add_messages]
    passage_context: PassageContext | None
    book_id: str | None  # Current book ID for tool execution
    book_context: str | None  # Pre-formatted book context (TOC, metadata) from client
    payment: PaymentInfo | None
    payment_validated: bool  # Token checked but not redeemed
    payment_token: str | None  # Token to redeem on success
    refund: bool  # Signal client to self-redeem on error
    run_id: str | None  # Unique ID for this run (for logging)


# =============================================================================
# SYSTEM PROMPT
# =============================================================================

def get_system_prompt(
    passage_context: PassageContext | None,
    book_context: str | None
) -> str:
    """Generate a system prompt based on the passage and book context."""
    base_prompt = """You are a reading assistant with access to the user's ebook.

## Available Tools

- **get_chapter(chapter_id)**: Read a chapter's full text. Use the EXACT chapter_id from the Table of Contents below.
- **search_book(queries)**: Semantic search with multiple queries (2-4) for better results. Example: ["topic phrase 1", "related concept", "alternative wording"].
- **get_current_page()**: Get what the user is currently reading (chapter, visible text). Use when user says "this page" or "what does this mean?".

## How to Answer Questions

**For summarization requests** (e.g., "summarize chapter 3"):
1. Look up the chapter_id in the Table of Contents below
2. Call get_chapter(chapter_id) with that EXACT ID
3. Summarize the returned content

**For topic/quote searches** (e.g., "where does the author discuss X?"):
1. Call search_book("relevant keywords")
2. Review the results and cite the chapters where the topic appears

**For questions about specific passages**:
1. Check if passage context is provided below
2. If not, use search_book() to find relevant sections

## Critical Rules

1. **ALWAYS explain first**: Before calling any tool, briefly tell the user what you're about to do (e.g., "Let me read that chapter..." or "I'll search for that topic..."). This helps users understand your process.
2. **Use EXACT chapter_ids** from the Table of Contents - don't guess or modify them
3. **Handle errors gracefully**: If a tool returns an error, explain the issue to the user rather than retrying endlessly
4. **Maximum 3 tool calls** for simple requests - don't loop trying different approaches
5. **If content is unavailable**: Tell the user honestly rather than making up information
6. **Cite sources with clickable references**: See Citation Format below

## Citation Format

When referencing content from the book, use this exact format to create clickable citations:

**Format**: `[[chapter_id|"quoted text excerpt"]]`

**Examples**:
- `[[chapter-3|"The fundamental principle of liberty..."]]`
- `[[np-5|"propaganda relies on repetition"]]`

**Rules for citations**:
1. Use the EXACT chapter_id from the Table of Contents or search results
2. Quote a short, distinctive text excerpt (10-50 words) that can be found in the chapter
3. Citations become clickable links that navigate to the exact passage
4. Include at least one citation when answering questions based on specific passages
5. For search results, use the chapter_id shown in brackets (e.g., `[chapter-3]`)

**When to cite**:
- After using search_book(): cite the relevant passages you found
- After using get_chapter(): cite key excerpts that answer the question
- When discussing specific quotes or ideas from the book

## Error Handling

- If get_chapter returns an error about "not found" or "empty content", that chapter may be a title page or section header - try a different chapter
- If search_book returns "no results", the search index may not be ready - suggest the user try again later
- If tools consistently fail, apologize and explain the technical limitation

Be concise, accurate, and honest about limitations."""

    # Add book context (TOC, metadata) - this is the key info the agent needs
    if book_context:
        base_prompt += f"\n\n=== BOOK INFORMATION ===\n{book_context}\n=== END BOOK INFO ==="

    # Add passage context if user highlighted text
    if passage_context:
        context_parts = []
        if passage_context.get("book_title"):
            context_parts.append(f"Book: {passage_context['book_title']}")
        if passage_context.get("chapter"):
            context_parts.append(f"Current Chapter: {passage_context['chapter']}")
        if passage_context.get("text"):
            context_parts.append(f'\nHighlighted passage:\n"{passage_context["text"]}"')
        if passage_context.get("note"):
            context_parts.append(f"\nUser's note: {passage_context['note']}")

        if context_parts:
            base_prompt += "\n\n--- User's Current Selection ---\n" + "\n".join(context_parts)

    return base_prompt


# =============================================================================
# MODEL CREATION
# =============================================================================

def create_model():
    """Create the LLM model using OpenAI-compatible endpoint.

    Requires explicit configuration - does NOT default to OpenAI.
    Works with any OpenAI-compatible API (Ollama, vLLM, LM Studio, etc.)
    """
    base_url = os.getenv("LLM_BASE_URL")
    api_key = os.getenv("LLM_API_KEY")
    model_name = os.getenv("LLM_MODEL")

    if not base_url:
        raise ValueError(
            "LLM_BASE_URL environment variable is required. "
            "Set it to your OpenAI-compatible endpoint (e.g., http://localhost:11434/v1 for Ollama)"
        )

    if not model_name:
        raise ValueError(
            "LLM_MODEL environment variable is required. "
            "Set it to your model name (e.g., llama3.2, mistral, etc.)"
        )

    return ChatOpenAI(
        base_url=base_url,
        api_key=api_key or "not-needed",  # Some endpoints don't require a key
        model=model_name,
        temperature=0.7,
        streaming=True,
    )


# =============================================================================
# PAYMENT VALIDATION
# =============================================================================

def validate_token_format(token: str) -> bool:
    """Validate that a string looks like a valid Cashu token.
    
    Cashu tokens have two formats:
    - cashuA: base64url encoded JSON
    - cashuB: base64url encoded CBOR (binary)
    
    We just check the prefix and that it's valid base64url.
    Actual validation happens when nutstash tries to redeem it.
    """
    try:
        if not (token.startswith("cashuA") or token.startswith("cashuB")):
            print(f"[Payment] Unknown token format: {token[:10]}...")
            return False
        
        token_data = token[6:]
        padding = 4 - len(token_data) % 4
        if padding != 4:
            token_data += "=" * padding
        
        decoded = base64.urlsafe_b64decode(token_data)
        
        if len(decoded) < 10:
            print("[Payment] Token data too short")
            return False
        
        token_type = "CBOR" if token.startswith("cashuB") else "JSON"
        print(f"[Payment] Token format valid: {token_type}, {len(decoded)} bytes")
        return True
        
    except Exception as e:
        print(f"[Payment] Token format validation failed: {e}")
        return False


async def validate_token_state(token: str) -> tuple[bool, str | None]:
    """Validate that a Cashu token has valid format."""
    if not validate_token_format(token):
        return False, None
    print("[Payment] Token format validated, will attempt redemption on success")
    return True, None


async def redeem_token_to_wallet(token: str) -> bool:
    """Redeem a Cashu token to the backend wallet service."""
    wallet_url = os.getenv("WALLET_URL", "http://localhost:8000/api/wallet")
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{wallet_url}/receive",
                json={"token": token},
                timeout=30.0,
            )
            
            if response.status_code == 200:
                result = response.json()
                if result.get("success"):
                    amount = result.get("amount", 0)
                    print(f"[Payment] Successfully redeemed {amount} sats to wallet")
                    return True
                else:
                    print(f"[Payment] Wallet rejected token: {result.get('error')}")
                    return False
            else:
                print(f"[Payment] Failed to redeem: {response.text}")
                return False
                
    except Exception as e:
        print(f"[Payment] Redemption error: {e}")
        return False


# =============================================================================
# GRAPH NODES
# =============================================================================

async def validate_payment_node(state: AgentState, config: RunnableConfig) -> dict:
    """Validate the ecash token WITHOUT redeeming it."""
    # Get thread_id and run_id for logging
    thread_id = get_thread_id(config)
    run_id = state.get("run_id") or str(uuid.uuid4())
    
    # Extract first human message for logging
    messages = state.get("messages", [])
    first_message = ""
    for msg in messages:
        if isinstance(msg, HumanMessage):
            first_message = msg.content if isinstance(msg.content, str) else str(msg.content)
            break
    
    # Log run start
    agent_logger.log_run_start(
        thread_id=thread_id,
        run_id=run_id,
        message=first_message,
        book_context=state.get("book_context"),
        passage_context=state.get("passage_context"),
        payment=state.get("payment"),
    )
    
    payment = state.get("payment")
    
    # If no payment provided, skip validation (free mode for development)
    if not payment or not payment.get("ecash_token"):
        print("[Payment] No payment token provided, skipping validation (free mode)")
        agent_logger.log_payment(thread_id, run_id, "skipped", amount_sats=0)
        return {
            "payment_validated": True,
            "payment_token": None,
            "refund": False,
            "run_id": run_id,
        }
    
    token = payment["ecash_token"]
    amount_sats = payment.get("amount_sats", 0)
    
    # Debug mode: accept fake tokens for testing without losing funds
    if token.startswith("cashu_debug_") or token == "debug":
        print("[Payment] DEBUG MODE - accepting fake token for testing")
        agent_logger.log_payment(thread_id, run_id, "debug_mode", amount_sats=amount_sats)
        return {
            "payment_validated": True,
            "payment_token": None,  # Don't try to redeem debug tokens
            "refund": False,
            "run_id": run_id,
        }
    
    print(f"[Payment] ========== RECEIVED TOKEN (for recovery) ==========")
    print(f"[Payment] {token}")
    print(f"[Payment] ====================================================")
    
    is_valid, mint_url = await validate_token_state(token)
    
    if not is_valid:
        print("[Payment] Token validation failed - client should still have valid token")
        agent_logger.log_payment(thread_id, run_id, "validation_failed", amount_sats=amount_sats, token_preview=token)
        return {
            "payment_validated": False,
            "payment_token": None,
            "refund": True,
            "run_id": run_id,
        }
    
    print(f"[Payment] Token validated, will redeem on success")
    agent_logger.log_payment(thread_id, run_id, "validated", amount_sats=amount_sats, token_preview=token)
    return {
        "payment_validated": True,
        "payment_token": token,
        "refund": False,
        "run_id": run_id,
    }


async def agent_node(state: AgentState, config: RunnableConfig) -> dict:
    """Process the user's message with the LLM.
    
    The model has access to tools for book retrieval.
    Tool calls will cause an interrupt - client executes them.
    """
    thread_id = get_thread_id(config)
    run_id = state.get("run_id", "unknown")
    
    if not state.get("payment_validated", True):
        agent_logger.log_run_end(thread_id, run_id, success=False, error="Payment validation failed", refund=True)
        return {
            "messages": [AIMessage(content="Payment validation failed. Please try again with a valid ecash token.")],
            "refund": True,
        }
    
    try:
        model = create_model()
        
        # Bind tools to the model
        model_with_tools = model.bind_tools(CLIENT_TOOLS)
        
        # Build messages with system prompt (includes book context with TOC)
        system_prompt = get_system_prompt(
            state.get("passage_context"),
            state.get("book_context")
        )
        messages = [SystemMessage(content=system_prompt)] + state["messages"]
        
        # Log book context availability for debugging
        has_book_context = bool(state.get("book_context"))
        print(f"[Agent] Invoking LLM... (book_context: {has_book_context})")
        response = await model_with_tools.ainvoke(messages)
        print(f"[Agent] LLM response received. Has tool calls: {bool(response.tool_calls)}")
        
        # Log the LLM response
        tool_calls_for_log = None
        if response.tool_calls:
            tool_calls_for_log = [{"name": tc["name"], "args": tc["args"]} for tc in response.tool_calls]
        
        agent_logger.log_llm_response(
            thread_id=thread_id,
            run_id=run_id,
            content=response.content if isinstance(response.content, str) else str(response.content),
            tool_calls=tool_calls_for_log,
            finish_reason=response.response_metadata.get("finish_reason") if hasattr(response, "response_metadata") else None,
        )
        
        return {"messages": [response]}
        
    except Exception as e:
        print(f"[Agent] LLM processing failed: {e}")
        agent_logger.log_run_end(thread_id, run_id, success=False, error=str(e), refund=True)
        token = state.get("payment_token")
        if token:
            print("[Payment] ========== REFUNDABLE TOKEN ==========")
            print(f"[Payment] {token}")
            print("[Payment] ========================================")
        return {
            "messages": [AIMessage(content=f"Sorry, I encountered an error processing your request. Your payment has not been taken - please try again.")],
            "refund": True,
        }


async def finalize_node(state: AgentState, config: RunnableConfig) -> dict:
    """Finalize the conversation and redeem payment if successful."""
    thread_id = get_thread_id(config)
    run_id = state.get("run_id", "unknown")
    token = state.get("payment_token")
    
    if token:
        print("[Payment] Attempting to redeem token to wallet...")
        redeemed = await redeem_token_to_wallet(token)
        if not redeemed:
            print("[Payment] !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
            print("[Payment] WARNING: Conversation succeeded but token redemption failed!")
            print("[Payment] UNREDEEMED TOKEN - MANUAL RECOVERY NEEDED:")
            print(f"[Payment] {token}")
            print("[Payment] !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
            agent_logger.log_payment(thread_id, run_id, "redemption_failed", token_preview=token)
        else:
            print("[Payment] Token redeemed successfully")
            agent_logger.log_payment(thread_id, run_id, "redeemed", token_preview=token)
    
    # Get final response for logging
    messages = state.get("messages", [])
    final_response = None
    if messages:
        last_msg = messages[-1]
        if isinstance(last_msg, AIMessage):
            final_response = last_msg.content if isinstance(last_msg.content, str) else str(last_msg.content)
    
    agent_logger.log_run_end(
        thread_id=thread_id,
        run_id=run_id,
        final_response=final_response,
        success=True,
        refund=False,
    )
    
    return {"refund": False}


# =============================================================================
# GRAPH ROUTING
# =============================================================================

def route_after_validation(state: AgentState) -> Literal["agent", "end"]:
    """Route based on payment validation result."""
    if state.get("payment_validated", True):
        return "agent"
    return "end"


def should_continue(state: AgentState, config: RunnableConfig) -> Literal["tools", "finalize"]:
    """Determine if the agent wants to call tools or is done."""
    thread_id = get_thread_id(config)
    run_id = state.get("run_id", "unknown")
    messages = state.get("messages", [])
    if not messages:
        return "finalize"
    
    last_message = messages[-1]
    
    # Log any tool results that have come back from the client
    for msg in messages:
        if isinstance(msg, ToolMessage):
            # Parse the content to check for errors
            content = msg.content if isinstance(msg.content, str) else str(msg.content)
            error = None
            if content.startswith('{"error":') or '"error":' in content:
                try:
                    parsed = json.loads(content)
                    error = parsed.get("error")
                except:
                    pass
            
            agent_logger.log_tool_call(
                thread_id=thread_id,
                run_id=run_id,
                tool_name=msg.name or "unknown",
                args={},  # Args were logged when tool was called
                result=content if not error else None,
                error=error,
            )
    
    # Check if the last message has tool calls
    if hasattr(last_message, "tool_calls") and last_message.tool_calls:
        print(f"[Agent] Tool calls detected: {[tc['name'] for tc in last_message.tool_calls]}")
        # Log the interrupt
        agent_logger.log_tool_interrupt(
            thread_id=thread_id,
            run_id=run_id,
            tool_calls=last_message.tool_calls,
        )
        return "tools"
    
    return "finalize"


def route_after_tools(state: AgentState) -> Literal["agent"]:
    """After tools execute, always go back to agent for next step."""
    return "agent"


# =============================================================================
# GRAPH CONSTRUCTION
# =============================================================================

# Create tool node for client-executed tools
tool_node = ToolNode(CLIENT_TOOLS)

# Build the graph
builder = StateGraph(AgentState)

# Add nodes
builder.add_node("validate_payment", validate_payment_node)
builder.add_node("agent", agent_node)
builder.add_node("tools", tool_node)
builder.add_node("finalize", finalize_node)

# Add edges
builder.add_edge("__start__", "validate_payment")
builder.add_conditional_edges(
    "validate_payment",
    route_after_validation,
    {"agent": "agent", "end": END},
)
builder.add_conditional_edges(
    "agent",
    should_continue,
    {"tools": "tools", "finalize": "finalize"},
)
builder.add_edge("tools", "agent")
builder.add_edge("finalize", END)

# Compile the graph WITH interrupt_before tools
# This causes the graph to pause before executing tools,
# allowing the client to execute them locally and resume
graph = builder.compile(interrupt_before=["tools"])
