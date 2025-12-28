"""Deeptutor Agent graph definition.

Architecture: Agent using create_agent() with client-executed tools
1. Payment validation node checks ecash token
2. create_agent() handles the agent loop with tool calling
3. Tools read project_files from config (passed by wrapper node)
4. Read-only tools (list_files, get_file, search_files) are auto-approved
5. Write tools (edit_file, create_file) require human approval via HITL at OUTER graph level
6. Payment redemption on completion

HITL Architecture:
- The inner agent does NOT have HITL middleware (it would lose resume context)
- The outer graph checks tool calls AFTER the inner agent returns
- If HITL tools are called, we interrupt at the outer level
- When resumed, we execute the approved tools and continue
"""

import os
from typing import Any

from langchain.agents import create_agent
from langchain_core.messages import ToolMessage
from langchain_openai import ChatOpenAI
from langgraph.config import RunnableConfig
from langgraph.graph import StateGraph, END
from langgraph.types import interrupt

from .state import DeeptutorState
from .tools import CLIENT_TOOLS
from .nodes import (
    validate_payment_node,
    redeem_payment_node,
    route_after_validation,
    build_system_prompt,
)

# Tools that require human approval before execution (write operations)
HITL_TOOLS = {"edit_file", "create_file"}


# Configuration
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "http://localhost:11434/v1")
LLM_MODEL = os.getenv("LLM_MODEL", "qwen3-coder-30b-a3b-instruct-mlx")
LLM_API_KEY = os.getenv("LLM_API_KEY", "not-needed")


def get_model():
    """Get the chat model configured for OpenAI-compatible endpoint."""
    return ChatOpenAI(
        model=LLM_MODEL,
        base_url=LLM_BASE_URL,
        api_key=LLM_API_KEY,
        temperature=0.7,
    )


def create_deeptutor_agent():
    """Create the core agent using create_agent().
    
    IMPORTANT: We do NOT use HumanInTheLoopMiddleware here!
    HITL is handled at the OUTER graph level (in agent_node).
    This is necessary because the inner agent runs as a sub-invocation
    and doesn't share checkpoint context with the outer graph.
    
    Read-only tools (list_files, get_file, search_files) work server-side
    by reading project_files from the config.
    """
    model = get_model()
    system_prompt = build_system_prompt(None)
    
    tool_names = {t.name for t in CLIENT_TOOLS}
    
    print(f"[Agent] Creating deeptutor agent")
    print(f"[Agent] Available tools: {tool_names}")
    print(f"[Agent] HITL tools (handled at outer graph): {HITL_TOOLS}")
    
    # Create agent WITHOUT HITL middleware - we handle it at outer level
    agent = create_agent(
        model,
        system_prompt=system_prompt,
        tools=CLIENT_TOOLS,
        middleware=[],  # No middleware - HITL at outer level
    )
    
    print(f"[Agent] Agent created (HITL handled at outer graph level)")
    
    return agent


# Store the compiled agent at module level
_deeptutor_agent = None


def get_deeptutor_agent():
    """Get or create the deeptutor agent singleton."""
    global _deeptutor_agent
    if _deeptutor_agent is None:
        _deeptutor_agent = create_deeptutor_agent()
    return _deeptutor_agent


def _find_tool_by_name(name: str):
    """Find a tool by name from CLIENT_TOOLS."""
    for tool in CLIENT_TOOLS:
        if tool.name == name:
            return tool
    return None


