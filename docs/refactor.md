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