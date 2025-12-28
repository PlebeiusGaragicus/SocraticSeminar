# Agent Architecture

## Available Agents

| Agent | Path | Description |
|-------|------|-------------|
| `deeptutor` | `./src/deeptutor/__init__.py:graph` | Socratic dialogue assistant with full middleware stack |
| `seminar_agent` | `./src/agent/__init__.py:graph` | Legacy seminar agent |
| `simple_agent` | `./src/simple_agent/__init__.py:graph` | Minimal agent for testing |

## Deeptutor (Primary Agent)

The **deeptutor** agent is the primary implementation with:

- **Middleware-based architecture** for modularity
- **Two file systems**: Client-side (user's files) and server-side (agent memory)
- **Clarification tools** for handling ambiguous user intent
- **Task tracking** with TodoListMiddleware
- **Streaming payments** with Cashu micropayments

See [Deeptutor Architecture](deeptutor.md) for full details.

### Middleware Stack

1. `CashuPaymentMiddleware` - Payment validation and per-iteration deduction
2. `TodoListMiddleware` - Task tracking for complex operations
3. `ClarifyWithHumanMiddleware` - Ask user for intent clarification
4. `FilesystemMiddleware` - Server-side ephemeral storage (StateBackend)
5. `ClientToolsMiddleware` - Client-side file operations via interrupts
6. `HumanInTheLoopMiddleware` - Approval for funding requests

## Deepagents Reference

The `deepagents/` directory contains a **reference implementation** of the deepagents library, which provides:

- `FilesystemMiddleware` - File tools with backend abstraction
- `TodoListMiddleware` - Task tracking (also available from langchain)
- `SubAgentMiddleware` - Spawn subagents for complex tasks
- `StateBackend` / `StoreBackend` - Storage backends

**Note**: This is included for reference only. The actual `deepagents` package should be installed separately via pip:

```bash
pip install -e ./deepagents/libs/deepagents
```

## LangGraph Configuration

```json
{
  "python_version": "3.11",
  "dependencies": ["."],
  "graphs": {
    "deeptutor": "./src/deeptutor/__init__.py:graph",
    "seminar_agent": "./src/agent/__init__.py:graph",
    "simple_agent": "./src/simple_agent/__init__.py:graph"
  }
}
```

## Legacy: Seminar Agent

The original seminar agent with simpler architecture:

```
__start__
    │
    ▼
validate_payment ──► (invalid) ──► END
    │
    │ (valid)
    ▼
  agent
    │
    ▼
redeem_payment
    │
    ▼
   END
```

## Debugging

To debug agent runs, see the [Debugging and Tracing](debugging.md) guide.