def _process_hitl_approval(
    hitl_tool_calls: list,
    resume_value: Any,
    agent_config: dict,
) -> list:
    """Process HITL approval decisions and execute tools.
    
    Resume value format from frontend:
    { "decisions": [{ "type": "approve" | "edit" | "reject", "args"?: {...} }, ...] }
    
    The decisions array is ordered to match hitl_tool_calls (one decision per tool call).
    
    Returns a list of ToolMessage results.
    """
    tool_results = []
    
    # Handle the nested structure from frontend
    # resume_value is { "decisions": [{ "type": "approve" }, ...] }
    decisions = []
    if isinstance(resume_value, dict):
        decisions = resume_value.get("decisions", [])
    elif isinstance(resume_value, list):
        decisions = resume_value
    
    print(f"[Agent] Processing {len(decisions)} decisions for {len(hitl_tool_calls)} tool calls")
    
    # Match decisions to tool calls by index
    for i, (tc, decision) in enumerate(zip(hitl_tool_calls, decisions)):
        action_name = tc["name"]
        tool_call_id = tc["id"]
        original_args = tc.get("args", {})
        
        decision_type = decision.get("type", "reject")  # Frontend uses "type" not "decision"
        modified_args = decision.get("args")  # Frontend uses "args" for edit case
        
        print(f"[Agent] Decision {i+1}: {action_name} -> {decision_type}")
        
        if decision_type in ("approve", "edit"):
            # Execute the tool
            tool = _find_tool_by_name(action_name)
            if tool:
                args = modified_args if modified_args else original_args
                try:
                    print(f"[Agent] Executing tool {action_name} with args: {args}")
                    result = tool.invoke(args, config=agent_config)
                    tool_results.append(ToolMessage(
                        content=str(result),
                        tool_call_id=tool_call_id,
                        name=action_name,
                    ))
                    print(f"[Agent] Tool {action_name} executed successfully")
                except Exception as e:
                    print(f"[Agent] Tool {action_name} failed: {e}")
                    tool_results.append(ToolMessage(
                        content=f"Error: {str(e)}",
                        tool_call_id=tool_call_id,
                        name=action_name,
                    ))
            else:
                print(f"[Agent] Warning: Tool {action_name} not found")
                tool_results.append(ToolMessage(
                    content=f"Error: Tool '{action_name}' not found",
                    tool_call_id=tool_call_id,
                    name=action_name,
                ))
        elif decision_type == "reject":
            tool_results.append(ToolMessage(
                content="Tool execution was rejected by user.",
                tool_call_id=tool_call_id,
                name=action_name,
            ))
            print(f"[Agent] Tool {action_name} rejected by user")
    
    return tool_results


