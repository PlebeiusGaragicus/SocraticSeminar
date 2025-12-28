"""ClarifyWithHumanMiddleware for user intent clarification.

Provides tools for the agent to ask clarifying questions when the user's
intent is unclear or when user preferences would significantly change approach.

Tools:
- ask_user(question): Free-form natural language question
- ask_choices(question, options, ...): Structured choice question

Key Patterns:
- Uses interrupt() to pause execution and get user input
- Frontend renders appropriate UI (text input or choice buttons)
- Resumes with user's response
"""

from collections.abc import Awaitable, Callable
from typing import Any

from langchain.agents.middleware.types import AgentMiddleware, AgentState, ModelRequest, ModelResponse
from langchain.tools import ToolRuntime
from langchain.tools.tool_node import ToolCallRequest
from langchain_core.messages import ToolMessage
from langchain_core.tools import StructuredTool
from langgraph.types import Command, interrupt
from typing_extensions import TypedDict


# =============================================================================
# STATE EXTENSION
# =============================================================================

class ClarifyState(AgentState):
    """State extension for clarification tools.
    
    No additional state needed - clarifications are handled via interrupts.
    """
    pass


# =============================================================================
# SYSTEM PROMPT
# =============================================================================

CLARIFY_SYSTEM_PROMPT = """## Clarification Tools

You have access to tools for asking the user clarifying questions when needed.

Available tools:
- `ask_user(question)` - Ask an open-ended question, user replies with free text
- `ask_choices(question, options, ...)` - Ask with predefined options

### When to Use Clarification Tools

Use these tools when:
- The user's goal or intent is ambiguous
- Multiple valid interpretations exist
- User preferences would significantly change your approach
- You need specific information only the user can provide

### When NOT to Use

Do NOT use clarification tools for:
- Asking how to use your own tools (you already know how)
- Confirming obvious next steps
- Delays that don't add value
- Questions you could answer yourself by reading files

### Best Practices

- Be concise with questions
- For ask_choices, provide 2-5 clear options when possible
- Set allow_freeform=True if user might have an answer outside your options (this is usually a good idea)
- Ask one question at a time, not multiple in sequence"""


# =============================================================================
# TYPE DEFINITIONS
# =============================================================================

class ChoiceOption(TypedDict):
    """A single choice option for ask_choices."""
    id: str
    """Unique identifier for this option."""
    label: str
    """Human-readable label displayed to user."""


# =============================================================================
# TOOL DEFINITIONS
# =============================================================================

def _create_ask_user_tool() -> StructuredTool:
    """Create the ask_user tool for free-form questions."""
    
    def ask_user(question: str, runtime: ToolRuntime) -> str:
        """Ask the user an open-ended question.
        
        Use this when you need free-form input from the user that can't
        be captured by predefined options.
        
        Args:
            question: The question to ask the user. Be clear and concise.
        
        Returns:
            The user's free-text response.
        """
        # Will be handled by middleware's wrap_tool_call
        return "Tool execution pending - awaiting user response"
    
    return StructuredTool.from_function(
        name="ask_user",
        func=ask_user,
        description="""Ask the user an open-ended question.

Use when you need free-form input that can't be captured by options.

Args:
    question: Clear, concise question for the user

Returns the user's free-text response.""",
    )


def _create_ask_choices_tool() -> StructuredTool:
    """Create the ask_choices tool for structured questions."""
    
    def ask_choices(
        question: str,
        options: list[dict[str, str]],
        allow_multiple: bool = False,
        allow_freeform: bool = False,
        runtime: ToolRuntime = None,
    ) -> str:
        """Ask the user to choose from predefined options.
        
        Use this when you can anticipate the likely answers and want
        to make it easy for the user to respond.
        
        Args:
            question: The question to ask the user.
            options: List of options, each with 'id' and 'label' keys.
            allow_multiple: If True, user can select multiple options.
            allow_freeform: If True, user can also type a custom answer.
        
        Returns:
            JSON with selected option id(s) and/or freeform text.
        """
        return "Tool execution pending - awaiting user response"
    
    return StructuredTool.from_function(
        name="ask_choices",
        func=ask_choices,
        description="""Ask the user to choose from predefined options.

Use when you can anticipate likely answers.

Args:
    question: The question to ask
    options: List of {"id": "...", "label": "..."} choices
    allow_multiple: Allow selecting multiple options (default: False)
    allow_freeform: Allow custom text answer (default: False)

Returns JSON with selected option(s) and/or freeform text.""",
    )


# Tool names for this middleware
CLARIFY_TOOLS = {"ask_user", "ask_choices"}


# =============================================================================
# MIDDLEWARE
# =============================================================================

