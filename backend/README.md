# Socratic Seminar Backend

FastAPI backend providing wallet services for eCash payments.

## Overview

This backend is called by **LangGraph agents**, not by the frontend directly.

The frontend calls LangGraph → LangGraph's validate_payment node calls this backend.

## Endpoints

- `POST /api/wallet/validate` - Validate a Cashu token without redeeming
- `POST /api/wallet/receive` - Redeem a Cashu token to the wallet
- `GET /api/wallet/balance` - Get current wallet balance

## Development

```bash
# Install dependencies
pip install -e .

# Run the server (development mode accepts all tokens)
DEV_MODE=true uvicorn src.main:app --reload --port 8000
```

## Configuration

Environment variables:
- `DEV_MODE` - If "true", accept all tokens without validation (default: true)
- `MINT_URL` - Cashu mint URL (default: https://mint.minibits.cash/Bitcoin)
- `WALLET_DB_PATH` - Path to wallet database (default: data/wallet)
- `PORT` - Server port (default: 8000)

