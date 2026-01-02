# Backend Architecture

## Purpose

The backend is a **minimal wallet service** called by LangGraph agents. It does NOT proxy frontend requests.

## Endpoints

### `POST /api/wallet/validate`
Validate a Cashu token without redeeming.

```json
// Request
{ "token": "cashuA..." }

// Response
{ "valid": true, "amount": 10, "mint": "https://mint.example.com" }
```

### `POST /api/wallet/receive`
Redeem a Cashu token to the backend wallet.

```json
// Request
{ "token": "cashuA..." }

// Response
{ "success": true, "amount": 10 }
```

### `GET /api/wallet/balance`
Get current wallet balance.

```json
{ "balance": 1000, "mint": "https://mint.example.com" }
```

## nutshell Integration

Uses the nutshell library (Cashu reference implementation):

```python
from cashu.wallet.wallet import Wallet
from cashu.wallet.helpers import receive, deserialize_token

# Initialize wallet
wallet = await Wallet.with_db(url=MINT_URL, db="data/wallet")
await wallet.load_mint()

# Receive token
token = deserialize_token(token_str)
await receive(wallet, token)
```

## Development Mode

Set `DEV_MODE=true` to:
- Accept all tokens without validation
- Skip actual mint communication
- Simulate successful redemption

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `DEV_MODE` | `true` | Skip real validation |
| `MINT_URL` | minibits | Cashu mint URL |
| `WALLET_DB_PATH` | `data/wallet` | SQLite wallet path |
| `PORT` | `8000` | Server port |

