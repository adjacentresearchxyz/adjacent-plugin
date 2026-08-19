---
name: kalshi-api
description: Use when calling Kalshi HTTP endpoints for orders, cancels, or settlement reads.
version: 1.0.0
category: software-development
allowed-tools:
  - Bash
---

# Kalshi API

Kalshi HTTP API conventions for direct-index replication. Use V2.

## V1 vs V2

| Endpoint | Status | Use |
| --- | --- | --- |
| `/v1/*` | deprecated | never. |
| `/v2/portfolio/orders` | canonical | place orders, list orders |
| `/v2/portfolio/positions` | canonical | live positions |
| `/v2/portfolio/balance` | canonical | NAV/balance |
| `/v2/markets` | canonical | market metadata |
| `/v2/markets/{ticker}/candlesticks` | canonical | price history |

Use V2. V1 will return 410 Gone for some endpoints as of mid-2026.

## Candlesticks shape

`GET /v2/markets/{ticker}/candlesticks` requires `start_ts` (unix seconds)
and returns period rows with dollar fields, not the older cent fields:

```json
{
  "end_period_ts": 1720000000,
  "yes_bid_dollars": "0.42",
  "yes_ask_dollars": "0.44",
  "yes_close_dollars": "0.43",
  "volume": 120
}
```

Always pass `start_ts`. Prefer `yes_*_dollars` for mid construction
(`(yes_bid_dollars + yes_ask_dollars) / 2`). `scripts/candles-chart.py`
already understands this shape and the Adjacent MCP candle payload.

## Authentication: RSA-PSS

Each request carries a `KALSHI-ACCESS-KEY` header (the API key id), and
the request body is signed with RSA-PSS using a per-account RSA key
stored at `KALSHI_RSA_KEY_PATH` (typically `~/.kalshi/kalshi_rsa.key`).

Headers:

```
KALSHI-ACCESS-KEY: <KALSHI_API_KEY>
KALSHI-ACCESS-TIMESTAMP: <unix_ms>
KALSHI-ACCESS-SIGNATURE: base64(rsa_pss_sign(private_key, timestamp + method + path + body))
```

The passphrase (`KALSHI_PASSPHRASE`) is used to decrypt the RSA key from
disk before signing. Never log any of these three values.

## Order placement (V2)

```http
POST /v2/portfolio/orders
{
  "ticker": "<example-market-id>",
  "action": "buy",
  "side": "yes",
  "count": 42,
  "type": "limit",
  "yes_price": <int-cents>,
  "expiration_ts": <unix>,
  "sell_position_floor": 0
}
```

`yes_price` and `no_price` are integer cents (1-99 inclusive).

## Cancel

| Verb | Path | Effect |
| --- | --- | --- |
| DELETE | `/v2/portfolio/orders/{order_id}` | cancel a single open order |
| DELETE | `/v2/portfolio/orders` (batch) | cancel up to 50 by id |

A single-cancel can fail with 409 if the order has already filled.
Treat 409 as success-by-time-of-attempt.

## Settlement reads

```
GET /v2/portfolio/positions?limit=200&settlement_status=settled
GET /v2/portfolio/settlements?limit=200
```

Use `position_events.csv` to absorb overnight settlement debits/credits.
The rebalance script reconciles on these two endpoints daily.

## Sandbox vs prod

The Kalshi demo env is `https://demo-api.kalshi.co`. For any new feature,
ship to demo first; only flip to prod after 1 cleared rebalance cycle on
demo.

## Idempotency

Re-running a rebalance at the same minute must be a no-op. Tag orders
with `client_order_id = "<index>-YYYYMMDDHHMM-<market_or_side>"` so
duplicates collapse at the API.
