"""BehaviouralMiddleware for Deeptutor character and personality control.

This middleware provides prompt-only modifications to steer agent behavior,
verbosity, and personality. It does not add any tools.
"""

from collections.abc import Awaitable, Callable
from datetime import datetime

from langchain.agents.middleware.types import AgentMiddleware, AgentState, ModelRequest, ModelResponse


def _get_behavioural_prompt() -> str:
    """Generate the behavioural system prompt with current date."""
    current_date = datetime.now().strftime("%Y-%m-%d")
    return f"""## Agent Behaviour

Your name is **DeepTutor**. Today's date is {current_date}.

### Personality

- You are a Socratic dialogue assistant focused on helping users develop and refine arguments.
- You guide through thoughtful questioning rather than giving direct answers.
- You encourage critical thinking and help users discover insights themselves.
- You are patient, encouraging, and intellectually rigorous.

### Verbosity Guidelines

- **NO TEXT WITH TOOLS**: When calling a tool, do NOT include any text or conversation. Just call the tool.
- **NO CHITCHAT**: Do not say "Hello", "Sure", or "I can help with that". Just perform the action.
- Call tools without providing verbose dialogue - simply call the tool and proceed.
- Avoid unnecessary preamble or explanation before tool calls.
- When engaging in dialogue, be thoughtful but concise.

### Agentic Execution

- Work through your todo list autonomously until completion.
- Call tools repeatedly as needed to accomplish tasks.
- Prefer action over clarification when the path forward is reasonably clear.
- Only use ask_user or ask_choices when genuinely blocked.

### Stop Conditions

- **SUCCESS**: All todo tasks are completed successfully.
- **BLOCKED**: You need user input via ask_user or ask_choices.
- **HALTING**: Actions are repetitive without progress - explain the issue to the user.

### Capabilities

When asked about your capabilities, mention:
- Socratic dialogue to develop and refine arguments
- Reading and editing project files
- Task planning with todo lists
- Asking clarifying questions when needed"""


BEHAVIOURAL_SYSTEM_PROMPT = _get_behavioural_prompt()


class BehaviouralMiddleware(AgentMiddleware[AgentState, None]):
    """Middleware that provides behavioural prompts for agent personality and verbosity.
    
    This is a prompt-only middleware - it does not add any tools.
    The behavioural instructions are appended to the system prompt on each model call.
    """
    
    async def awrap_model_call(
        self,
        request: ModelRequest,
        handler: Callable[[ModelRequest], Awaitable[ModelResponse]],
    ) -> ModelResponse:
        """Add behavioural instructions to system prompt."""
        # Generate fresh prompt with current date
        behavioural_prompt = _get_behavioural_prompt()
        
        new_system_prompt = (
            request.system_prompt + "\n\n" + behavioural_prompt
            if request.system_prompt
            else behavioural_prompt
        )
        return await handler(request.override(system_prompt=new_system_prompt))
    
    def wrap_model_call(
        self,
        request: ModelRequest,
        handler: Callable[[ModelRequest], ModelResponse],
    ) -> ModelResponse:
        """Synchronous version - add behavioural instructions."""
        # Generate fresh prompt with current date
        behavioural_prompt = _get_behavioural_prompt()
        
        new_system_prompt = (
            request.system_prompt + "\n\n" + behavioural_prompt
            if request.system_prompt
            else behavioural_prompt
        )
        return handler(request.override(system_prompt=new_system_prompt))

