#!/bin/bash
# Quick wrapper to fetch LangSmith traces for debugging DeepAgents
# 
# Usage:
#   ./scripts/fetch_trace.sh --list              # List recent threads
#   ./scripts/fetch_trace.sh --latest            # Fetch most recent thread
#   ./scripts/fetch_trace.sh --thread <id>       # Fetch specific thread
#   ./scripts/fetch_trace.sh --latest --summary  # With human-readable summary
#
# Output is JSON on stdout, suitable for jq or saving to file:
#   ./scripts/fetch_trace.sh --latest > trace.json
#   ./scripts/fetch_trace.sh --latest | jq '.runs[] | select(.error)'

# MOST USED
# ./fetch_trace.sh --latest > ./traces/latest.json
# ./fetch_trace.sh --latest | jq '.runs[-1].inputs.messages' > ./traces/messages.json
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
AGENTS_DIR="$(dirname "$SCRIPT_DIR")"

# Load .env if it exists
if [ -f "$AGENTS_DIR/.env" ]; then
    set -a
    source "$AGENTS_DIR/.env"
    set +a
fi

# Check for required env vars
if [ -z "$LANGSMITH_API_KEY" ] && [ -z "$LANGCHAIN_API_KEY" ]; then
    echo "Error: LANGSMITH_API_KEY or LANGCHAIN_API_KEY not set" >&2
    echo "Set in $AGENTS_DIR/.env or environment" >&2
    exit 1
fi

# Run the Python script
exec python3 "$SCRIPT_DIR/fetch_thread_trace.py" "$@"

