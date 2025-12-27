# Agent Architecture

## LangGraph Configuration

```json
{
  "python_version": "3.11",
  "dependencies": ["."],
  "graphs": {
    "seminar_agent": "./src/seminar/graph.py:graph"
  }
}
```

## Graph Structure

```
__start__
    │
    ▼
validate_payment ──► (invalid) ──► END
    │
    │ (valid)
    ▼
  agent
    │
    ▼
redeem_payment
    │
    ▼
   END
```

## State Definition

```python
class AgentState(TypedDict, total=False):
    # Conversation
    messages: Annotated[Sequence[BaseMessage], add_messages]
    
    # Payment
    payment: Optional[PaymentInfo]
    payment_validated: bool
    payment_token: Optional[str]
    
    # Artifact context
    artifact: Optional[Artifact]
    highlighted_text: Optional[str]
    
    # Control
    next: Optional[str]
    run_id: Optional[str]
    refund: bool
```

## Payment Validation Node

```python
async def validate_payment_node(state, config) -> dict:
    payment = state.get("payment")
    
    # Free mode for development
    if not payment or not payment.get("ecash_token"):
        return {"payment_validated": True, "payment_token": None}
    
    # Debug tokens
    if token.startswith("cashu_debug_"):
        return {"payment_validated": True, "payment_token": None}
    
    # Production: call backend wallet service
    # is_valid = await validate_with_backend(token)
    
    return {
        "payment_validated": True,
        "payment_token": token,  # For redemption after success
    }
```

## Agent Node

The main agent node:
1. Gets the configured model (OpenAI-compatible endpoint)
2. Builds system prompt for Socratic dialogue
3. Includes artifact context if available
4. Returns AI response

## Future Enhancements

- **Artifact tools** - Create, update, fork artifacts
- **deepagents integration** - Planning, filesystem, subagents
- **Memory** - User preferences and conversation history

