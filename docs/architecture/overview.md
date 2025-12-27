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
│   │   │   └── stores/      # State management
│   │   └── routes/          # SvelteKit routes
│   └── package.json
│
├── agents/             # LangGraph agents
│   ├── src/seminar/
│   │   ├── graph.py   # Main graph definition
│   │   ├── nodes.py   # Node implementations
│   │   └── state.py   # State types
│   └── langgraph.json
│
├── backend/            # FastAPI wallet service
│   └── src/
│       ├── main.py    # FastAPI app
│       └── wallet.py  # Cashu operations
│
├── cyphertap/          # Nostr auth + Bitcoin payments (submodule)
├── nutshell/           # Cashu wallet library (submodule)
└── docs/               # This documentation
```

## Key Design Decisions

### Direct LangGraph Streaming
The frontend calls LangGraph directly rather than proxying through the backend. This provides:
- Lower latency for real-time streaming
- Simpler backend (only handles payments)
- Better separation of concerns

### Payment Validation in LangGraph
Payment validation is a LangGraph node, not backend middleware:
- Agent has full control of payment flow
- Can implement refunds on agent failure
- Token only redeemed after successful completion

### Development Mode
All components support development mode:
- Frontend: Demo login without Nostr
- Agent: Accepts debug tokens (`cashu_debug_*`)
- Backend: `DEV_MODE=true` skips validation

