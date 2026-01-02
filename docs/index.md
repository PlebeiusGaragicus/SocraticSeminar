# Socratic Seminar

Coding agents must ALWAYS read [their instructions](../README.md).

---

A self-hostable, project-based agentic document editor powered by Nostr authentication and Bitcoin eCash payments.

Socratic Seminar enables structured intellectual discourse through AI-assisted document editing. Users authenticate via Nostr (decentralized identity), pay per agent query with Bitcoin eCash tokens (Cashu protocol), and collaborate on versioned artifacts within project workspaces.

## Key Features

- **[Project-based organization](features/projects.md)** - Group related threads, artifacts, and sources.
- **[Agentic document editing](features/agents.md)** - AI agents (Socratic Tutors) help create and refine arguments.
- **[Nostr authentication](features/nostr.md)** - Decentralized identity using public/private key pairs.
- **Bitcoin eCash payments** - Pay-as-you-go with Cashu tokens via the [Backend](features/backend.md).
- **[Tabbed Editor](features/tabbed_editor.md)** - A unified workspace for chat, versioned documents, and research.
- **[Local-first storage](features/local_storage.md)** - IndexedDB for privacy and offline capability.

## Core Philosophy

### Freedom Software
This software is meant to empower users and increase their self-sovereignty. We avoid architectures that use central databases for file storage, user "credits," or metadata.

### Data Sovereignty
"Dude, where's my files?" - They're in your browser. We use local storage primarily, with optional sync via the Nostr protocol. Your data never leaves your device unless you choose to share it.

### Pay-per-use
We favor eCash (Cashu) over subscriptions. Any human can pay for AI features with Bitcoin, avoiding the over-charging and privacy invasions of traditional credit card-based models.

### CopyFuck
The free sharing of knowledge is core to technological progress. Socratic Seminar is designed to help you synthesize information, develop strong arguments, and share them freely.

## Documentation Map

- **[Overview](features/overview.md)**: System architecture and data flow.
- **[Frontend](features/frontend.md)**: Svelte 5 architecture, state management, and UI.
- **[Agents](features/agents.md)**: LangGraph agent architecture, middleware, and interrupts.
- **[Backend](features/backend.md)**: The minimal eCash wallet service.
- **[Debugging](features/debugging.md)**: Tools for tracing and analyzing agent behavior.
- **[Nostr Integration](features/nostr.md)**: How decentralized identity works under the hood.
- **[Templates](features/templates.md)**: Scaffolding new documents.
- **[Testing](features/testing.md)**: Current status and plans for automated testing.
