"""
Token pricing service for Socratic Seminar.

Provides satoshi-per-token pricing for LLM models based on:
- USD pricing per million tokens (from model_pricing.json)
- Current BTC/USD price (fetched every 5 minutes)

The LangGraph agents call these endpoints to determine current costs.
"""

import asyncio
import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

# Configure logging
logger = logging.getLogger("pricing")
logger.setLevel(logging.INFO)

# Add console handler if not already present
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter(
        "[%(asctime)s] %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    ))
    logger.addHandler(handler)


# =============================================================================
# CONFIGURATION
# =============================================================================

# Path to model pricing config
MODEL_PRICING_PATH = Path(__file__).parent / "model_pricing.json"

# BTC price refresh interval (seconds)
BTC_PRICE_REFRESH_INTERVAL = int(os.getenv("BTC_PRICE_REFRESH_INTERVAL", "300"))  # 5 minutes

# API endpoints
COINBASE_API_URL = "https://api.coinbase.com/v2/prices/BTC-USD/spot"
COINGECKO_API_URL = "https://api.coingecko.com/api/v3/simple/price?ids=bitcoin&vs_currencies=usd"

# Sats per BTC
SATS_PER_BTC = 100_000_000


# =============================================================================
# PRICING SERVICE
# =============================================================================

class PricingService:
    """Service for calculating token prices in satoshis.
    
    Maintains:
    - Current BTC/USD price (refreshed every 5 minutes)
    - Model pricing config (hot-reloadable from JSON)
    """
    
    def __init__(self):
        self._btc_price_usd: Optional[float] = None
        self._btc_price_updated_at: Optional[datetime] = None
        self._btc_price_source: Optional[str] = None
        self._model_pricing: dict = {}
        self._model_pricing_loaded_at: Optional[datetime] = None
        self._background_task: Optional[asyncio.Task] = None
        self._running = False
    
    @property
    def btc_price_usd(self) -> Optional[float]:
        return self._btc_price_usd
    
    @property
    def btc_price_updated_at(self) -> Optional[datetime]:
        return self._btc_price_updated_at
    
    @property
    def btc_price_source(self) -> Optional[str]:
        return self._btc_price_source
    
    def load_model_pricing(self) -> dict:
        """Load model pricing from JSON config file.
        
        This is called on each request to support hot-reloading.
        """
        try:
            with open(MODEL_PRICING_PATH, "r") as f:
                data = json.load(f)
                self._model_pricing = data.get("models", {})
                self._model_pricing_loaded_at = datetime.now(timezone.utc)
                return self._model_pricing
        except FileNotFoundError:
            logger.error(f"Model pricing file not found: {MODEL_PRICING_PATH}")
            return {}
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in model pricing file: {e}")
            return {}
    
    def get_model_pricing(self, model: str) -> Optional[dict]:
        """Get USD pricing for a specific model.
        
        Args:
            model: Model name (e.g., 'gpt-4o', 'grok-2')
            
        Returns:
            Dict with input_usd_per_million and output_usd_per_million, or None
        """
        # Hot-reload config on each request
        self.load_model_pricing()
        return self._model_pricing.get(model)
    
    def get_all_models(self) -> dict:
        """Get pricing for all known models."""
        self.load_model_pricing()
        return self._model_pricing
    
    async def fetch_btc_price(self) -> Optional[float]:
        """Fetch current BTC/USD price from APIs.
        
        Tries Coinbase first, falls back to CoinGecko if that fails.
        
        Returns:
            BTC price in USD, or None if both APIs fail
        """
        async with httpx.AsyncClient(timeout=10.0) as client:
            # Try Coinbase first
            try:
                response = await client.get(COINBASE_API_URL)
                response.raise_for_status()
                data = response.json()
                price = float(data["data"]["amount"])
                self._btc_price_source = "coinbase"
                logger.info(f"Fetched BTC price from Coinbase: ${price:,.2f}")
                return price
            except Exception as e:
                logger.warning(f"Coinbase API failed: {e}, trying CoinGecko...")
            
            # Fallback to CoinGecko
            try:
                response = await client.get(COINGECKO_API_URL)
                response.raise_for_status()
                data = response.json()
                price = float(data["bitcoin"]["usd"])
                self._btc_price_source = "coingecko"
                logger.info(f"Fetched BTC price from CoinGecko (fallback): ${price:,.2f}")
                return price
            except Exception as e:
                logger.error(f"CoinGecko API also failed: {e}")
                return None
    
    async def update_btc_price(self) -> bool:
        """Update the cached BTC price.
        
        Returns:
            True if price was successfully updated
        """
        price = await self.fetch_btc_price()
        if price is not None:
            self._btc_price_usd = price
            self._btc_price_updated_at = datetime.now(timezone.utc)
            
            # Log current sats-per-token calculations for all models
            self._log_token_prices()
            return True
        return False
    
    def _log_token_prices(self):
        """Log current sats-per-token for all models."""
        if not self._btc_price_usd:
            return
        
        self.load_model_pricing()
        
        logger.info("=" * 60)
        logger.info(f"Token Pricing Update | BTC: ${self._btc_price_usd:,.2f} | Source: {self._btc_price_source}")
        logger.info("-" * 60)
        logger.info(f"{'Model':<35} {'Input (sats/token)':<20} {'Output (sats/token)':<20}")
        logger.info("-" * 60)
        
        for model, pricing in self._model_pricing.items():
            input_sats = self.calculate_sats_per_token(pricing["input_usd_per_million"])
            output_sats = self.calculate_sats_per_token(pricing["output_usd_per_million"])
            logger.info(f"{model:<35} {input_sats:<20.8f} {output_sats:<20.8f}")
        
        logger.info("=" * 60)
    
    def calculate_sats_per_token(self, usd_per_million: float) -> float:
        """Calculate satoshis per token from USD per million tokens.
        
        Formula: (usd_per_million / 1_000_000) / btc_price_usd * 100_000_000
        
        Args:
            usd_per_million: USD cost per million tokens
            
        Returns:
            Satoshis per single token
        """
        if not self._btc_price_usd or self._btc_price_usd <= 0:
            return 0.0
        
        usd_per_token = usd_per_million / 1_000_000
        btc_per_token = usd_per_token / self._btc_price_usd
        sats_per_token = btc_per_token * SATS_PER_BTC
        return sats_per_token
    
    async def start_background_refresh(self):
        """Start the background task that refreshes BTC price periodically."""
        if self._running:
            return
        
        self._running = True
        
        # Initial fetch
        logger.info("Starting BTC price background refresh service...")
        await self.update_btc_price()
        
        # Start background loop
        self._background_task = asyncio.create_task(self._refresh_loop())
    
    async def stop_background_refresh(self):
        """Stop the background refresh task."""
        self._running = False
        if self._background_task:
            self._background_task.cancel()
            try:
                await self._background_task
            except asyncio.CancelledError:
                pass
            self._background_task = None
        logger.info("Stopped BTC price background refresh service")
    
    async def _refresh_loop(self):
        """Background loop that fetches BTC price every interval."""
        while self._running:
            await asyncio.sleep(BTC_PRICE_REFRESH_INTERVAL)
            if self._running:
                logger.info(f"Refreshing BTC price (interval: {BTC_PRICE_REFRESH_INTERVAL}s)...")
                await self.update_btc_price()


# Global service instance
pricing_service = PricingService()


# =============================================================================
# API MODELS
# =============================================================================

class TokenPricingResponse(BaseModel):
    """Response for token pricing endpoint."""
    model: str
    input_sats_per_token: float
    output_sats_per_token: float
    btc_price_usd: float
    btc_price_source: str
    updated_at: str


class BTCPriceResponse(BaseModel):
    """Response for BTC price endpoint."""
    btc_price_usd: float
    source: str
    updated_at: str


class ModelPricingInfo(BaseModel):
    """Model pricing information."""
    input_usd_per_million: float
    output_usd_per_million: float


class ModelsResponse(BaseModel):
    """Response for models listing endpoint."""
    models: dict[str, ModelPricingInfo]


# =============================================================================
# API ROUTER
# =============================================================================

pricing_router = APIRouter()


@pricing_router.get("/tokens", response_model=TokenPricingResponse)
async def get_token_pricing(model: str) -> TokenPricingResponse:
    """Get satoshi-per-token pricing for a specific model.
    
    Args:
        model: Model name (e.g., 'gpt-4o', 'grok-4-1-fast-non-reasoning')
        
    Returns:
        Token pricing in satoshis for both input and output tokens
        
    Raises:
        404: Model not found in pricing config
        503: BTC price not available yet
    """
    # Check if BTC price is available
    if pricing_service.btc_price_usd is None:
        raise HTTPException(
            status_code=503,
            detail="BTC price not available yet. Please try again shortly."
        )
    
    # Get model pricing
    model_pricing = pricing_service.get_model_pricing(model)
    if model_pricing is None:
        raise HTTPException(
            status_code=404,
            detail=f"Model '{model}' not found in pricing config. Use GET /api/pricing/models to see available models."
        )
    
    # Calculate sats per token
    input_sats = pricing_service.calculate_sats_per_token(model_pricing["input_usd_per_million"])
    output_sats = pricing_service.calculate_sats_per_token(model_pricing["output_usd_per_million"])
    
    return TokenPricingResponse(
        model=model,
        input_sats_per_token=input_sats,
        output_sats_per_token=output_sats,
        btc_price_usd=pricing_service.btc_price_usd,
        btc_price_source=pricing_service.btc_price_source or "unknown",
        updated_at=pricing_service.btc_price_updated_at.isoformat() if pricing_service.btc_price_updated_at else "",
    )


@pricing_router.get("/btc", response_model=BTCPriceResponse)
async def get_btc_price() -> BTCPriceResponse:
    """Get current BTC/USD price.
    
    Returns:
        Current BTC price, source, and last update time
        
    Raises:
        503: BTC price not available yet
    """
    if pricing_service.btc_price_usd is None:
        raise HTTPException(
            status_code=503,
            detail="BTC price not available yet. Please try again shortly."
        )
    
    return BTCPriceResponse(
        btc_price_usd=pricing_service.btc_price_usd,
        source=pricing_service.btc_price_source or "unknown",
        updated_at=pricing_service.btc_price_updated_at.isoformat() if pricing_service.btc_price_updated_at else "",
    )


@pricing_router.get("/models", response_model=ModelsResponse)
async def list_models() -> ModelsResponse:
    """List all known models and their USD pricing.
    
    Returns:
        Dict of all models with their input/output USD pricing per million tokens
    """
    models = pricing_service.get_all_models()
    return ModelsResponse(
        models={
            name: ModelPricingInfo(
                input_usd_per_million=pricing["input_usd_per_million"],
                output_usd_per_million=pricing["output_usd_per_million"],
            )
            for name, pricing in models.items()
        }
    )


@pricing_router.post("/refresh")
async def refresh_btc_price():
    """Manually trigger a BTC price refresh.
    
    Returns:
        New BTC price after refresh
    """
    success = await pricing_service.update_btc_price()
    if not success:
        raise HTTPException(
            status_code=503,
            detail="Failed to fetch BTC price from all sources"
        )
    
    return {
        "success": True,
        "btc_price_usd": pricing_service.btc_price_usd,
        "source": pricing_service.btc_price_source,
        "updated_at": pricing_service.btc_price_updated_at.isoformat() if pricing_service.btc_price_updated_at else "",
    }

