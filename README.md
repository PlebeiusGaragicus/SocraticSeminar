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
 - The `CypherTap` submodule is a Svelte 5 component which will handle user login (using nostr keys) and payment (using Bitcoin eCash).  We'll use our local submodule as the official CypherTap npm package is out-of-date
 - The `deepagents` submodule outlines one form of agentic graph which we will use and have multiple variants of.
 - The `fullstack-chat-client` is an example fullstack web application that exemplifies an agentic UI compatible with LangGraph agents
 - The `open-canvas` submodule provides an example web application that allows for artifact editing between a human and LangGraph agent.
 - The `nutshell` submodule will be used for our ecash wallet and is provided for reference and clarity.

These references will be used to build our "Socratic Seminar" web application:

`frontend/` - our Svelte 5 frontend

`agents/` - our agentic graphs, deployed using `langgraph dev`. One node will hit our backend with an ecash token which will need to be verified before execution.

`backend/` - our Python 3.12+ FastAPI backend, accepts and verifies eCash payments

---

## Initial setup for local development:

```sh
python3.12 -m venv venv_agents
source venv_agents/bin/activate
cd agents
pip install -e .
cp .env.example .env
nano .env
```

```sh
python3.12 -m venv venv_backend
source venv_backend/bin/activate
cd backend
pip install -e .
cp .env.example .env
nano .env
```

```sh
cd cyphertap
npm run build
cd ../frontend
npm install

cp .env.example .env
nano .env
```



## How to run for development:

```sh
git submodule --init --recursive
```

```sh
# Frontend
cd frontend
npm run dev
```

```sh
# Backend  
cd backend
source ../venv_backend/bin/activate
uvicorn src.main:app --reload
```

```sh
# Agents
cd agents
source ../venv_agents/bin/activate
langgraph dev --no-browser
```