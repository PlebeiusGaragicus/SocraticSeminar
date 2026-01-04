# Architecture Overview

## System Components

```
┌────────────────────────────────────────────────────────────────┐
│                         Frontend                                │
│                    (Svelte 5 + Vite)                           │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐            │
│  │   CypherTap  │ │   Stores     │ │   Workspace  │            │
│  │   (Auth/Pay) │ │  (Projects)  │ │     (UI)     │            │
│  └──────────────┘ └──────────────┘ └──────────────┘            │
└────────────────────────────────────────────────────────────────┘
           │                               │
           │ Nostr relays                  │ Direct streaming
           ▼                               ▼
    ┌──────────────┐              ┌──────────────────┐
    │    Nostr     │              │    LangGraph     │
    │   Network    │              │     Server       │
    └──────────────┘              └──────────────────┘
                                           │
                                           │ Payment validation
                                           ▼
                                  ┌──────────────────┐
                                  │  FastAPI Backend │
                                  │  (Wallet Service)│
                                  └──────────────────┘
                                           │
                                           │ nutshell library
                                           ▼
                                  ┌──────────────────┐
                                  │   Cashu Mint     │
                                  └──────────────────┘
```

## Data Flow

### 1. Authentication (Nostr)
- User authenticates via CypherTap component
- Private key stored locally (NIP-49 encrypted) or via browser extension (NIP-07)
- User identity is their Nostr public key (npub)

### 2. Agent Queries (LangGraph)
- Frontend calls LangGraph server directly (not proxied through backend)
- Uses `@langchain/langgraph-sdk` for streaming
- Client injects `files_list` and `sources_list` on each invocation
- Optional eCash token included for paid queries

### 3. Payment Flow
```
Client → LangGraph → validate_payment_node → Backend Wallet → Cashu Mint
                           │
                           ├── Valid → Continue to agent
                           └── Invalid → End with refund flag
```

## Directory Structure

```
SocraticSeminar/
├── frontend/           # Svelte 5 + Vite application
│   ├── src/
│   │   ├── lib/
│   │   │   ├── components/  # UI components
│   │   │   ├── services/    # LangGraph client, tool executor
│   │   │   └── stores/      # State management
│   │   └── routes/          # SvelteKit routes
│   └── package.json
│
├── agents/             # LangGraph agents
│   ├── src/
│   │   ├── deepresearch/    # Main production agent
│   │   │   ├── graph.py     # Agent factory
│   │   │   ├── state.py     # State types
│   │   │   ├── behaviour.py # BehaviouralMiddleware
│   │   │   └── prompts.py   # System prompts
│   │   └── shared/          # Shared middleware
│   │       ├── middleware/  # All middleware implementations
│   │       ├── config.py    # Agent configuration
│   │       ├── models.py    # Model helpers
│   │       └── state.py     # Base state types
│   ├── scripts/             # Debugging and tracing scripts
│   └── langgraph.json
│
├── agents-examples/    # Reference implementations (not production)
│   └── deep_research/       # Example research agent
│
├── backend/            # FastAPI wallet service
│   └── src/
│       ├── main.py          # FastAPI app
│       ├── wallet.py        # Cashu operations
│       └── scrape.py        # URL scraping service
│
├── cyphertap/          # Nostr auth + Bitcoin payments (submodule)
├── nutshell/           # Cashu wallet library (submodule)
├── deepagents/         # Reference deepagents library
│   └── libs/
│       ├── deepagents/      # Core library
│       └── deepagents-cli/  # CLI tools
└── docs/               # This documentation
```

## Key Design Decisions

### Single Production Agent
The project has one production agent: **DeepResearch** (`agents/src/deepresearch/`). 
Other agents in `agents-examples/` are reference implementations for learning.

### Direct LangGraph Streaming
The frontend calls LangGraph directly rather than proxying through the backend. This provides:
- Lower latency for real-time streaming
- Simpler backend (only handles payments and scraping)
- Better separation of concerns

### Client State Injection
The client injects `files_list` and `sources_list` on each invocation:
- `list_files` and `list_sources` tools return immediately from state
- No interrupt needed for listing operations
- Reduces round-trips for common operations

### Middleware Architecture
All agent capabilities are implemented as composable middleware:
- Each middleware provides specific tools and/or prompt modifications
- HITL behavior is controlled per-tool (not per-middleware)
- Middleware order matters for prompt composition

### HITL Patterns
Three types of tools based on interrupt behavior:
1. **State return**: `list_files`, `list_sources` - return from injected state
2. **Auto-approved**: Most file/source operations - interrupt but auto-execute
3. **HITL required**: `patch_file`, `ask_*`, `scrape_url` - require user approval

### Payment Validation in LangGraph
Payment validation is a LangGraph middleware, not backend middleware:
- Agent has full control of payment flow
- Can implement refunds on agent failure
- Token only redeemed after successful completion

### Development Mode
All components support development mode:
- Frontend: Demo login without Nostr
- Agent: Accepts debug tokens (`cashu_debug_*`)
- Backend: `DEV_MODE=true` skips validation
