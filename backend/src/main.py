"""
FastAPI backend for Socratic Seminar.

This backend provides:
- Wallet service for eCash token validation and redemption
- Called by LangGraph agents, not by the frontend directly
"""

import os
import sys
from contextlib import asynccontextmanager
from typing import Optional

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# Add nutshell to path (from submodule)
NUTSHELL_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "nutshell")
if os.path.exists(NUTSHELL_PATH):
    sys.path.insert(0, NUTSHELL_PATH)

load_dotenv()

from .wallet import wallet_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    print("[Backend] Starting Socratic Seminar backend...")
    yield
    print("[Backend] Shutting down...")


app = FastAPI(
    title="Socratic Seminar Backend",
    description="Wallet service for eCash payments",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS - allow LangGraph agents to call this service
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, restrict to LangGraph server
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(wallet_router, prefix="/api/wallet", tags=["wallet"])


@app.get("/")
async def root():
    """Health check endpoint."""
    return {"status": "ok", "service": "socratic-seminar-backend"}


@app.get("/health")
async def health():
    """Health check for monitoring."""
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn
    
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run(app, host="0.0.0.0", port=port)

