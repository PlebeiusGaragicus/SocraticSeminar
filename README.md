# Socratic Seminar

**Important information for coding agents:**

1. Always read the docs!

1. We always ensure to both review documentation and keep it up-to-date with code changes.  Instead of adding new files, we keep updates terse and contained in the files that reference the features.  We don't include verbose changelogs or list of refactored code elements - we simply update the existing documentation to match.

1. The submodules in this repo are for **reference only** - our Svelte frontend/ contains our web app.

1. Project structure:

  - **`docs/`** - our MKDocs documentation hosted on Github Pages
  - **`frontend/`** - Svelte 5 web app
  - **`backend/`** - Python3.12 FastAPI backend for accepting payments - used by our LangGraph agents for payment validation and redemption
  - **`agent/`** - Self-hosted LangGraph agents for AI chat

  - **`cyphertap`** is our fork of the repository since its `npm` library is out-of-date.  We build from and use our local submodule since it has new features not included in the origional repository. **Changes may be made to this submodule in order to further bugfix/develop its features!**
  - **`nutshell/`** a python library which handles self-custody ecash wallets - it is used in our FastAPI backend/ to store user's funds which were spent to pay for usage of our agents and is provided for reference and clarity.
  - **`deepagents/`** is a LangGraph library which demonstrates a `deepagent` whose capabilities can be extended with `Middleware`.  We custom-build out own agents using `create_agent()` similarly to the deepagent library.
  - **`deep-agent-ui`** is another React frontend that demonstrates a chat UI between a user and a LangGraph `deepagent` capable of tool calling.
  - **`fullstack-chat-client`** is an example React frontend for demonstrating a chat UI between a user and LangGraph agent capable of tool calling.




Web Application features:
 - agentic: powered by LangGraph / DeepAgents
 - web-editor: more than just a chat, agents are equipped with tools and able to edit artifacts alongside the user
 - project-based: instead of linear "chat threads" we make "projects" made up of multiple artifacts, akin to files in a folder.
 - nostr-powered: users are public/private key-pairs
 - pay-as-you-go: using bitcoin eCash

Implementation details:
 - Tech Stack: Svelte 5 + Vite
 - openai-compatible: instead of paying for AI usage, we use our own AI inference and connect our LLMs to our own OpenAI-compatible endpoints.  We won't put OpenAI model names as defaults.





---


**Humans:** see our [docs](https://plebeiusgaragicus.github.io/SvelteReader/) for information.

Run all three services for full-stack development:

With `tmux`:
```bash
tmux new-session -d -s sveltereader
tmux split-window -h
tmux split-window -v
tmux send-keys -t 0 'cd agent && source .venv/bin/activate && langgraph dev' C-m
tmux send-keys -t 1 'cd backend && source .venv/bin/activate && uvicorn src.main:app --reload' C-m
tmux send-keys -t 2 'cd frontend && pnpm dev' C-m
tmux attach
```

---

**git clone**

```sh
git clone ...
git submodule update --init --recursive
```

**Fresh install setup**

```sh
# LangGraph agent server
cd agents
python3.12 -m venv venv
source venv/bin/activate
pip install -e .

cp .env.example .env
nano .env

# run from start root with...


cd agents
source venv/bin/activate
langgraph dev --no-browser
```


---

**FastAPI payment backend**

```sh
cd backend
python3.12 -m venv venv
source venv/bin/activate
pip install -e .

cp .env.example .env
nano .env

# run from root with...
cd backend
source venv/bin/activate
uvicorn src.main:app --reload
```

---

**Svelte Frontend**

```sh
# build cyphertap so we can use it...
cd cyphertap
pnpm install
pnpm run build

# build frontend
cd frontend
pnpm install
pnpm run build

cp .env.example .env
nano .env


# run from root with...
cd frontend
pnpm run dev
```

---

## pull latest trace's message history from LangSmith

```sh
cd agents/scripts
./fetch_trace.sh --latest > ./traces/latest.json
./fetch_trace.sh --latest | jq '.runs[-1].inputs.messages' > ./traces/messages.json
```


# Socratic Hitch

see our [docs](https://plebeiusgaragicus.github.io/SocraticHitch/) for an explanation.

---

You can also compile specific files or use light mode:

```bash
# Show help and usage options
./compile --help

# Compile using light mode instead of the default dark mode
./compile --light

# Compile a specific markdown file
./compile path/to/your/argument.md
```

The `./compile.sh` script will:
1.  Automatically create a Python virtual environment (`venv`) if it doesn't exist.
2.  Install the necessary dependencies from `requirements.txt`.
3.  Compile the Markdown files located in `docs/arguments/` into HTML.
4.  Output the compiled HTML files into the `compiled-html/` folder at the project root.