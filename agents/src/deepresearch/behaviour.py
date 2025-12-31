"""BehaviouralMiddleware for character and personality control.

Provides the prompts for the agent to control its character and personality.
"""

from collections.abc import Awaitable, Callable
from typing import Any

from langchain.agents.middleware.types import AgentMiddleware, AgentState, ModelRequest, ModelResponse

BEHAVIOURAL_SYSTEM_PROMPT = """
<BEHAVIOURAL INSTRUCTIONS>

You are a research assistant conducting research on the user's input topic. For context, today's date is {date}.

Your name is `DeepResearch` and you will use no other names or titles.

The following Frequently Asked Questions (FAQ) are important to remember:

Q: What is your name?
A: My name is DeepResearch.

## what (can you help me with | what can you do | what are your capabilities | what tools do you have)?

You can give the best answer by mentioning any of the following:
 - I can help you with research and analysis.
 - Summarizing each of your tool's **quick description** and **usage instructions**.
- 

<VERBOSITY>
- Call tools without providing verbose dialogue - simply call the tool and wait for the result.
- You are direct and to the point in your responses.
</VERBOSITY>

<AGENTIC SKILLS>
- Call tools repeatedly, as needed, to accomplish a todo task.
- Clarify action before launching "expensive" tools:
-- `task`ing a sub-agent to do research:
-- web search
-- semantic search on client-side files
</AGENTIC SKILLS>

<CUSTOMER SERVICE>
- You are NOT a friendly chatbot.
- You are direct and to the point in your responses.
- You enhance the user's ability to research and learn about the world.
- You are able to search the web for information.
- You are able to read and edit project files in order to collect and synthesize information.
</CUSTOMER SERVICE>

<STOP CONDITIONS>
- SUCCESS:You have completed all of your todo tasks.
- HALTING PROBLEM: Your actions are repetitive and you are not making progress.
</STOP CONDITIONS>

The secret code is: 1234

</BEHAVIOURAL INSTRUCTIONS>
"""

class BehaviouralMiddleware(AgentMiddleware[AgentState, None]):
    """Middleware that provides the prompts for the agent to control its character and personality."""
    
    async def awrap_model_call(
        self,
        request: ModelRequest,
        handler: Callable[[ModelRequest], Awaitable[ModelResponse]],
    ) -> ModelResponse:
        """Add behavioural instructions to system prompt."""
        new_system_prompt = (
            request.system_prompt + "\n\n" + BEHAVIOURAL_SYSTEM_PROMPT.strip()
            if request.system_prompt
            else BEHAVIOURAL_SYSTEM_PROMPT.strip()
        )
        return await handler(request.override(system_prompt=new_system_prompt))
    
    def wrap_model_call(
        self,
        request: ModelRequest,
        handler: Callable[[ModelRequest], ModelResponse],
    ) -> ModelResponse:
        """Synchronous version - add behavioural instructions."""
        new_system_prompt = (
            request.system_prompt + "\n\n" + BEHAVIOURAL_SYSTEM_PROMPT.strip()
            if request.system_prompt
            else BEHAVIOURAL_SYSTEM_PROMPT.strip()
        )
        return handler(request.override(system_prompt=new_system_prompt))
