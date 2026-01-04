# DeepResearch Agent Architecture

The DeepResearch agent is the primary agent for the Socratic Seminar project. It's a research assistant that helps users find, synthesize, and organize information using web search, file management, and structured task planning.

## Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                     DeepResearch Agent                          │
├─────────────────────────────────────────────────────────────────┤
│  Middleware Stack (processed in order)                          │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │ 1. CashuPaymentMiddleware  - Payment validation (TBD)    │   │
│  │ 2. ToolValidationMiddleware - JSON validation            │   │
│  │ 3. BehaviouralMiddleware   - Personality (prompt-only)   │   │
│  │ 4. TodoListMiddleware      - Task tracking               │   │
│  │ 5. ThinkingMiddleware      - Strategic reflection        │   │
│  │ 6. ClarifyWithHumanMiddleware - User clarification       │   │
│  │ 7. ClientToolsMiddleware   - File operations             │   │
│  │ 8. SourcesMiddleware       - Project sources             │   │
│  │ 9. WebsearchMiddleware     - Web search & scraping       │   │
│  │ 10. SubAgentMiddleware     - Parallel research (opt)     │   │
│  └──────────────────────────────────────────────────────────┘   │
├─────────────────────────────────────────────────────────────────┤
│                    Client-Injected State                         │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │ files_list: List of project files (for list_files tool)   │ │
│  │ sources_list: List of sources (for list_sources tool)     │ │
│  └────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
```

## Middleware Stack

### 1. CashuPaymentMiddleware (TBD)

Handles streaming micropayments with per-iteration deduction.

- Validates Cashu tokens without immediate redemption
- Deducts configurable satoshis per LLM iteration
- Interrupts for additional funding when exhausted
- Generates refund tokens for unused balance

**Status:** Not fully implemented. Feature is TBD.

### 2. ToolValidationMiddleware

Validates all tool call arguments against their Pydantic schemas before execution.

- Catches malformed JSON from LLM
- Returns descriptive errors prompting self-correction
- No HITL interrupts

### 3. BehaviouralMiddleware

Provides prompt-only modifications to steer agent behavior.

- Controls agent personality and verbosity
- Injects current date into system prompt
- No tools, no HITL interrupts

### 4. TodoListMiddleware

Provides task tracking for complex multi-step operations.

**Tool:** `write_todos(todos: List[Todo])`

Use cases:
- Multi-step research tasks
- Complex document creation
- Breaking down research into focused tasks

### 5. ThinkingMiddleware

Provides a reflection tool for strategic planning during research.

**Tool:** `think_tool(reflection: str)`

Use after significant steps to:
- Analyze current findings
- Assess gaps in research
- Plan next steps systematically

### 6. ClarifyWithHumanMiddleware

Allows the agent to ask clarifying questions when user intent is unclear.

**Tools:**
- `ask_user(question)` - Free-form natural language question
- `ask_choices(question, options, allow_multiple?, allow_freeform?)` - Structured choices

**HITL Behavior:** Both tools interrupt for user input.

**When to use:**
- User's goal or intent is ambiguous
- Multiple valid interpretations exist
- User preferences would significantly change approach

**When NOT to use:**
- Asking how to use its own tools
- Confirming obvious next steps
- Delays that don't add value

### 7. ClientToolsMiddleware

Provides access to user's project files stored in the browser.

**Tools:**

| Tool | Description | Interrupt Type |
|------|-------------|----------------|
| `list_files(file_type?)` | List project files | **No interrupt** - returns from state |
| `read_file(file_id)` | Read file content | Auto-approved |
| `search_files(query, top_k?)` | Semantic search | Auto-approved |
| `grep_files(pattern, glob_pattern?)` | Pattern search | Auto-approved |
| `glob_files(pattern)` | Find by name pattern | Auto-approved |
| `write_file(title, content, file_type)` | Create new file | Auto-approved |
| `patch_file(file_id, patches, description)` | Edit file | **HITL required** |
| `create_source(url, title, content, ...)` | Save web source | Auto-approved |

**State Injection:** Client must inject `files_list` on each invocation so `list_files` can return immediately without interrupting.

### 8. SourcesMiddleware

Provides access to project sources (web references, PDFs, documents).

**Tools:**

| Tool | Description | Interrupt Type |
|------|-------------|----------------|
| `list_sources(source_type?)` | List sources | **No interrupt** - returns from state |
| `read_source(source_id)` | Read source content | Auto-approved |
| `search_sources(query, top_k?)` | Semantic search | Auto-approved |

**State Injection:** Client must inject `sources_list` on each invocation so `list_sources` can return immediately without interrupting.

### 9. WebsearchMiddleware

Provides web search and URL scraping capabilities.

**Tools:**

| Tool | Description | Interrupt Type |
|------|-------------|----------------|
| `web_search(query, max_results?, topic?)` | Tavily search | Auto-approved (auto-creates sources) |
| `fetch_webpage(url)` | Quick markdown fetch | No interrupt (server-side) |
| `scrape_url(url, method?)` | High-quality scrape | **HITL required** (costs money) |

### 10. SubAgentMiddleware (Optional)

Enables parallel research delegation to sub-agents.

**Status:** Disabled by default (`include_subagents=False`). Spec is being finalized.

## HITL Interrupt Summary

The following tools trigger Human-in-the-Loop interrupts:

| Tool | Middleware | Reason |
|------|------------|--------|
| `ask_user` | ClarifyWithHumanMiddleware | User input needed |
| `ask_choices` | ClarifyWithHumanMiddleware | User input needed |
| `patch_file` | ClientToolsMiddleware | File edit approval |
| `scrape_url` | WebsearchMiddleware | Costs money (Firecrawl) |

## Client Integration

### Required State Injection

The client must inject these fields on each invocation:

```typescript
agent.invoke({
  messages: [...],
  files_list: [
    { id: "abc123", title: "Research Notes.md", file_type: "document" },
    // ...
  ],
  sources_list: [
    { id: "def456", title: "Bitcoin Whitepaper", url: "https://...", sourceType: "url" },
    // ...
  ],
  // Optional payment
  payment_token: "cashuA...",
})
```

### Interrupt Flow

```
Agent calls tool
       │
       ▼
