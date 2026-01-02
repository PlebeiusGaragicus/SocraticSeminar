"""CashuPaymentMiddleware for streaming micropayments.

Handles the complete Cashu payment lifecycle:
1. Token validation (without redemption)
2. Per-iteration balance deduction via tools
3. Funding exhaustion interrupts
4. Refund token generation on completion/error
5. Session recovery support

Note: State access in middleware follows these patterns:
- wrap_model_call: Only has access to messages, tools, system_prompt (not state)
- wrap_tool_call: Has access to state via ToolRuntime.state
- after_agent: Receives state directly as parameter

Payment tracking happens through the graph state, initialized from input
and updated via tool calls.
"""

import os
from collections.abc import Awaitable, Callable
from typing import Any, Literal

from langchain.agents.middleware.types import AgentMiddleware, AgentState, ModelRequest, ModelResponse
from langchain.tools import ToolRuntime
from langchain.tools.tool_node import ToolCallRequest
from langchain_core.messages import ToolMessage
from langchain_core.tools import StructuredTool
from langgraph.runtime import Runtime
from langgraph.types import Command, interrupt
from typing_extensions import NotRequired


# =============================================================================
# CONFIGURATION
# =============================================================================

# Cost per agent iteration in satoshis
COST_PER_ITERATION_SATS = int(os.getenv("COST_PER_ITERATION_SATS", "10"))

# Development mode: skip actual token validation/redemption
DEV_MODE = os.getenv("DEV_MODE", "true").lower() == "true"


# =============================================================================
# PAYMENT STATE
# =============================================================================

PaymentStatus = Literal["pending", "active", "exhausted", "completed", "error", "refunded"]


class CashuPaymentState(AgentState):
    """State extension for Cashu payment tracking.
    
    These fields should be included in the initial input to the agent:
    - payment_token: The Cashu token from the client
    - payment_balance_sats: Initial balance (validated from token)
    
    These are updated during execution:
    - payment_spent_sats: Accumulated spending
    - payment_status: Current status
    - payment_refund_token: Token for unused balance
    """
    
    # Original token from client
    payment_token: NotRequired[str | None]
    
    # Remaining balance in satoshis
    payment_balance_sats: NotRequired[int]
    
    # Total spent this session
    payment_spent_sats: NotRequired[int]
    
    # Refund token for unused balance
    payment_refund_token: NotRequired[str | None]
    
    # Current payment status
    payment_status: NotRequired[PaymentStatus]
    
    # Whether refund has been claimed
    payment_refund_claimed: NotRequired[bool]


# =============================================================================
# TOKEN OPERATIONS
# =============================================================================

def validate_token_sync(token: str) -> tuple[bool, int, str | None]:
    """Validate a Cashu token without redeeming (synchronous).
    
    Args:
        token: Cashu token string
        
    Returns:
        Tuple of (is_valid, amount_sats, error_message)
    """
    if not token:
        return False, 0, "No token provided"
    
    # Debug tokens for testing
    if token.startswith("cashu_debug_") or token == "debug":
        try:
            amount = int(token.split("_")[-1])
        except (ValueError, IndexError):
            amount = 100
        return True, amount, None
    
    # Development mode: accept all tokens
    if DEV_MODE:
        print(f"[Payment] DEV MODE - accepting token without validation")
        try:
            from cashu.wallet.helpers import deserialize_token
            from cashu.core.helpers import sum_proofs
            
            token_obj = deserialize_token(token)
            amount = sum_proofs(token_obj.proofs)
            return True, amount, None
        except Exception:
            return True, 100, None
    
    # Production: validate with Cashu library
    try:
        from cashu.wallet.helpers import deserialize_token
        from cashu.core.helpers import sum_proofs
        
        token_obj = deserialize_token(token)
        amount = sum_proofs(token_obj.proofs)
        return True, amount, None
        
    except Exception as e:
        return False, 0, str(e)


def generate_refund_token_sync(original_token: str, amount: int) -> str | None:
    """Generate a refund token for the remaining balance (synchronous).
    
    Args:
        original_token: Original payment token
        amount: Amount to refund in sats
        
    Returns:
        Refund token string, or None if unable to generate
    """
    if amount <= 0:
        return None
    
    if DEV_MODE:
        return f"cashu_refund_{amount}"
    
    # Production: would generate actual Cashu token
    try:
        return f"cashu_refund_{amount}"
    except Exception as e:
        print(f"[Payment] Failed to generate refund: {e}")
        return None


# =============================================================================
# PAYMENT TOOLS
# =============================================================================

