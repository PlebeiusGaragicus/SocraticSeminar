# Socratic Seminar

Coding agents must ALWAYS read [their instructions](../README.md).

---

A self-hostable, project-based agentic document editor powered by Nostr authentication and Bitcoin eCash payments.

Socratic Seminar enables structured intellectual discourse through AI-assisted document editing. Users authenticate via Nostr (decentralized identity), pay per agent query with Bitcoin eCash tokens (Cashu protocol), and collaborate on versioned artifacts within project workspaces.

## Key Features

- **Project-based organization** - Group related threads and artifacts
- **Agentic document editing** - AI agents help create and refine documents
- **Nostr authentication** - Decentralized identity using public/private key pairs
- **Bitcoin eCash payments** - Pay-as-you-go with Cashu tokens
- **Artifact versioning** - Track and revert document changes
- **Local-first storage** - IndexedDB for offline capability


- **Nostr Protocol:**
    - **Users** are just simply public/private key pairs - no usernames/passwords. Usage of a NIP-07 browser extention elevates this experience even further.
    - **Just works** - Nostr protocol is used "under the hood" and should be largely invisible to the user. We aim for an experience that *"just works"* with only the "advanced user" suspecting usage of the nostr protocol.
    - **Decentralized Sync** — User data are sent via user-specified relays.
    - **No central databases** - relays > central databases

- **Client-Side Storage:**
    - **Local Browser Storage:** All application data is stored in the user's browser, you own your data.
    - Avoid "app store" ecosystem lock-in - we don't need approval to publish freedom tech apps
    - Core experience is ran on user's device.

- **eCash Payments:**
    - **Bitcoin payments:** *any human* can pay for this service to enhance their learning without risk of government "money" regulations locking them out.
    - **Pay-per-use** AI features avoid subscriptions therefore the over-charging of users who don't maximize their monthly usage.
    - **Self-custody** prevents risk of centralized theft of user funds - private keys are stored on user's devices.

- **CopyFuck:** - The *Free sharing of Knowledge* is core to technological progress.

# Concepts

# Building `deepagents` to fit nicely inside their intended environment

## What are `deepagents`?

LangGraph's `deepagents` library is an LLM "harness" which uses "middleware" to extend a LangGraph's graph's state, add to the system prompt, and include callable tools to extend an agent's abilities.

Similarly to the `deepagents` library, we use the `create_agent()` function to craft our own custom agents that fit nicely inside our User Interface.

## Freedom software

### "dude, where's my files?"

This software is meant to be "freedom software" which empowers users and increases their self-sovereignty. To this end, we avoid architectures that use a central database for file storage, user 'credits,' and metadata. Alternatively, we use the `CypherTap` Svelte component which handles nostr protocol key public/private key management as well as an eCash wallet.  A user's "files" may be sync'd to a nostr relay (or many relays), if desired - but **we primarily use local browser storage.** Similarly, we favor Markdown file formats for their ease of use and to avoid vendor lock-in. This poses a challenge when working with LangGraph agents, as they need access to user data, and we don't use a user database. To fix this, we instead design our graph to "interrupt," which returns execution back to our frontend which then detects a "client-side tool" (such as `read_file`, for example) and will resume the graph with the requesite file data, for example. Such tools may also be set for Human-in-the-Loop permissions to further put the human in the driver's seat.

### Self-hosting

Additionally, we are proponents of self hosting - so, once served, our User Interface is meant to run entirely client-side. Ideally, one day as a PWA. Also, hopefully in a "one click install" manner on such registries as start9 or Umbrel.

## Middleware

### `TodoListMiddleware`

Todos are a "pseudo tool", in that, their purpose is to ensure the agent can (1) develop and focus on a detailed plan of execution and (2) track progress towards a goal - yet their effect is to simply inject a tool call (and resulting tool message) into chat history for visibility.

`./deep-agents-ui/src/app/hooks/useChat.ts:16-52` shows how we update the UI by tracking the graph state instead of keeping track of tool calls in the message history.  Notice the coupline between frontend UI and backend **graph.**

### `ClientToolsMiddleware`

The provided `deepagents` reference git submodule shows an example usage of `FilesystemMiddleware` in which a "pseudo filesystem" is given to the agent will full read/write permissions. This filesystem is simply a list of strings stored in the graph state - so no possible damage can be done. Instead of this approach we craft `ClientToolsMiddleware` whose usage cause a graph interrupt to pass execution back to the client to read/modify files as needed, with HITL approval, if desired.

We will modify this approach in order to give the agent a per-thread "memory" or rather a "scratch pad" to use.  Our `ScratchpadMiddleware` will allow the agent to write to a 

### `ClarifyWithHumanMiddleware`

Our agents are meant to work well with human direction and follow behaviours that allow them to interact well with the user.  The clarification tools can be used when ambiguous instructions are provided.  Also, agents can be instructed to act as a one-on-one tutor and test the user's knowledge and provide impromptu training or refreshers.

### `ThinkingMiddleware`

