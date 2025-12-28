#!/usr/bin/env python3
"""Fetch raw trace data from LangSmith for a thread.

This script fetches all runs associated with a thread ID, providing raw data
for debugging LangGraph DeepAgents behavior, interrupts, and state management.

Usage:
    # List recent threads
    python scripts/fetch_thread_trace.py --list
    
    # Fetch traces for specific thread (outputs JSON)
    python scripts/fetch_thread_trace.py --thread <thread_id>
    
    # Fetch latest thread
    python scripts/fetch_thread_trace.py --latest
    
    # Show full state snapshots (verbose)
    python scripts/fetch_thread_trace.py --thread <thread_id> --full-state
    
    # Save to file
    python scripts/fetch_thread_trace.py --thread <thread_id> > trace.json

Environment (from .env):
    LANGSMITH_API_KEY or LANGCHAIN_API_KEY - API key for LangSmith
    LANGCHAIN_PROJECT - Project name (optional, will list all if not set)
"""

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

# Load .env from agents directory
try:
    from dotenv import load_dotenv
    env_path = Path(__file__).parent.parent / ".env"
    if env_path.exists():
        load_dotenv(env_path)
except ImportError:
    pass  # Use system env vars


def get_langsmith_client():
    """Get LangSmith client."""
    api_key = os.getenv("LANGSMITH_API_KEY") or os.getenv("LANGCHAIN_API_KEY")
    if not api_key:
        print("Error: LANGSMITH_API_KEY or LANGCHAIN_API_KEY not set", file=sys.stderr)
        print("Set in .env file or environment", file=sys.stderr)
        sys.exit(1)
    
    try:
        from langsmith import Client
        return Client(api_key=api_key)
    except ImportError:
        print("Error: langsmith package not installed", file=sys.stderr)
        print("Run: pip install langsmith", file=sys.stderr)
        sys.exit(1)


def list_recent_threads(client, project_name: str | None, limit: int = 20):
    """List recent threads with their run counts."""
    projects = [project_name] if project_name else None
    
    # If no project specified, get recent projects
    if not projects:
        try:
            proj_list = list(client.list_projects(limit=10))
            projects = [p.name for p in proj_list]
            print(f"Scanning projects: {projects}", file=sys.stderr)
        except Exception as e:
            print(f"Error listing projects: {e}", file=sys.stderr)
            return
    
    threads_info = {}  # thread_id -> {runs, first_time, last_time, project}
    
    for proj in projects:
        try:
            runs = list(client.list_runs(
                project_name=proj,
                is_root=True,
                limit=limit * 5,
            ))
            
            for run in runs:
                # Get thread_id from metadata
                metadata = getattr(run, 'extra', {}).get('metadata', {})
                thread_id = metadata.get('thread_id')
                
                if not thread_id:
                    continue
                
                run_time = run.start_time if run.start_time else datetime.now()
                
                if thread_id not in threads_info:
                    threads_info[thread_id] = {
                        'runs': 0,
                        'first_time': run_time,
                        'last_time': run_time,
                        'project': proj,
                    }
                
                threads_info[thread_id]['runs'] += 1
                if run_time < threads_info[thread_id]['first_time']:
                    threads_info[thread_id]['first_time'] = run_time
                if run_time > threads_info[thread_id]['last_time']:
                    threads_info[thread_id]['last_time'] = run_time
                    
        except Exception as e:
            print(f"Error scanning project {proj}: {e}", file=sys.stderr)
    
    # Sort by last_time, most recent first
    sorted_threads = sorted(
        threads_info.items(),
        key=lambda x: x[1]['last_time'],
        reverse=True
    )[:limit]
    
    print("\nRecent threads:")
    print("-" * 90)
    print(f"{'Thread ID':<40} {'Runs':>5} {'Project':<25} {'Last Activity':<20}")
    print("-" * 90)
    
    for thread_id, info in sorted_threads:
        last = info['last_time'].strftime('%Y-%m-%d %H:%M') if info['last_time'] else 'N/A'
        print(f"{thread_id:<40} {info['runs']:>5} {info['project']:<25} {last:<20}")
    
    print("-" * 90)
    print(f"Total: {len(sorted_threads)} threads")


