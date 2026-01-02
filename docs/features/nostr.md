# Nostr Integration

Nostr (Notes and Other Stuff Transmitted by Relays) is a decentralized protocol used for identity and optional data synchronization in Socratic Seminar.

## Identity (npubs)

In Socratic Seminar, users are identified by their **Nostr Public Key (npub)**. 

- **No Passwords**: Authentication is done via digital signatures. Users can use browser extensions like Alby or nos2x (NIP-07) to sign in without ever revealing their private key to the application.
- **Sovereignty**: Your identity is a cryptographic key pair that you own. No central authority can "ban" your account or take away your access to the software.
- **Privacy**: Socratic Seminar does not require an email address or any personal information. Your `npub` is your unique identifier.

## CypherTap

The frontend uses the `CypherTap` component (a dedicated submodule) to manage Nostr keys and authentication.

### NIPs Supported
- **NIP-01**: Basic protocol support.
- **NIP-07**: Browser extension integration.
- **NIP-49**: Private key encryption for local storage.

## Data Synchronization

While Socratic Seminar is primarily [Local-First](local_storage.md), Nostr can be used as a transport layer for syncing data across devices or sharing artifacts.

- **Relay-Based**: Data is "published" to user-specified relays. Other instances of Socratic Seminar (signed in with the same key) can "subscribe" to these events to rebuild the local state.
- **Encrypted Content**: Sensitive data can be encrypted (NIP-04 or NIP-44) so that only the user can read it, even if it's stored on a public relay.

## Why Nostr?

Traditional web applications rely on a central database to store user accounts and data. This creates a "honeypot" for hackers and gives the platform owner total control over the users. 

By using Nostr:
1.  **Users own their data**: Even if our servers go down, you can still access your data from any other Nostr-compatible client.
2.  **Censorship resistance**: No one can stop you from publishing your thoughts or accessing your research.
3.  **Interoperability**: Your identity and work can eventually be used in other Nostr-powered intellectual tools.

---

# CopyFuck

`CopyFuck` is the idea that information SHOULD be free. It is a moral statement about how one should live in Nature. Socratic Seminar is built to facilitate the free sharing and synthesis of knowledge, empowering individuals to think for themselves.

# Local Storage & Persistence

Socratic Seminar is a **local-first** application. All user data—projects, threads, artifacts, and settings—is stored directly in the user's browser. This ensures maximum privacy, offline capability, and zero reliance on a central database.

## IndexedDB

The primary storage engine is **IndexedDB**, a low-level API for client-side storage of significant amounts of structured data. We use a custom service wrapper in `frontend/src/lib/services/indexeddb.ts` to provide a clean, promise-based interface.

### Schema Overview

The database (`socratic-seminar`) consists of several object stores:

-   **`projects`**: Metadata for high-level workspaces.
-   **`threads`**: Chat session metadata.
-   **`messages`**: Individual messages within threads, indexed by `threadId`.
-   **`artifacts`**: Document metadata and their full version history.
-   **`sources`**: Scraped web content and reference materials.
-   **`settings`**: User preferences and application state.

## Persistence Strategy

### 1. Transparent Saving
Most stores (Projects, Threads, Sources) implement "Transparent Saving." When an action like `createThread` is called, the store updates its reactive state and immediately triggers an asynchronous, non-blocking save to IndexedDB.

### 2. Debounced Document Saving
Artifacts (documents) use a debounced strategy to avoid performance issues during rapid typing:
-   **Live Map**: As you type, changes are stored in a reactive `liveContentMap` in memory.
-   **Auto-save**: After 500ms of inactivity, the `liveContentMap` is flushed to IndexedDB.
-   **Explicit Versions**: New versions are only created when explicitly triggered or during significant workflow transitions.

### 3. Loading and Initialization
On application start, the `init()` sequence:
1.  Connects to IndexedDB.
2.  Loads all `projects` for the active Nostr public key.
3.  Hydrates the stores with the initial data.
4.  Subsequent data (like messages for a specific thread) is loaded on-demand as the user navigates.

## Data Sovereignty

Because data is stored in the browser:
-   **Privacy**: Your research and writing never touch our servers.
-   **Ownership**: You can export your data at any time (as Markdown or JSON).
-   **No Login**: You don't need an account on our servers to use the app; your identity is your Nostr key, and your data is local.

## Limitations and Sync

-   **Browser Cleared**: If you manually clear your browser's "Site Data," your local work will be lost.
-   **Multi-Device**: To use Socratic Seminar on multiple devices, users must sync their data via the **Nostr Protocol** (optional) or manual export/import.

