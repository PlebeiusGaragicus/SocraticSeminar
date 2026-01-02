"""ToolValidationMiddleware for catching and correcting malformed tool calls.

This middleware validates tool arguments against their Pydantic schemas 
before execution. If validation fails, it returns a descriptive error message 
to the model, prompting it to self-correct and retry.
"""

import json
from collections.abc import Awaitable, Callable
from typing import Any

from langchain.agents.middleware.types import AgentMiddleware, AgentState, ToolCallRequest
from langchain_core.messages import ToolMessage
from langgraph.types import Command
from pydantic import ValidationError


class ToolValidationMiddleware(AgentMiddleware[AgentState, Any]):
    """Middleware that enforces strict schema validation for all tool calls.
    
    If an LLM provides malformed JSON or arguments that violate the tool's 
    Pydantic schema, this middleware catches the error and returns a 
    ToolMessage with validation details to the model for correction.
    """
    
    async def awrap_tool_call(
        self,
        request: ToolCallRequest,
        handler: Callable[[ToolCallRequest], Awaitable[ToolMessage | Command]],
    ) -> ToolMessage | Command:
        """Intercept tool execution and perform schema validation."""
        tool_name = request.tool_call.get("name", "")
        tool_call_id = request.tool_call.get("id", "")
        tool_args = request.tool_call.get("args", {})
        
        # 1. HANDLE STRINGIFIED ARGS: Some models incorrectly send args as a JSON string
        if isinstance(tool_args, str):
            # Try to fix common hallucination typos before parsing
            # e.g. "options": [...]), -> "options": [...]
            cleaned_args = tool_args.strip()
            if cleaned_args.endswith("),"):
                cleaned_args = cleaned_args[:-2]
            elif cleaned_args.endswith(")"):
                cleaned_args = cleaned_args[:-1]
                
            try:
                # Attempt to parse the string into a dictionary
                tool_args = json.loads(cleaned_args)
                # Update the request with parsed args so subsequent handlers see valid data
                request = request.override(tool_call={**request.tool_call, "args": tool_args})
            except json.JSONDecodeError:
                # If it's a string but not valid JSON, return a standard JSON error
                error_msg = (
                    f"Error: Tool '{tool_name}' received a string instead of a JSON object, "
                    "and it could not be parsed as valid JSON. Please retry with a proper "
                    "JSON object for arguments."
                )
                return ToolMessage(content=error_msg, tool_call_id=tool_call_id, name=tool_name)

        # 2. SCHEMA VALIDATION: Check against tool's Pydantic schema
        args_schema = getattr(request.tool, "args_schema", None)
        if args_schema:
            # Create a copy of args to inject internal fields if needed
            validation_args = tool_args.copy() if isinstance(tool_args, dict) else {}
            
            # Inject known internal fields if they are in the schema but missing from model output
            schema_fields = args_schema.model_fields
            
            if "tool_call_id" in schema_fields and "tool_call_id" not in validation_args:
                validation_args["tool_call_id"] = tool_call_id
                
            if "runtime" in schema_fields and "runtime" not in validation_args:
                validation_args["runtime"] = request.runtime
                
            if "config" in schema_fields and "config" not in validation_args:
                validation_args["config"] = request.config

            try:
                # Validate the provided arguments against the schema.
                # This automatically ignores 'InjectedToolArg' fields like runtime.
                args_schema.model_validate(validation_args)
            except ValidationError as e:
                # Format a detailed error message for the LLM
                errors = []
                for err in e.errors():
                    loc = " -> ".join(str(l) for l in err["loc"])
                    msg = err["msg"]
                    errors.append(f"- {loc}: {msg}")
                
                error_msg = (
                    f"Error: Invalid arguments for tool '{tool_name}'.\n"
                    "Validation failed with the following errors:\n"
                    + "\n".join(errors) + "\n\n"
                    "Please fix these errors and retry the tool call."
                )
                
                print(f"[ValidationMiddleware] Rejected {tool_name}: {len(errors)} errors")
                
                # Return the error message to the model. 
                # This terminates this tool execution attempt and "throws it back" to the LLM.
                return ToolMessage(
                    content=error_msg,
                    tool_call_id=tool_call_id,
                    name=tool_name,
                )
            except Exception as e:
                # Fallback for unexpected validation failures
                error_msg = f"Error: Unexpected validation failure for '{tool_name}': {str(e)}"
                return ToolMessage(content=error_msg, tool_call_id=tool_call_id, name=tool_name)
        
        # 3. PROCEED: Arguments are valid, continue to next middleware or tool execution
        return await handler(request)

    def wrap_tool_call(
        self,
        request: ToolCallRequest,
        handler: Callable[[ToolCallRequest], ToolMessage | Command],
    ) -> ToolMessage | Command:
        """Synchronous version - delegates to async implementation via event loop."""
        import asyncio
        from concurrent.futures import ThreadPoolExecutor
        
        async def async_handler(req: ToolCallRequest) -> ToolMessage | Command:
            return handler(req)
        
        def run_async():
            loop = asyncio.new_event_loop()
            try:
                asyncio.set_event_loop(loop)
                return loop.run_until_complete(self.awrap_tool_call(request, async_handler))
            finally:
                loop.close()

        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # Already in a loop, run in a thread to avoid blocking it
                with ThreadPoolExecutor() as executor:
                    return executor.submit(run_async).result()
            else:
                return loop.run_until_complete(self.awrap_tool_call(request, async_handler))
        except (RuntimeError, Exception):
            # No loop or other error, run in a new one
            return run_async()

