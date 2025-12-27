# Socratic Seminar

This project uses several example submodules to create a self-hostable web application:

Web Application features:
 - agentic: powered by LangGraph / DeepAgents
 - web-editor: more than just a chat, agents are equipped with tools and able to edit artifacts alongside the user
 - project-based: instead of linear "chat threads" we make "projects" made up of multiple artifacts, akin to files in a folder.
 - nostr-powered: users are public/private key-pairs
 - pay-as-you-go: using bitcoin eCash

Implementation details:
 - Tech Stack: Svelte 5 + Vite
 - openai-compatible: instead of paying for AI usage, we use our own AI inference and connect our LLMs to our own OpenAI-compatible endpoints.  We won't put OpenAI model names as defaults.

Built from references:
 - The `CypherTap` submodule is a Svelte 5 component which will handle user login (using nostr keys) and payment (using Bitcoin eCash)
 - The `deepagents` submodule outlines one form of agentic graph which we will use and have multiple variants of.
 - The `fullstack-chat-client` is an example fullstack web application that exemplifies an agentic UI compatible with LangGraph agents
 - The `open-canvas` submodule provides an example web application that allows for artifact editing between a human and LangGraph agent.

These references will be used to build our "Socratic Seminar" web application:

`frontend/` - our Svelte 5 frontend

`agents/` - our agentic graphs, deployed using `langgraph dev`. One node will hit our backend with an ecash token which will need to be verified before execution.

`backend/` - our Python FastAPI backend, accepts and verifies eCash payments

---

# Starting Prompt for Cursor

Review the @README.md and submodules to understand the core features of our web application. We'll need to understand the example submodules and build out a thorough plan before building.

The idea is to have projects, which will contain both threads and artifacts.  The submodule's are examples upon which we will.

We will update our MKDocs in docs/ as we go - this should be terse and be used to outline our architecture, design decisions and progress as we go.