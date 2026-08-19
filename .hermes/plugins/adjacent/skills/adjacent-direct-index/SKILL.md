---
name: adjacent-direct-index
description: Use when replicating an Adjacent index on a connected exchange, computing constituent weights, or running a weekday rebalance.
version: 1.1.0
category: software-development
allowed-tools:
  - adjacent-markets/list
  - adjacent-markets/get
  - adjacent-markets/find
  - adjacent-markets/price
  - adjacent-markets-dev/list
  - adjacent-markets-dev/get
  - adjacent-markets-dev/find
  - adjacent-markets-dev/price
  - Bash
---

# Adjacent direct index

How to replicate any Adjacent index by buying its constituent markets on
a connected exchange. Today only the Kalshi V2 adapter ships; the
rebalance-index script has a dispatcher (`EXCHANGES[--exchange]`) and
additional adapters (Polymarket CLOB, Manifold AMM, Hyperliquid, etc.)
plug in without rewriting this skill.

## Convention

Tracking uses mid-quote pricing end-to-end. Tracking_error =
`(mid_portfolio_return - mid_index_return)` expressed in `%`.

## Live pricing fallback

Adjacent MCP is always the primary source. If a market `price` call fails,
the agent may request an explicit read-only venue fallback through
`mcp-cli.py price ... --fallback-venue <venue>`. The market id must carry the
venue prefix (`kalshi:<ticker>` or `polymarket:<token_id>`). The fallback
returns bid, ask, and mid and must be labeled with `venue` and
`basis: mid-quote`.

- Kalshi uses the public V2 orderbook and derives the YES ask from the best
  NO bid, or vice versa.
- Polymarket uses the public CLOB orderbook and takes the best bid and ask.
- A fallback is valid for a current quote only. Do not substitute it for
  Adjacent historical index series.
- If either side is missing, fail closed and stop the buy queue.
- Never use last trade as a fallback for tracking, sizing, or P&L.

## Files of record

- `<data-dir>/adjacent_direct_indices.json`: **trading
  catalog**. Drives `scripts/rebalance-index.py` and any plan built
  for live order placement. Fail-closed on `_placeholders.value:
  true`. The plugin does NOT ship with seeded Adjacent slugs; the
  user fills this catalog with slugs they want to trade on.
- Adjacent slug discovery for briefs / charts / Q&A lives entirely
  in the live MCP. The agents call
  `mcp__adjacent_markets_dev__list(type=index)` (and `find`,
  `get`, `price`) at runtime; nothing is cached as a fixture.
- `<data-dir>/positions/<index>.json`: live state per index
  (production by `scripts/portfolio-snapshot.py`).
- `<data-dir>/tracking/<index>.json`: per-row tracking table
  (production by `scripts/tracking-index.py`).

## Index catalog schema

```json
{
  "indices": {
    "<slug>": {
      "category": "<theme>",
      "budget_usd": <number>,
      "rebalance_cron_local_hour_et": 16,
      "rebalance_days": ["mon", "tue", "wed", "thu", "fri"],
      "exchange": "kalshi",
      "constituents": [
        {
          "market_id": "kalshi:<ticker>",
          "platform": "kalshi",
          "side": "yes",
          "target_weight": 0.142
        }
      ]
    }
  }
}
```

## Rebalance algorithm

Weekdays 16:00 ET.

1. Pull constituents + weights via `list` on the target index.
2. For each constituent, call `price(market_id, "1d")` to refresh mid.
3. `current_weight = position_notional_mid / total_portfolio_nav`.
4. `drift = (current_weight - target_weight) / target_weight`.
5. Sell queue: drift >= +1% OR name flagged in `index.removals` for
   today.
6. Buy queue: positive target_weight AND drift <= -1%, sorted by
   target_weight descending.
7. Execute via the per-exchange adapter with target
   `target_weight * NAV` notional.
8. Settle-fill reconcile vs pending; emit tracking table to JSON.

## Tracking components (report every rebalance)

| Component | Definition |
| --- | --- |
| drift | weight change since last rebalance |
| selection | alpha of chosen constituents |
| fee_impact | realized fees / spend |
| fill_queue | slippage mid-vs-fill weighted |

Sum them. Each in `%`.

## Sizing

Use mid-based notional. Round the buy/sell to integer contract count.
Reject dust orders (less than $5 notional) and accumulate into the
next-week rebalance.

## Failure modes

- If a constituent has zero 24h volume, skip it but log as `--` in the
  table.
- If `price` returns no data, mark `stale` and exclude from the buy
  queue but keep it in the portfolio.
- If the exchange API key is unset, refuse to place orders and print
  one line: `error: <EXCHANGE>_API_KEY unset`.
- If the catalog `_schema._placeholders.value` is not `false`, refuse
  to place orders and print the fail-closed message from
  `rebalance-index.py`.