def fetch_thread_runs(client, thread_id: str, project_name: str | None) -> list:
    """Fetch all runs for a thread, returning raw data."""
    projects = [project_name] if project_name else None
    
    if not projects:
        try:
            proj_list = list(client.list_projects(limit=20))
            projects = [p.name for p in proj_list]
        except Exception:
            projects = []
    
    all_runs = []
    
    for proj in projects:
        try:
            # Fetch root runs and filter by thread_id locally
            # (metadata filter syntax varies by LangSmith version)
            runs = list(client.list_runs(
                project_name=proj,
                is_root=True,
                limit=100,
            ))
            
            # Filter by thread_id in metadata
            matching_root_runs = []
            for run in runs:
                metadata = getattr(run, 'extra', {}).get('metadata', {})
                if metadata.get('thread_id') == thread_id:
                    matching_root_runs.append(run)
            
            if matching_root_runs:
                print(f"Found {len(matching_root_runs)} root runs in '{proj}'", file=sys.stderr)
                
                # Now fetch child runs for each matching root
                for root_run in matching_root_runs:
                    all_runs.append(root_run)
                    try:
                        # Get all child runs under this root
                        child_runs = list(client.list_runs(
                            project_name=proj,
                            trace_id=str(root_run.trace_id) if root_run.trace_id else str(root_run.id),
                            limit=100,
                        ))
                        # Add children (excluding the root itself)
                        for child in child_runs:
                            if str(child.id) != str(root_run.id):
                                all_runs.append(child)
                    except Exception as e:
                        print(f"  Error fetching children: {e}", file=sys.stderr)
                        
        except Exception as e:
            print(f"Error fetching from {proj}: {e}", file=sys.stderr)
    
    return all_runs


def run_to_dict(run, include_full_state: bool = False) -> dict[str, Any]:
    """Convert a LangSmith Run object to a serializable dict."""
    data = {
        'id': str(run.id),
        'name': run.name,
        'run_type': run.run_type,
        'status': run.status,
        'start_time': run.start_time.isoformat() if run.start_time else None,
        'end_time': run.end_time.isoformat() if run.end_time else None,
        'parent_run_id': str(run.parent_run_id) if run.parent_run_id else None,
        'error': run.error,
        'metadata': getattr(run, 'extra', {}).get('metadata', {}),
    }
    
    # Include inputs/outputs (the core debugging data)
    if run.inputs:
        data['inputs'] = run.inputs
    if run.outputs:
        data['outputs'] = run.outputs
    
    # Include events for interrupt/resume tracking
    if hasattr(run, 'events') and run.events:
        data['events'] = run.events
    
    # Full state for verbose debugging
    if include_full_state:
        data['extra'] = getattr(run, 'extra', {})
        data['serialized'] = getattr(run, 'serialized', {})
    
    return data


