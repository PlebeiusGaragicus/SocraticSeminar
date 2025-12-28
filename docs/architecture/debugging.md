# Debugging and Tracing

To iterate on LangGraph agents and handle complex flows (like interrupts for client-side tool execution), clear visibility into the graph state and execution history is essential.

## LangSmith Tracing

The agents are configured to trace to LangSmith. Tracing allows you to inspect:
- Every run of the graph
- Inputs and outputs of each node
- LLM prompt and response details
- Tool calls and results
- Graph interrupts and resumptions

### Environment Setup

Ensure your `agents/.env` file contains:
```bash
LANGSMITH_API_KEY=your_key_here
LANGSMITH_TRACING_V2=true
LANGSMITH_PROJECT=svelte-reader  # Or your project name
```

## Debugging Scripts

We provide specialized scripts in the `agents/scripts/` directory to fetch and analyze trace data without leaving the terminal.

### Fetching Thread Traces

A "thread" in LangGraph often spans multiple runs due to interrupts (e.g., waiting for client-side tool execution). The `fetch_thread_trace.py` script gathers all runs for a single thread into a coherent view.

#### Usage

```bash
# List recent threads and their run counts
./scripts/fetch_trace.sh --list

# Fetch the most recent thread with a human-readable summary
./scripts/fetch_trace.sh --latest --summary

# Fetch a specific thread and output raw JSON (for programmatic analysis)
./scripts/fetch_trace.sh --thread <thread_id> > trace.json
```

#### Key Features
- **Resumption Tracking**: Automatically finds all root runs and their children for a given thread.
- **Interrupt Detection**: Clearly identifies when a graph was interrupted for tool execution.
- **Summary View**: Provides a timeline of events, time ranges, and error counts.
- **JQ Integration**: The JSON output is designed to be easily filtered with `jq`.

### Common Debugging Queries

Once you have a trace JSON, you can use `jq` to answer specific questions:

**What tool calls were requested?**
```bash
./scripts/fetch_trace.sh --latest | jq '.runs[] | select(.run_type=="tool") | {name, inputs, outputs}'
```

**Where did it interrupt?**
```bash
./scripts/fetch_trace.sh --latest | jq '.runs[] | select(.error | contains("GraphInterrupt")) | {name, error}'
```

**What was the final state?**
```bash
./scripts/fetch_trace.sh --latest | jq '.runs | map(select(.parent_run_id==null)) | last | .outputs'
```

## Local Logging

In addition to LangSmith, some agents may log events locally to `agents/logs/<thread_id>.jsonl`. The `SvelteReader/agent/scripts/debug_agent.py` script can combine these local logs with LangSmith data for a comprehensive report.

