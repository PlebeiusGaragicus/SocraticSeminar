# Deeptutor Agent Architecture

The Deeptutor agent is a Socratic dialogue assistant that helps users develop and refine arguments. It uses a middleware-based architecture for modularity and extensibility.

## Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                        Deeptutor Agent                          │
├─────────────────────────────────────────────────────────────────┤
│  Middleware Stack (processed in order)                          │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │ 1. CashuPaymentMiddleware  - Payment validation          │   │
│  │ 2. TodoListMiddleware      - Task tracking               │   │
│  │ 3. ClarifyWithHumanMiddleware - User clarification       │   │
│  │ 4. FilesystemMiddleware    - Server-side memory          │   │
│  │ 5. ClientToolsMiddleware   - Client-side file ops        │   │
│  │ 6. HumanInTheLoopMiddleware - Approval workflows         │   │
│  └──────────────────────────────────────────────────────────┘   │
├─────────────────────────────────────────────────────────────────┤
│                      Two File Systems                            │
│  ┌────────────────────┐    ┌────────────────────────────────┐   │
│  │ Server-side        │    │ Client-side (Browser)          │   │
│  │ (StateBackend)     │    │ (IndexedDB)                    │   │
│  │                    │    │                                │   │
│  │ /scratch/          │    │ User's project files:          │   │
│  │ /summaries/        │    │ - Scraped articles             │   │
│  │ /analysis/         │    │ - Drafts and notes             │   │
│  │                    │    │ - Seminar documents            │   │
│  │ Agent writes freely│    │ Writes require approval        │   │
│  └────────────────────┘    └────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

## Middleware Stack

### 1. CashuPaymentMiddleware

Handles streaming micropayments with per-iteration deduction.

- Validates Cashu tokens without immediate redemption
- Deducts configurable satoshis per LLM iteration
- Interrupts for additional funding when exhausted
- Generates refund tokens for unused balance

### 2. TodoListMiddleware

Provides task tracking for complex multi-step operations.

**Tool:** `write_todos(todos: List[Todo])`

Use cases:
- Multi-step research tasks
- Argument development workflows
- Complex document creation

### 3. ClarifyWithHumanMiddleware

Allows the agent to ask clarifying questions when user intent is unclear.

**Tools:**
- `ask_user(question)` - Free-form natural language question
- `ask_choices(question, options, allow_multiple?, allow_freeform?)` - Structured choices

**When to use:**
- User's goal or intent is ambiguous
- Multiple valid interpretations exist
- User preferences would significantly change approach

**When NOT to use:**
- Asking how to use its own tools
- Confirming obvious next steps
- Delays that don't add value

### 4. FilesystemMiddleware (StateBackend)

Provides server-side ephemeral storage for agent working memory.

**Tools:** `ls`, `read_file`, `write_file`, `edit_file`, `glob`, `grep`

Use for:
- Intermediate analysis and notes
- Drafts before presenting to user
- Research findings within a session

Files persist within a thread but not across threads.

### 5. ClientToolsMiddleware

Provides access to user's project files stored in the browser.

**Read tools (auto-approved):**
- `list_files(tag?, file_type?)` - List files with optional filters
- `read_file(file_id)` - Read file content
- `search_files(query, top_k?)` - Semantic search
- `grep_files(pattern, glob_pattern?, case_sensitive?)` - Pattern search
- `glob_files(pattern)` - Find files by name pattern

**Write tools (require approval):**
- `write_file(title, content, file_type)` - Create new file
- `edit_file(file_id, new_content, description)` - Edit file
- `tag_file(file_id, tags, replace?)` - Add/update tags

### 6. HumanInTheLoopMiddleware

Handles approval workflows for payment funding requests.

## Interrupt Flow

```
Agent calls tool
       │
       ▼
┌──────────────────┐
│ Is it a client   │──No──► Execute normally
│ or clarify tool? │
└────────┬─────────┘
         │Yes
         ▼
┌──────────────────┐
│ interrupt()      │
│ Pause execution  │
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│ Frontend handles │
│ - Renders UI     │
│ - Gets user input│
│ - Executes tool  │
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│ Resume with      │
│ tool result      │
└────────┬─────────┘
         │
         ▼
Agent continues
```

## Design Considerations

### Why Two File Systems?

1. **User autonomy**: User's files stay in their browser, under their control
2. **Privacy**: Scraped articles and drafts never leave the client unless explicitly shared
3. **Agent flexibility**: Agent can freely write to its working memory without interrupting the user
4. **Session context**: Agent can maintain analysis notes throughout a conversation

### Why Clarification Tools?

Instead of making assumptions, the agent can:
- Ask structured questions with predefined options
- Request free-form clarification when needed
- Avoid wasted effort from misunderstanding intent

The tools are designed to NOT be overused:
- System prompt discourages asking about tool usage
- Encourages asking only when genuinely ambiguous

### Why Client-side Tool Execution?

1. **Latency**: File operations happen locally, no round-trip to server
2. **Offline capability**: Files work even if connection drops
3. **Data sovereignty**: User's documents stay on their device
4. **Approval UX**: Frontend can show rich diffs and approval dialogs

## State Schema

