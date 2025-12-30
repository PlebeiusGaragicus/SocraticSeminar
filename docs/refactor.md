# An explanation of `deepagents` and their intended UI environment

## What are `deepagents`?

LangGraph's `deepagents` library is an LLM "harness" which uses "middleware" to extend a graph's state, add to the system prompt, and includes callable tools to extend an agent's abilities.

Similarly to the library, we use `create_agent()` to craft our own custom agent that fit nicely inside our User Interface.

## Our User Interface / The agent's environment

Our agents are designed to work nicely inside our User Interface.

## Middleware

### `TodoListMiddleware`

Todos are a "pseudo tool", in that, their purpose is to ensure the agent can (1) develop and focus on a detailed plan of execution and (2) track progress towards a goal yet their effect is to simply inject a tool call (and resulting tool message) into chat history.

./deep-agents-ui/src/app/hooks/useChat.ts:16-52 shows how we update the UI by tracking the graph state instead of keeping track of tool calls in the message history.  Notice the coupline between frontend UI and backend graph.

### `ClientToolsMiddleware`

The provided `deepagents` reference git submodule shows an example usage of `FilesystemMiddleware` in which a "pseudo filesystem" is given to the agent will full read/write permissions. Instead of this approach we craft `ClientToolsMiddleware` whose tools cause a graph interrupt to pass execution back to the client to read/modify files as needed, with HITL approval, as needed.



We will modify this approach in order to give the agent a per-thread "memory" or rather a "scratch pad" to use.  Our `ScratchpadMiddleware` will allow the agent to write to a 



### `ClarifyWithHumanMiddleware`

Our agents are meant to work well with human direction and follow behaviours that allow them to interact well with the user.  The clarification tools can be used when ambiguous instructions are provided.  Also, agents can be instructed to test the user's knowledge and provide questions in order to emulate a one-on-one tutor-like experience.



## Freedom software

### "dude, where's my files?"

This software is meant to be "freedom software" which empowers and increases the self-sovereignty of our users. To this end, we avoid architectures that use a central database for file storage, user 'credits' and metadata. Alternatively, we use the `CypherTap` Svelte component which handles nostr protocol key public/private key management as well as eCash wallet.  A user's "files" may be sync'd to any nostr relay (or many relays) but are **primarily stored in local browser storage.** This poses a challenge when working with LangGraph agents, as they need access to user data, and we don't use a database. To fix this, we instead design our graph to "interrupt", which returns execution back to our frontend that then detects a "client-side tool" (such as `read_file`, for example) and resumes the graph with the requesite file data or after making the intended changes.

### Self-hosting

Additionally, our User Interface is meant to run entirely client-side and, ideally, as a PWA one day.

## Implementation

There is no official langchain/langgraph-sdk/svelte. However, the React SDK is just a thin wrapper around the vanilla JS client.  In Svelte 5, you would replace the complex useStream hook with a simpler $state rune class.

Key Differences:

- State: Instead of useState, you use a $state class to hold messages.
- Streaming: You use the vanilla Client from langchain/langgraph-sdk directly.