async def agent_node(state: DeeptutorState, config: RunnableConfig) -> dict[str, Any]:
    """Wrapper node that invokes the agent with project_files in config.
    
    HITL Architecture (handled at OUTER graph level):
    1. Invoke the inner agent (no HITL middleware on inner agent)
    2. If the agent returns tool_calls for HITL tools, build interrupt data
    3. Call interrupt() with HITL data - this PAUSES execution
    4. When resumed, interrupt() RETURNS the approval decisions (doesn't raise)
    5. Execute approved tools and get ToolMessage results
    6. Continue the agent with tool results
    7. Loop until no more HITL tools are needed
    
    This works because:
    - The outer graph's checkpoint properly tracks the interrupt state
    - When resumed, THIS node runs again, interrupt() returns the value
    - We then continue execution in the same node
    """
    agent = get_deeptutor_agent()
    
    # Extract project_files from our state and pass via config
    project_files = state.get("project_files", [])
    messages = list(state.get("messages", []))  # Make a copy we can extend
    
    print(f"[Agent] agent_node called with {len(messages)} messages")
    print(f"[Agent] project_files: {len(project_files)} files")
    
    # Merge project_files into the configurable section of the config
    agent_config = {
        **config,
        "configurable": {
            **config.get("configurable", {}),
            "project_files": project_files,
        }
    }
    
    # Agent loop - keeps running until complete (no more tool calls or all non-HITL)
    max_iterations = 10
    iteration = 0
    
    while iteration < max_iterations:
        iteration += 1
        print(f"[Agent] Iteration {iteration}/{max_iterations}")
        
        # Check if the last message has pending HITL tool calls that need approval
        last_msg = messages[-1] if messages else None
        if last_msg and hasattr(last_msg, 'tool_calls') and last_msg.tool_calls:
            hitl_tool_calls = [tc for tc in last_msg.tool_calls if tc.get('name') in HITL_TOOLS]
            if hitl_tool_calls:
                print(f"[Agent] Pending HITL tool calls: {[tc['name'] for tc in hitl_tool_calls]}")
                
                # Build HITL interrupt data
                action_requests = [
                    {
                        "name": tc["name"],
                        "args": tc.get("args", {}),
                        "description": f"Tool execution requires approval\n\nTool: {tc['name']}\nArgs: {tc.get('args', {})}"
                    }
                    for tc in hitl_tool_calls
                ]
                review_configs = [
                    {
                        "action_name": tc["name"],
                        "allowed_decisions": ["approve", "edit", "reject"]
                    }
                    for tc in hitl_tool_calls
                ]
                
                hitl_data = {
                    "action_requests": action_requests,
                    "review_configs": review_configs,
                }
                
                print(f"[Agent] Calling interrupt() for HITL approval...")
                # First call: raises GraphInterrupt, pauses execution
                # Resume call: returns the approval decisions
                resume_value = interrupt(hitl_data)
                print(f"[Agent] interrupt() returned: {resume_value}")
                
                # Process approvals and execute tools
                tool_results = _process_hitl_approval(
                    hitl_tool_calls, resume_value, agent_config
                )
                
                if tool_results:
                    messages.extend(tool_results)
                    print(f"[Agent] Added {len(tool_results)} tool results, continuing...")
                    continue  # Loop back to call agent with tool results
                else:
                    print("[Agent] No tool results, completing")
                    break
        
        # Invoke the inner agent
        print("[Agent] Invoking inner agent...")
        result = await agent.ainvoke(
            {"messages": messages},
            agent_config
        )
        
        result_messages = result.get("messages", [])
        print(f"[Agent] Inner agent returned {len(result_messages)} messages")
        
        if not result_messages:
            break
        
        # Update messages with the new ones from agent
        messages = result_messages
        
        # Check if the result has tool calls
        last_result_msg = messages[-1] if messages else None
        if last_result_msg and hasattr(last_result_msg, 'tool_calls') and last_result_msg.tool_calls:
            tool_call_names = [tc.get('name') for tc in last_result_msg.tool_calls]
            print(f"[Agent] Agent returned tool calls: {tool_call_names}")
            
            # Check if any are HITL tools
            hitl_calls = [tc for tc in last_result_msg.tool_calls if tc.get('name') in HITL_TOOLS]
            if hitl_calls:
                # Loop again - next iteration will handle HITL interrupt
                print(f"[Agent] HITL tools detected, will interrupt on next iteration")
                continue
            else:
                # Non-HITL tools - the inner agent should handle them
                # (but we're not using create_agent's tool execution here)
                print(f"[Agent] Non-HITL tools - agent should have executed them")
                break
        else:
            # No tool calls - we're done
            print("[Agent] No tool calls, agent completed")
            break
    
    if iteration >= max_iterations:
        print(f"[Agent] Warning: reached max iterations ({max_iterations})")
    
    print(f"[Agent] Returning {len(messages)} messages")
    return {"messages": messages}


def create_graph() -> StateGraph:
    """Create the Deeptutor Agent graph with payment wrapper.
    
    The graph uses a wrapper node (agent_node) that passes project_files
    through config to the inner agent's tools.
    """
    
    builder = StateGraph(DeeptutorState)
    
    # Add nodes
    builder.add_node("validate_payment", validate_payment_node)
    builder.add_node("agent", agent_node)  # Wrapper that passes project_files via config
    builder.add_node("redeem_payment", redeem_payment_node)
    
    # Define edges
    # Start -> validate_payment
    builder.add_edge("__start__", "validate_payment")
    
    # validate_payment -> agent (if valid) or end (if invalid)
    builder.add_conditional_edges(
        "validate_payment",
        route_after_validation,
        {"agent": "agent", "end": END},
    )
    
    # agent -> redeem_payment (agent handles its own tool loop internally)
    builder.add_edge("agent", "redeem_payment")
    
    # redeem_payment -> end
    builder.add_edge("redeem_payment", END)
    
    return builder


# Compile the graph
# Note: GraphInterrupt raised by nodes will automatically pause execution
graph = create_graph().compile()