┌──────────────────┐
│ Is it a state    │──Yes──► Return from files_list/sources_list
│ return tool?     │         (list_files, list_sources)
└────────┬─────────┘
         │No
         ▼
┌──────────────────┐
│ Is it a HITL     │──Yes──► interrupt() with approval UI
│ tool?            │         (patch_file, ask_*, scrape_url)
└────────┬─────────┘
         │No
         ▼
┌──────────────────┐
│ Is it a client   │──Yes──► interrupt() with auto_approve=true
│ tool?            │         (read_file, search_files, etc.)
└────────┬─────────┘
         │No
         ▼
Execute server-side
(fetch_webpage, think_tool, etc.)
```

### Handling Interrupts

When the agent triggers an interrupt:

1. **Detect interrupt type** via `type` field:
   - `client_tool_execution` → Execute tool locally, resume with result
   - `clarification_request` → Show question UI, resume with answer
   - `human_approval_required` → Show approval dialog, resume with decision

2. **Resume the graph** with the appropriate response format:

```typescript
// For auto-approved client tools
{ tool_results: [{ tool_call_id: "...", content: "..." }] }

// For clarification
{ response: "user's answer" }
// or
{ selected: ["option-id"], freeform: "optional text" }

// For HITL approval
{ decisions: [{ type: "approve" }] }
// or
{ decisions: [{ type: "reject" }] }
```

## State Schema

```python
class DeepResearchState(BaseAgentState):
    # Client-injected state (provided each invocation)
    files_list: list[FileMetadata] | None    # For list_files tool
    sources_list: list[SourceMetadata] | None  # For list_sources tool
    
    # Inherited from BaseAgentState
    messages: Sequence[BaseMessage]
    payment_token: str | None
    payment_balance_sats: int
    payment_spent_sats: int
    payment_status: PaymentStatus
    current_project_id: str | None
    
    # Research state
    research_query: str | None
    research_sources: list[ResearchSource]
    research_findings: list[ResearchFinding]
    research_phase: Literal["planning", "researching", "synthesizing", "complete"] | None
```

## File Structure

```
agents/src/deepresearch/
├── __init__.py
├── graph.py              # Agent factory and configuration
├── state.py              # State type definitions
├── behaviour.py          # BehaviouralMiddleware
└── prompts.py            # System prompts

agents/src/shared/middleware/
├── __init__.py
├── payment.py            # CashuPaymentMiddleware
├── validation.py         # ToolValidationMiddleware
├── thinking.py           # ThinkingMiddleware
├── clarify.py            # ClarifyWithHumanMiddleware
├── client_tools.py       # ClientToolsMiddleware
├── sources.py            # SourcesMiddleware
└── websearch.py          # WebsearchMiddleware
```

## Example Usage

```python
from langgraph.checkpoint.memory import MemorySaver
from src.deepresearch.graph import create_deepresearch_agent

# Create agent with checkpointer
agent = create_deepresearch_agent(
    checkpointer=MemorySaver(),
    include_payment=False,  # Disable payment for development
)

# Invoke with client-injected state
result = await agent.ainvoke({
    "messages": [HumanMessage(content="Research Bitcoin's consensus mechanism")],
    "files_list": [],
    "sources_list": [],
})
```

## Deepagents Reference

The `deepagents/` directory contains a **reference implementation** of the deepagents library, which provides additional middleware:

- `SubAgentMiddleware` - Spawn subagents for complex tasks
- `FilesystemMiddleware` - File tools with backend abstraction
- `StateBackend` / `StoreBackend` - Storage backends

**Note**: This is included for reference only. The actual `deepagents` package should be installed separately:

```bash
pip install -e ./deepagents/libs/deepagents
```
