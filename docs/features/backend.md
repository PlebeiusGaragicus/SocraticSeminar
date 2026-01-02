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

---

# *ecash*

**Nutshell is a Chaumian Ecash wallet and mint for Bitcoin Lightning based on the Cashu protocol.**

<a href="https://pypi.org/project/cashu/"><img alt="Release" src="https://img.shields.io/pypi/v/cashu?color=black"></a> <a href="https://pepy.tech/project/cashu"> <img alt="Downloads" src="https://pepy.tech/badge/cashu"></a> <a href="https://app.codecov.io/gh/cashubtc/nutshell"><img alt="Coverage" src="https://img.shields.io/codecov/c/gh/cashubtc/nutshell"></a>

Cashu is a free and open-source [Ecash protocol](https://github.com/cashubtc/nuts) based on David Wagner's variant of Chaumian blinding called [Blind Diffie-Hellman Key Exchange](https://cypherpunks.venona.com/date/1996/03/msg01848.html) scheme written down [here](https://gist.github.com/RubenSomsen/be7a4760dd4596d06963d67baf140406).