Similarly to `TodoListMiddleware`, this tool is meant to for the agent to self-reflect on its trajectory thus far, synthesis any new information and voice its intended next steps. The goal is that by doing this the agent can run longer threads without getting stuck.

## Implementation

There is no official langchain/langgraph-sdk/svelte. However, the React SDK is just a thin wrapper around the vanilla JS client.  In Svelte 5, you would replace the complex useStream hook with a simpler $state rune class.

Key Differences:

- State: Instead of useState, you use a $state class to hold messages.
- Streaming: You use the vanilla Client from langchain/langgraph-sdk directly.


# Design FAQ

### Why don't you migrate your databases?

We are very early in development and can't be bothered to migrate - that's a feature for a mature product.  We break things and move fast using a "clean slate" approach.  Adapt or die.

### Why Nostr instead of traditional auth (email/password, OAuth)?

**Decision:** Users authenticate via Nostr public keys (npubs) using the CypherTap component.

**Reasoning:**
- **Sovereignty:** Users own their identity (private key), not the platform
- **Portability:** Same identity works across all Nostr-compatible apps
- **No email:** No PII collection, no password reset flows, no email verification
- **Censorship resistance:** No central authority can ban a user

**Trade-offs:**
- Key management is user's responsibility (can be complex)
- No account recovery if private key is lost
- Less familiar UX for mainstream users

### Why no server-side user accounts?

**Decision:** All user data is stored client-side (browser) with optional sync to Nostr relays.

**Reasoning:**
- **Privacy:** User data never touches our servers
- **Simplicity:** No user database to manage, secure, or GDPR-comply with
- **Offline-first:** App works without internet after initial load
- **Cost:** No database hosting costs that scale with users

**Trade-offs:**
- Data lost if browser storage cleared (unless synced to Nostr)
- No server-side features (email notifications, etc.)
- Multi-device requires Nostr sync (not instant)

### Why ecash (Cashu) instead of Stripe or subscriptions?

**Decision:** Users pay per AI message using Cashu ecash tokens.

**Reasoning:**
- **Micropayments:** Pay 1 sat per message (fractions of a cent)
- **No accounts:** No Stripe account, credit card, or identity required
- **Privacy:** Bearer tokens, no payment history linked to identity
- **Instant:** No payment processing delays
- **Global:** Works anywhere Bitcoin/Lightning works

**Trade-offs:**
- Users must acquire Bitcoin/Lightning sats first
- Ecash is less familiar than credit cards
- Wallet balance management UX is new


### Why pay-per-message instead of subscriptions?

**Decision:** Each AI message costs a fixed amount (default: 1 sat).

**Reasoning:**
- **Fairness:** Pay only for what you use
- **Low barrier:** Try for 1 sat, no monthly commitment
- **Scalability:** Heavy users pay more, light users pay less
- **Simplicity:** No subscription tiers, no billing cycles

**Trade-offs:**
- Less predictable revenue for operator
- Friction on every message (mitigated by wallet balance)
- No "unlimited" option for power users (yet)


### Why addressable events (kind 30000+) instead of regular notes?

**Decision:** Use addressable events for annotations and books.

**Reasoning:**
- **Updatable:** Edit annotations without creating duplicates
- **Deletable:** Publish tombstone to "delete" an annotation
- **LWW:** Last write wins, simple conflict resolution
- **Deduplication:** Relays keep only latest event per d-tag

**Trade-offs:**
- More complex event structure
- Requires d-tag management
- Some relays may not fully support NIP-33


### Why self-hosted LangGraph instead of OpenAI API directly?

**Decision:** AI runs through a self-hosted LangGraph agent, not direct API calls.

**Reasoning:**
- **Flexibility:** Use any OpenAI-compatible LLM (Ollama, vLLM, etc.)
- **Control:** Run inference on own hardware
- **Privacy:** Conversations don't go to OpenAI by default
- **Extensibility:** Add tools, RAG, multi-step reasoning
- **Cost:** Self-hosted inference can be cheaper at scale

**Trade-offs:**
- More infrastructure to manage
- Need GPU for good performance
- LangGraph learning curve


### Why Svelte 5 with runes instead of Svelte 4 stores?

**Decision:** Use Svelte 5 runes (`$state`, `$derived`, `$effect`) for new code.

**Reasoning:**
- **Future-proof:** Runes are the future of Svelte
- **Fine-grained:** Better reactivity control
- **TypeScript:** Better type inference than stores
- **Simpler:** No subscription boilerplate

**Trade-offs:**
- Mixing patterns with existing Svelte 4 stores
- Runes still evolving (potential API changes)
- Learning curve for Svelte 4 developers

### Why store ecash tokens in logs during development?

**Decision:** Full tokens logged for recovery during POC phase.

**Reasoning:**
- **Recovery:** If funds are lost due to bugs, can manually recover
- **Debugging:** See exact token flow through system
- **POC phase:** Will be removed before production

**Trade-offs:**
- Tokens visible in logs (security risk)
- Log storage requirements
- Must disable before production