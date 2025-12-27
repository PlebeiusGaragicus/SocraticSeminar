# Socratic Seminar

A self-hostable, project-based agentic document editor powered by Nostr authentication and Bitcoin eCash payments.

## Overview

Socratic Seminar enables structured intellectual discourse through AI-assisted document editing. Users authenticate via Nostr (decentralized identity), pay per agent query with Bitcoin eCash tokens (Cashu protocol), and collaborate on versioned artifacts within project workspaces.

## Key Features

- **Project-based organization** - Group related threads and artifacts
- **Agentic document editing** - AI agents help create and refine documents
- **Nostr authentication** - Decentralized identity using public/private key pairs
- **Bitcoin eCash payments** - Pay-as-you-go with Cashu tokens
- **Artifact versioning** - Track and revert document changes
- **Local-first storage** - IndexedDB for offline capability

## Quick Start

```bash
# Frontend
cd frontend && npm install && npm run dev

# Backend (wallet service)
cd backend && pip install -e . && uvicorn src.main:app --reload

# Agents
cd agents && langgraph dev
```

## Architecture

See [Architecture Documentation](architecture/overview.md) for details.