def format_summary(runs: list[dict]) -> str:
    """Create a human-readable summary of the thread."""
    lines = []
    lines.append("\n" + "=" * 70)
    lines.append("THREAD SUMMARY")
    lines.append("=" * 70)
    
    if not runs:
        lines.append("No runs found.")
        return "\n".join(lines)
    
    # Sort by start_time
    sorted_runs = sorted(runs, key=lambda r: r.get('start_time') or '')
    
    lines.append(f"Total runs: {len(runs)}")
    lines.append(f"Time range: {sorted_runs[0].get('start_time', 'N/A')} → {sorted_runs[-1].get('start_time', 'N/A')}")
    
    # Count by run type
    type_counts = {}
    for run in runs:
        rt = run.get('run_type', 'unknown')
        type_counts[rt] = type_counts.get(rt, 0) + 1
    lines.append(f"Run types: {type_counts}")
    
    # Count root runs (resumptions)
    root_runs = [r for r in sorted_runs if not r.get('parent_run_id')]
    lines.append(f"Root runs (resumptions): {len(root_runs)}")
    
    # Check for interrupts vs real errors
    errors = [r for r in runs if r.get('error')]
    interrupts = [r for r in errors if 'GraphInterrupt' in str(r.get('error', ''))]
    real_errors = [r for r in errors if 'GraphInterrupt' not in str(r.get('error', ''))]
    
    if interrupts:
        lines.append(f"\n🔄 Interrupts: {len(interrupts)}")
        for r in interrupts[:3]:
            error = r.get('error', '')
            # Extract tool name from interrupt
            if 'action_requests' in error and "'name':" in error:
                import re
                match = re.search(r"'name': '(\w+)'", error)
                tool = match.group(1) if match else 'unknown'
                lines.append(f"  - {r.get('name')}: interrupted for tool '{tool}'")
    
    if real_errors:
        lines.append(f"\n⚠️  Errors: {len(real_errors)}")
        for r in real_errors[:5]:
            lines.append(f"  - {r.get('name')}: {r.get('error')[:100]}")
    
    # Show timeline of root runs
    lines.append("\n--- Run Timeline (Root Runs Only) ---")
    
    for i, run in enumerate(root_runs):
        status_icon = "✓" if run.get('status') == 'success' else "✗" if run.get('error') else "…"
        name = run.get('name', 'unknown')
        start = run.get('start_time', '')[:19] if run.get('start_time') else '?'
        
        # Check for interrupts in outputs
        outputs = run.get('outputs', {})
        has_interrupt = '__interrupt__' in str(outputs) or 'interrupt' in str(outputs).lower()
        interrupt_marker = " [INTERRUPT]" if has_interrupt else ""
        
        # Check if this is a resume (has Command in inputs)
        inputs = run.get('inputs', {})
        is_resume = 'resume' in str(inputs).lower() or i > 0
        resume_marker = " (resume)" if is_resume and i > 0 else ""
        
        lines.append(f"  [{status_icon}] {start} - {name}{interrupt_marker}{resume_marker}")
        
        # Show input messages briefly
        if 'messages' in inputs and inputs['messages']:
            first_msg = inputs['messages'][0]
            if isinstance(first_msg, dict):
                content = first_msg.get('content', '')[:80]
                if content:
                    lines.append(f"      Input: {content}...")
    
    lines.append("=" * 70)
    lines.append("\nUseful jq queries:")
    lines.append("  # Get all tool calls:")
    lines.append("  jq '.runs[] | select(.run_type==\"tool\") | {name, inputs, outputs}'")
    lines.append("  # Find interrupts:")
    lines.append("  jq '.runs[] | select(.error | contains(\"GraphInterrupt\")) | {name, error}'")
    lines.append("  # Get final state:")
    lines.append("  jq '.runs | map(select(.parent_run_id==null)) | last | .outputs'")
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(
        description="Fetch raw LangSmith trace data for a thread",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    parser.add_argument('--list', action='store_true', help='List recent threads')
    parser.add_argument('--thread', '-t', type=str, help='Thread ID to fetch')
    parser.add_argument('--latest', action='store_true', help='Fetch the most recent thread')
    parser.add_argument('--project', '-p', type=str, help='LangSmith project name')
    parser.add_argument('--full-state', action='store_true', help='Include full state data')
    parser.add_argument('--summary', '-s', action='store_true', help='Show human-readable summary')
    parser.add_argument('--limit', type=int, default=20, help='Limit for --list')
    args = parser.parse_args()
    
    project = args.project or os.getenv('LANGCHAIN_PROJECT')
    client = get_langsmith_client()
    
    if args.list:
        list_recent_threads(client, project, args.limit)
        return
    
    # Determine thread ID
    thread_id = args.thread
    
    if args.latest and not thread_id:
        # Get the most recent thread
        print("Finding most recent thread...", file=sys.stderr)
        projects = [project] if project else None
        if not projects:
            try:
                proj_list = list(client.list_projects(limit=10))
                projects = [p.name for p in proj_list]
            except Exception:
                projects = []
        
        latest_time = None
        for proj in projects:
            try:
                runs = list(client.list_runs(
                    project_name=proj,
                    is_root=True,
                    limit=10,
                ))
                for run in runs:
                    metadata = getattr(run, 'extra', {}).get('metadata', {})
                    tid = metadata.get('thread_id')
                    if tid:
                        run_time = run.start_time
                        if latest_time is None or (run_time and run_time > latest_time):
                            latest_time = run_time
                            thread_id = tid
            except Exception:
                pass
        
        if thread_id:
            print(f"Latest thread: {thread_id}", file=sys.stderr)
        else:
            print("No threads found", file=sys.stderr)
            sys.exit(1)
    
    if not thread_id:
        print("Error: Specify --thread <id>, --latest, or --list", file=sys.stderr)
        parser.print_help()
        sys.exit(1)
    
    # Fetch runs
    print(f"Fetching runs for thread: {thread_id}", file=sys.stderr)
    runs = fetch_thread_runs(client, thread_id, project)
    
    if not runs:
        print("No runs found for this thread", file=sys.stderr)
        sys.exit(1)
    
    # Convert to dicts
    runs_data = [run_to_dict(r, include_full_state=args.full_state) for r in runs]
    
    # Sort by start_time
    runs_data.sort(key=lambda r: r.get('start_time') or '')
    
    # Output
    if args.summary:
        print(format_summary(runs_data), file=sys.stderr)
    
    # Always output JSON to stdout (for piping/saving)
    output = {
        'thread_id': thread_id,
        'run_count': len(runs_data),
        'fetched_at': datetime.now().isoformat(),
        'runs': runs_data,
    }
    
    print(json.dumps(output, indent=2, default=str))


if __name__ == "__main__":
    main()

