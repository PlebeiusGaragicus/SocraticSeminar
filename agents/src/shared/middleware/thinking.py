"""ThinkingMiddleware for strategic reflection.

Provides the think_tool for the agent to pause and reflect on its progress,
which helps with quality decision-making in complex tasks.
"""

from collections.abc import Awaitable, Callable
from typing import Any

from langchain.agents.middleware.types import AgentMiddleware, AgentState, ModelRequest, ModelResponse
from langchain_core.tools import tool


@tool(parse_docstring=True)
def think_tool(reflection: str) -> str:
    """Tool for strategic reflection on progress and decision-making.

    Use this tool to create a deliberate pause in your workflow for quality decision-making.
    Analyze your current findings, assess gaps, and plan next steps systematically.

    IMPORTANT:
     - Do not provide chat dialogue when calling this tool.
     - Do not provide any other text than the reflection.

    Reflection should address:
    1. Analysis of current findings - What concrete information have I gathered?
    2. Gap assessment - What crucial information is still missing?
    3. Quality evaluation - Do I have sufficient evidence for a good answer?
    4. Strategic decision - What is the best next step?

    Args:
        reflection: Your detailed reflection on progress, findings, gaps, and next steps
    """
    return f"Reflection recorded: {reflection}"


class ThinkingMiddleware(AgentMiddleware[AgentState, None]):
    """Middleware that provides a thinking tool for strategic reflection.
    
    This middleware is useful for agents performing complex multi-step tasks
    where quality decision-making and self-correction are important.
    """
    
    def __init__(self) -> None:
        """Initialize thinking middleware."""
        super().__init__()
        self.tools = [think_tool]
    
    async def awrap_model_call(
        self,
        request: ModelRequest,
        handler: Callable[[ModelRequest], Awaitable[ModelResponse]],
    ) -> ModelResponse:
        """Add thinking tool instructions to system prompt."""
        thinking_instructions = "## Thinking Tool\n\nUse the `think_tool` after significant steps to analyze your progress and plan next moves. This helps ensure high quality and systematic progress."

        new_system_prompt = (
            request.system_prompt + "\n\n" + thinking_instructions
            if request.system_prompt
            else thinking_instructions
        )
        
        return await handler(request.override(system_prompt=new_system_prompt))
    
    def wrap_model_call(
        self,
        request: ModelRequest,
        handler: Callable[[ModelRequest], ModelResponse],
    ) -> ModelResponse:
        """Synchronous version - add thinking tool instructions."""
        thinking_instructions = "## Thinking Tool\n\nUse the `think_tool` after significant steps to analyze your progress and plan next moves. This helps ensure high quality and systematic progress."
        
        new_system_prompt = (
            request.system_prompt + "\n\n" + thinking_instructions
            if request.system_prompt
            else thinking_instructions
        )
        
        return handler(request.override(system_prompt=new_system_prompt))