class ClarifyWithHumanMiddleware(AgentMiddleware[ClarifyState, None]):
    """Middleware for user intent clarification.
    
    Provides tools for the agent to ask clarifying questions when the user's
    intent is unclear or when gathering preferences would improve results.
    
    All clarification tools interrupt execution and wait for user response.
    
    Example:
        ```python
        agent = create_agent(
            model,
            middleware=[
                ClarifyWithHumanMiddleware(),
            ],
        )
        ```
    
    Interrupt Format:
        When the agent calls a clarification tool, execution interrupts with:
        ```json
        {
            "type": "clarification_request",
            "tool": "ask_user" | "ask_choices",
            "question": "What aspect interests you?",
            "options": [...],  // for ask_choices only
            "allow_multiple": false,
            "allow_freeform": true
        }
        ```
        
        Client should resume with:
        ```json
        {
            "response": "user's text"  // for ask_user
        }
        // OR
        {
            "selected": ["option-id"],  // for ask_choices
            "freeform": "optional custom text"
        }
        ```
    """
    
    state_schema = ClarifyState
    
    def __init__(self) -> None:
        """Initialize clarification middleware."""
        super().__init__()
        self.tools = [
            _create_ask_user_tool(),
            _create_ask_choices_tool(),
        ]
    
    async def awrap_model_call(
        self,
        request: ModelRequest,
        handler: Callable[[ModelRequest], Awaitable[ModelResponse]],
    ) -> ModelResponse:
        """Add clarification tools system prompt."""
        new_system_prompt = (
            request.system_prompt + "\n\n" + CLARIFY_SYSTEM_PROMPT
            if request.system_prompt
            else CLARIFY_SYSTEM_PROMPT
        )
        
        return await handler(request.override(system_prompt=new_system_prompt))
    
    def wrap_model_call(
        self,
        request: ModelRequest,
        handler: Callable[[ModelRequest], ModelResponse],
    ) -> ModelResponse:
        """Synchronous version - add clarification tools system prompt."""
        new_system_prompt = (
            request.system_prompt + "\n\n" + CLARIFY_SYSTEM_PROMPT
            if request.system_prompt
            else CLARIFY_SYSTEM_PROMPT
        )
        
        return handler(request.override(system_prompt=new_system_prompt))
    
    async def awrap_tool_call(
        self,
        request: ToolCallRequest,
        handler: Callable[[ToolCallRequest], Awaitable[ToolMessage | Command]],
    ) -> ToolMessage | Command:
        """Intercept clarification tool calls for user interaction.
        
        Flow:
        1. Check if this is a clarification tool
        2. If yes, interrupt with question details
        3. When resumed, extract user's response
        4. Return the response as a ToolMessage
        """
        tool_name = request.tool_call.get("name", "")
        tool_call_id = request.tool_call.get("id", "")
        tool_args = request.tool_call.get("args", {})
        
        # Check if this is a clarification tool
        if tool_name not in CLARIFY_TOOLS:
            # Not our tool, pass through
            return await handler(request)
        
        # Build interrupt data based on tool type
        if tool_name == "ask_user":
            interrupt_data = {
                "type": "clarification_request",
                "tool": "ask_user",
                "tool_call_id": tool_call_id,
                "question": tool_args.get("question", ""),
            }
        else:  # ask_choices
            interrupt_data = {
                "type": "clarification_request",
                "tool": "ask_choices",
                "tool_call_id": tool_call_id,
                "question": tool_args.get("question", ""),
                "options": tool_args.get("options", []),
                "allow_multiple": tool_args.get("allow_multiple", False),
                "allow_freeform": tool_args.get("allow_freeform", False),
            }
        
        print(f"[ClarifyMiddleware] Interrupting for {tool_name}: {tool_args.get('question', '')[:50]}...")
        
        # Interrupt and wait for user response
        resume_value = interrupt(interrupt_data)
        
        print(f"[ClarifyMiddleware] Resumed with: {type(resume_value)}")
        
        # Extract response from user
        response_content = _extract_clarify_response(resume_value, tool_name)
        
        return ToolMessage(
            content=response_content,
            tool_call_id=tool_call_id,
            name=tool_name,
        )
    
    def wrap_tool_call(
        self,
        request: ToolCallRequest,
        handler: Callable[[ToolCallRequest], ToolMessage | Command],
    ) -> ToolMessage | Command:
        """Synchronous version of tool call interception."""
        import asyncio
        
        async def async_handler(req: ToolCallRequest) -> ToolMessage | Command:
            return handler(req)
        
        return asyncio.get_event_loop().run_until_complete(
            self.awrap_tool_call(request, async_handler)
        )


def _extract_clarify_response(resume_value: Any, tool_name: str) -> str:
    """Extract user response from resume value.
    
    Expected formats:
    For ask_user:
        { "response": "user's text" }
        OR { "tool_results": [{ "content": "user's text", "tool_call_id": "..." }] }
        OR just a string
    
    For ask_choices:
        { "selected": ["option-id", ...], "freeform": "optional text" }
    """
    import json
    
    if isinstance(resume_value, str):
        return resume_value
    
    if isinstance(resume_value, dict):
        # Handle tool_results format from frontend (this is what resumeWithToolResults sends)
        if "tool_results" in resume_value:
            tool_results = resume_value["tool_results"]
            if isinstance(tool_results, list) and len(tool_results) > 0:
                first_result = tool_results[0]
                if isinstance(first_result, dict) and "content" in first_result:
                    return first_result["content"]
        
        # ask_user format
        if "response" in resume_value:
            return resume_value["response"]
        
        # ask_choices format
        if "selected" in resume_value:
            result = {
                "selected": resume_value.get("selected", []),
            }
            if "freeform" in resume_value and resume_value["freeform"]:
                result["freeform"] = resume_value["freeform"]
            return json.dumps(result)
        
        # Direct content
        if "content" in resume_value:
            return resume_value["content"]
        
        # Error case
        if "error" in resume_value:
            return f"User declined to answer: {resume_value['error']}"
    
    return f"Unexpected response format: {resume_value}"

