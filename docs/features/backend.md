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

---

## Pricing Endpoints

Token pricing in satoshis, calculated from USD pricing and live BTC price.

### `GET /api/pricing/tokens`
Get satoshi-per-token pricing for a specific model. Called by LangGraph agents to determine costs.

```json
// Request
GET /api/pricing/tokens?model=gpt-4o

// Response
{
  "model": "gpt-4o",
  "input_sats_per_token": 0.0025,
  "output_sats_per_token": 0.01,
  "btc_price_usd": 100000,
  "btc_price_source": "coinbase",
  "updated_at": "2026-01-02T12:00:00Z"
}
```

### `GET /api/pricing/btc`
Get current BTC/USD price and source.

```json
{
  "btc_price_usd": 100000,
  "source": "coinbase",
  "updated_at": "2026-01-02T12:00:00Z"
}
```

### `GET /api/pricing/models`
List all known models and their USD pricing.

```json
{
  "models": {
    "gpt-4o": {
      "input_usd_per_million": 2.5,
      "output_usd_per_million": 10.0
    },
    "grok-4-1-fast-non-reasoning": {
      "input_usd_per_million": 0.2,
      "output_usd_per_million": 0.5
    }
  }
}
```

### `POST /api/pricing/refresh`
Manually trigger a BTC price refresh (for testing).

```json
{
  "success": true,
  "btc_price_usd": 100000,
  "source": "coinbase",
  "updated_at": "2026-01-02T12:00:00Z"
}
```

## Pricing Calculation

Satoshis per token is calculated as:

```
sats_per_token = (usd_per_million / 1,000,000) / btc_price_usd * 100,000,000
```

Example: GPT-4o input at $2.50/M tokens, BTC at $100k:
- `(2.50 / 1,000,000) / 100,000 * 100,000,000 = 0.0025 sats per token`

## Model Pricing Config

Model pricing is stored in `backend/src/model_pricing.json` and hot-reloaded on each request:

```json
{
  "models": {
    "gpt-4o": {
      "input_usd_per_million": 2.50,
      "output_usd_per_million": 10.00
    }
  }
}
```

---

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
| `BTC_PRICE_REFRESH_INTERVAL` | `300` | BTC price refresh interval in seconds (5 min) |

---

# *ecash*

**Nutshell is a Chaumian Ecash wallet and mint for Bitcoin Lightning based on the Cashu protocol.**

<a href="https://pypi.org/project/cashu/"><img alt="Release" src="https://img.shields.io/pypi/v/cashu?color=black"></a> <a href="https://pepy.tech/project/cashu"> <img alt="Downloads" src="https://pepy.tech/badge/cashu"></a> <a href="https://app.codecov.io/gh/cashubtc/nutshell"><img alt="Coverage" src="https://img.shields.io/codecov/c/gh/cashubtc/nutshell"></a>

Cashu is a free and open-source [Ecash protocol](https://github.com/cashubtc/nuts) based on David Wagner's variant of Chaumian blinding called [Blind Diffie-Hellman Key Exchange](https://cypherpunks.venona.com/date/1996/03/msg01848.html) scheme written down [here](https://gist.github.com/RubenSomsen/be7a4760dd4596d06963d67baf140406).