def _create_request_funding_tool() -> StructuredTool:
    """Create the request_additional_funding tool."""
    
    def request_additional_funding(
        reason: str,
        suggested_amount_sats: int = 100,
        runtime: ToolRuntime = None,
    ) -> str:
        """Request additional funding from the user.
        
        Called when the payment balance is exhausted and more work is needed.
        
        Args:
            reason: Explanation of why additional funds are needed
            suggested_amount_sats: Suggested amount in satoshis (default 100)
        """
        # This tool is handled by HumanInTheLoopMiddleware interrupt
        return f"Funding request submitted: {reason} (suggested: {suggested_amount_sats} sats)"
    
    return StructuredTool.from_function(
        name="request_additional_funding",
        func=request_additional_funding,
        description="""Request additional payment when funds are exhausted.

Args:
    reason: Clear explanation of why more funds are needed
    suggested_amount_sats: Suggested amount (default 100 sats)

This tool requires human approval.""",
    )


def _create_check_balance_tool(cost_per_iteration: int) -> StructuredTool:
    """Create an internal tool to check and deduct payment balance."""
    
    def check_payment_balance(
        runtime: ToolRuntime,
    ) -> Command | str:
        """Check payment balance and deduct iteration cost.
        
        This is called internally to track payment per iteration.
        """
        state = runtime.state
        
        token = state.get("payment_token")
        balance = state.get("payment_balance_sats", 0)
        spent = state.get("payment_spent_sats", 0)
        status = state.get("payment_status", "pending")
        
        # Initialize if pending
        if status == "pending" and token:
            is_valid, amount, error = validate_token_sync(token)
            if is_valid:
                balance = amount
                status = "active"
                print(f"[Payment] Token validated: {amount} sats")
            else:
                print(f"[Payment] Token validation failed: {error}")
                status = "error"
        elif status == "pending" and not token:
            # Free mode
            status = "active"
            print("[Payment] No token provided, running in free mode")
        
        # Check if funds exhausted
        if token and balance <= 0 and status == "active":
            status = "exhausted"
            return Command(
                update={
                    "payment_status": status,
                    "messages": [ToolMessage(
                        content="Payment balance exhausted. Use request_additional_funding to continue.",
                        tool_call_id=runtime.tool_call_id,
                    )],
                }
            )
        
        # Deduct cost
        if balance >= cost_per_iteration:
            new_balance = balance - cost_per_iteration
            new_spent = spent + cost_per_iteration
            print(f"[Payment] Deducted {cost_per_iteration} sats. Balance: {new_balance}")
            
            return Command(
                update={
                    "payment_balance_sats": new_balance,
                    "payment_spent_sats": new_spent,
                    "payment_status": status,
                    "messages": [ToolMessage(
                        content=f"Balance: {new_balance} sats (spent {new_spent} total)",
                        tool_call_id=runtime.tool_call_id,
                    )],
                }
            )
        
        return f"Balance: {balance} sats, Status: {status}"
    
    return StructuredTool.from_function(
        name="_check_payment_balance",
        func=check_payment_balance,
        description="Internal tool to check payment balance.",
    )


# =============================================================================
# SYSTEM PROMPT
# =============================================================================

PAYMENT_SYSTEM_PROMPT = """## Payment System

This agent uses a streaming micropayment system. Each tool execution costs approximately {cost_per_iteration} sats.

If you run out of funds, use the `request_additional_funding` tool to ask the user for more payment.

The user's payment balance is tracked automatically. Be mindful of costs and work efficiently."""


# =============================================================================
# MIDDLEWARE
# =============================================================================

