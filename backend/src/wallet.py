"""
Wallet service for Cashu eCash token operations.

Uses the nutshell library (submodule) for Cashu protocol operations.
For development, accepts all tokens without validation.
"""

import os
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

# Configuration
MINT_URL = os.getenv("MINT_URL", "https://mint.minibits.cash/Bitcoin")
WALLET_DB_PATH = os.getenv("WALLET_DB_PATH", "data/wallet")
DEV_MODE = os.getenv("DEV_MODE", "true").lower() == "true"


wallet_router = APIRouter()


class TokenRequest(BaseModel):
    """Request body for token operations."""
    token: str


class ValidateResponse(BaseModel):
    """Response for token validation."""
    valid: bool
    amount: Optional[int] = None
    mint: Optional[str] = None
    error: Optional[str] = None


class ReceiveResponse(BaseModel):
    """Response for token redemption."""
    success: bool
    amount: Optional[int] = None
    error: Optional[str] = None


@wallet_router.post("/validate", response_model=ValidateResponse)
async def validate_token(request: TokenRequest) -> ValidateResponse:
    """
    Validate a Cashu token without redeeming it.
    
    In development mode, accepts all tokens.
    In production, uses nutshell to check token state.
    """
    token = request.token
    
    if not token:
        return ValidateResponse(valid=False, error="No token provided")
    
    # Debug tokens
    if token.startswith("cashu_debug_") or token == "debug":
        return ValidateResponse(
            valid=True,
            amount=10,
            mint="debug",
        )
    
    # Development mode: accept all tokens
    if DEV_MODE:
        print(f"[Wallet] DEV MODE - accepting token without validation")
        # Try to parse amount from token if it's a real cashu token
        amount = _estimate_token_amount(token)
        return ValidateResponse(
            valid=True,
            amount=amount,
            mint=MINT_URL,
        )
    
    # Production: Use nutshell to validate
    try:
        from cashu.wallet.helpers import deserialize_token
        from cashu.core.helpers import sum_proofs
        
        token_obj = deserialize_token(token)
        amount = sum_proofs(token_obj.proofs)
        mint = token_obj.mint if hasattr(token_obj, 'mint') else MINT_URL
        
        # TODO: Check token state with mint (not spent)
        # For now, just verify it parses correctly
        
        return ValidateResponse(
            valid=True,
            amount=amount,
            mint=mint,
        )
    except Exception as e:
        print(f"[Wallet] Validation error: {e}")
        return ValidateResponse(
            valid=False,
            error=str(e),
        )


@wallet_router.post("/receive", response_model=ReceiveResponse)
async def receive_token(request: TokenRequest) -> ReceiveResponse:
    """
    Receive (redeem) a Cashu token into the backend wallet.
    
    In development mode, simulates success.
    In production, uses nutshell to redeem the token.
    """
    token = request.token
    
    if not token:
        return ReceiveResponse(success=False, error="No token provided")
    
    # Debug tokens
    if token.startswith("cashu_debug_") or token == "debug":
        return ReceiveResponse(success=True, amount=10)
    
    # Development mode: simulate success
    if DEV_MODE:
        print(f"[Wallet] DEV MODE - simulating token redemption")
        amount = _estimate_token_amount(token)
        return ReceiveResponse(success=True, amount=amount)
    
    # Production: Use nutshell to receive
    try:
        from cashu.wallet.wallet import Wallet
        from cashu.wallet.helpers import receive, deserialize_token
        from cashu.core.helpers import sum_proofs
        
        # Initialize wallet
        wallet = await Wallet.with_db(
            url=MINT_URL,
            db=WALLET_DB_PATH,
        )
        await wallet.load_mint()
        
        # Deserialize and receive token
        token_obj = deserialize_token(token)
        await receive(wallet, token_obj)
        
        amount = sum_proofs(token_obj.proofs)
        print(f"[Wallet] Received {amount} sats")
        
        return ReceiveResponse(success=True, amount=amount)
        
    except Exception as e:
        print(f"[Wallet] Receive error: {e}")
        return ReceiveResponse(success=False, error=str(e))


@wallet_router.get("/balance")
async def get_balance():
    """Get the current wallet balance."""
    
    if DEV_MODE:
        return {"balance": 0, "dev_mode": True}
    
    try:
        from cashu.wallet.wallet import Wallet
        
        wallet = await Wallet.with_db(
            url=MINT_URL,
            db=WALLET_DB_PATH,
        )
        await wallet.load_proofs()
        
        balance = wallet.balance
        return {"balance": balance, "mint": MINT_URL}
        
    except Exception as e:
        print(f"[Wallet] Balance error: {e}")
        return {"balance": 0, "error": str(e)}


def _estimate_token_amount(token: str) -> int:
    """
    Try to estimate token amount from a cashu token.
    Returns 0 if unable to parse.
    """
    try:
        from cashu.wallet.helpers import deserialize_token
        from cashu.core.helpers import sum_proofs
        
        token_obj = deserialize_token(token)
        return sum_proofs(token_obj.proofs)
    except Exception:
        return 0