```python
class DeeptutorState(TypedDict, total=False):
    # Messages (required)
    messages: Annotated[Sequence[BaseMessage], add_messages]
    
    # Payment state
    payment_token: str | None
    payment_balance_sats: int
    payment_spent_sats: int
    payment_refund_token: str | None
    payment_status: PaymentStatus
    payment_refund_claimed: bool
    
    # Project context
    current_project_id: str | None
    
    # Middleware-added state
    # files: dict[str, FileData]  # Added by FilesystemMiddleware
    # todos: list[Todo]           # Added by TodoListMiddleware
```

## Example Prompts

### Trigger Clarification Tools

```
"Help me with my argument"
```
→ Agent should ask: "What topic is your argument about?" or offer choices.

```
"I want to write about economics"  
```
→ Agent might ask choices: "Which aspect interests you? a) Monetary policy b) Market structures c) International trade d) Something else"

```
"Improve this"
```
→ Agent should ask: "What would you like me to improve? Style, clarity, argumentation, or something else?"

### Normal Usage (No Clarification Needed)

```
"Create a new document titled 'Bitcoin Thesis' with an introduction about sound money"
```
→ Clear intent, agent proceeds with write_file.

```
"Search my files for mentions of inflation"
```
→ Clear intent, agent uses grep_files.

## File Structure

```
agents/src/deeptutor/
├── __init__.py
├── graph.py              # Agent factory and configuration
├── state.py              # State type definitions
└── middleware/
    ├── __init__.py
    ├── payment.py        # CashuPaymentMiddleware
    ├── client_tools.py   # ClientToolsMiddleware
    └── clarify.py        # ClarifyWithHumanMiddleware
```

## Frontend Integration

The frontend handles interrupts by:

1. **Detecting interrupt type** via `type` field:
   - `client_tool_execution` → Execute tool locally
   - `clarification_request` → Show question UI
   - `payment_exhausted` → Show funding dialog

2. **Rendering appropriate UI**:
   - Text input for `ask_user`
   - Choice buttons for `ask_choices`
   - Diff view for `edit_file` approval

3. **Resuming the graph** with the response in the expected format

See `frontend/src/lib/services/tool-executor.ts` for tool execution implementation.

## Clarification Flow

When the agent calls `ask_user` or `ask_choices`:

```
Agent calls ask_user("What topic?")
         │
         ▼
ClarifyWithHumanMiddleware
         │
         ▼
interrupt({type: "clarification_request", ...})
         │
         ▼
┌────────────────────────────────────────┐
│ Frontend: langgraph.ts                 │
│ - Detects isClarificationInterrupt()   │
│ - Calls onClarificationInterrupt()     │
└────────────────────────────────────────┘
         │
         ▼
┌────────────────────────────────────────┐
│ Frontend: agent.svelte.ts              │
│ - Stores clarificationInterrupt        │
│ - Sets awaitingHumanResponse = true    │
└────────────────────────────────────────┘
         │
         ▼
┌────────────────────────────────────────┐
│ Frontend: ClarificationPanel.svelte    │
│ - Shows question text                  │
│ - For ask_user: textarea input         │
│ - For ask_choices: button options      │
│ - Optional freeform with choices       │
└────────────────────────────────────────┘
         │
         ▼ (user responds)
┌────────────────────────────────────────┐
│ resumeWithClarificationResponse()      │
│ - Formats response as tool result      │
│ - Resumes graph with answer            │
└────────────────────────────────────────┘
         │
         ▼
Agent receives user's answer as ToolMessage
         │
         ▼
Agent continues with clarified intent
         │
         ▼ (may trigger another interrupt)
┌────────────────────────────────────────┐
│ Chained Interrupt Handling:            │
│ - Another clarification (ask_user)     │
│ - Client tool (list_files, etc.)       │
│ - HITL approval (write operations)     │
└────────────────────────────────────────┘
```

### Chained Interrupt Handling

After resuming from any interrupt type, the agent may immediately trigger another
interrupt. All resume functions include callbacks for all interrupt types:

- `onClarificationInterrupt` - Another clarification question
- `onClientToolInterrupt` - Client-side tool execution needed  
- `onHITLInterrupt` - Human approval required

This allows seamless handling of multi-step interactions where the agent asks
clarifying questions, then uses tools, then requests approvals, etc.

### Interrupt Data Format

```typescript
// ask_user interrupt
{
  type: 'clarification_request',
  tool: 'ask_user',
  tool_call_id: '12345',
  question: 'What topic would you like to write about?'
}

// ask_choices interrupt
{
  type: 'clarification_request',
  tool: 'ask_choices',
  tool_call_id: '12345',
  question: 'What type of document?',
  options: [
    { id: 'seminar', label: 'Socratic Seminar' },
    { id: 'essay', label: 'Essay' },
    { id: 'notes', label: 'Research Notes' }
  ],
  allow_multiple: false,
  allow_freeform: true
}
```

### Response Format

```typescript
// For ask_user
{ response: "I want to write about Bitcoin's monetary policy" }

// For ask_choices (single select)
{ selected: ['seminar'] }

// For ask_choices (with freeform)
{ selected: ['essay'], freeform: 'Specifically about inflation' }
```