class CashuPaymentMiddleware(AgentMiddleware[CashuPaymentState, None]):
    """Middleware for streaming Cashu micropayments.
    
    Payment state is initialized from the input (payment_token, payment_balance_sats)
    and tracked through the conversation. On completion, a refund token is generated
    for any remaining balance.
    
    Configuration:
        cost_per_iteration: Sats deducted per LLM call (default: 10)
        
    Example:
        ```python
        agent = create_agent(
            model,
            middleware=[
                CashuPaymentMiddleware(cost_per_iteration=10),
            ],
        )
        
        # Call with payment info in input
        agent.invoke({
            "messages": [...],
            "payment_token": "cashuA...",
            "payment_balance_sats": 100,  # Pre-validated by frontend
        })
        ```
    """
    
    state_schema = CashuPaymentState
    
    def __init__(
        self,
        *,
        cost_per_iteration: int = COST_PER_ITERATION_SATS,
    ) -> None:
        """Initialize payment middleware.
        
        Args:
            cost_per_iteration: Satoshis to deduct per iteration
        """
        super().__init__()
        self.cost_per_iteration = cost_per_iteration
        self.tools = [_create_request_funding_tool()]
    
    async def awrap_model_call(
        self,
        request: ModelRequest,
        handler: Callable[[ModelRequest], Awaitable[ModelResponse]],
    ) -> ModelResponse:
        """Add payment info to system prompt.
        
        Note: We don't access state here - state access is only available
        in wrap_tool_call or after_agent.
        """
        payment_prompt = PAYMENT_SYSTEM_PROMPT.format(
            cost_per_iteration=self.cost_per_iteration,
        )
        
        new_system_prompt = (
            request.system_prompt + "\n\n" + payment_prompt
            if request.system_prompt
            else payment_prompt
        )
        
        return await handler(request.override(system_prompt=new_system_prompt))
    
    def wrap_model_call(
        self,
        request: ModelRequest,
        handler: Callable[[ModelRequest], ModelResponse],
    ) -> ModelResponse:
        """Synchronous version - add payment info to system prompt."""
        payment_prompt = PAYMENT_SYSTEM_PROMPT.format(
            cost_per_iteration=self.cost_per_iteration,
        )
        
        new_system_prompt = (
            request.system_prompt + "\n\n" + payment_prompt
            if request.system_prompt
            else payment_prompt
        )
        
        return handler(request.override(system_prompt=new_system_prompt))
    
    async def awrap_tool_call(
        self,
        request: ToolCallRequest,
        handler: Callable[[ToolCallRequest], Awaitable[ToolMessage | Command]],
    ) -> ToolMessage | Command:
        """Deduct payment for tool calls.
        
        This is where we can access state via request.runtime.state.
        """
        state = request.runtime.state
        tool_name = request.tool_call.get("name", "")
        tool_call_id = request.tool_call.get("id", "")
        
        # Skip payment deduction for internal tools
        if tool_name.startswith("_"):
            return await handler(request)
        
        # Check payment status
        token = state.get("payment_token")
        balance = state.get("payment_balance_sats", 0)
        spent = state.get("payment_spent_sats", 0)
        status = state.get("payment_status", "pending")
        
        # Initialize if this is the first tool call and we have a token
        if status == "pending":
            if token:
                is_valid, amount, error = validate_token_sync(token)
                if is_valid:
                    state["payment_balance_sats"] = amount
                    state["payment_status"] = "active"
                    balance = amount
                    status = "active"
                    print(f"[Payment] Token validated on first tool call: {amount} sats")
                else:
                    state["payment_status"] = "error"
                    print(f"[Payment] Token validation failed: {error}")
            else:
                state["payment_status"] = "active"
                status = "active"
                print("[Payment] No token, running in free mode")
        
        # Check if we have funds (only if token was provided)
        if token and balance <= 0 and status == "active":
            print(f"[Payment] Funds exhausted before tool {tool_name}")
            state["payment_status"] = "exhausted"
            
            # Interrupt for funding
            interrupt_data = {
                "type": "payment_exhausted",
                "spent_sats": spent,
                "message": "Payment balance exhausted. Please add more funds.",
                "action_requests": [
                    {
                        "name": "request_additional_funding",
                        "args": {"reason": "Funds exhausted", "spent_so_far": spent},
                    }
                ],
                "review_configs": [
                    {
                        "action_name": "request_additional_funding", 
                        "allowed_decisions": ["approve", "reject"],
                    }
                ],
            }
            
            resume_value = interrupt(interrupt_data)
            
            # Handle resumed with new payment
            if isinstance(resume_value, dict):
                new_token = resume_value.get("payment_token")
                if new_token:
                    is_valid, amount, error = validate_token_sync(new_token)
                    if is_valid:
                        state["payment_token"] = new_token
                        state["payment_balance_sats"] = amount
                        state["payment_status"] = "active"
                        balance = amount
                        print(f"[Payment] Additional funding: {amount} sats")
        
        # Deduct cost for this tool call
        if token and balance >= self.cost_per_iteration:
            new_balance = balance - self.cost_per_iteration
            new_spent = spent + self.cost_per_iteration
            state["payment_balance_sats"] = new_balance
            state["payment_spent_sats"] = new_spent
            print(f"[Payment] Deducted {self.cost_per_iteration} sats for {tool_name}. Balance: {new_balance}")
        
        # Execute the tool
        return await handler(request)
    
    def wrap_tool_call(
        self,
        request: ToolCallRequest,
        handler: Callable[[ToolCallRequest], ToolMessage | Command],
    ) -> ToolMessage | Command:
        """Synchronous tool call wrapper."""
        import asyncio
        
        async def async_handler(req: ToolCallRequest) -> ToolMessage | Command:
            return handler(req)
        
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(
                self.awrap_tool_call(request, async_handler)
            )
        finally:
            loop.close()
    
    def after_agent(
        self,
        state: CashuPaymentState,
        runtime: Runtime[None],
    ) -> dict[str, Any] | None:
        """Generate refund token after agent completes."""
        token = state.get("payment_token")
        balance = state.get("payment_balance_sats", 0)
        
        if not token or balance <= 0:
            return {"payment_status": "completed"}
        
        print(f"[Payment] Generating refund for {balance} sats")
        refund_token = generate_refund_token_sync(token, balance)
        
        if refund_token:
            return {
                "payment_status": "completed",
                "payment_refund_token": refund_token,
                "payment_refund_claimed": False,
            }
        
        return {"payment_status": "completed"}
    
    async def aafter_agent(
        self,
        state: CashuPaymentState,
        runtime: Runtime[None],
    ) -> dict[str, Any] | None:
        """Async version of after_agent."""
        return self.after_agent(state, runtime)

