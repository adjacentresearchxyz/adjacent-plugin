---
name: kalshi-direct-indexing
description: Allocation math, tracking error formulas, Kalshi balance quirks, fee accounting for direct-index replication on Kalshi.
version: 1.0.0
category: productivity
allowed-tools:
  - Bash
---

# Kalshi direct indexing

Everything you need to compute allocations, tracking error, account
balances, fees, and fill accounting on the Kalshi V2 API for direct
indices tracked via the Adjacent MCP.

## Notional -> contracts

For a market with mid `m` and target notional `n`:

- `n_dollars = n`
- `contracts = floor(n_dollars / m)`   // 1 contract = $1 settlement
- `dust = n_dollars - contracts * m`   // accumulate across week

Reject dust if it would create a fractional contract.

## Balance quirks

- Kalshi NAV = settled cash + unrealized P&L + reserves for live orders.
- Settlements debit/credit at `close()`, NOT at `fill()`.
- A rebalance placed at 16:00 ET will settle over the next 1-3 days.
- The rebalance script reconciles NAV on `settled` vs `pending`.
- Buy queue must respect `unsettled_count + buy_count <= 1000`
  (per-account constraint; do not exceed without splitting batches).

## Tracking error formulas

| Component | Formula |
| --- | --- |
| drift | `\|current_weight - target_weight\| / target_weight` |
| selection | `weighted_avg(constituent_alpha) / index_alpha` |
| fee_impact | `sum(fees) / total_notional` |
| fill_queue | `sum(\|mid - fill\|) / total_notional` |
| residual | `sum_of_above` |

All in `%`. All at mid. All expressed mid-based.

## Fee accounting

Fees = per-contract fee * contracts * (1 + fee_multiplier). Log them
per-fill. Roll up daily at 00:00 UTC.

Fees:
- 0.1% of notional on settlement of a yes contract you bought at >50%.
- The fee on `close` order `cross_side`.

Verify fees by reading `position_events.csv` daily.

## Compact delivery format

For each rebalance, the script emits a `.compact.json` containing:

```json
{
  "index": "<slug>",
  "ts": "YYYY-MM-DDTHH:MM:SSZ",
  "sells": [{"market_id":"...", "size": <n>, "mid": <m>}, ...],
  "buys":  [{"market_id":"...", "size": <n>, "mid": <m>}, ...],
  "drift_residual_pct": <d>,
  "fees_pct": <f>,
  "fill_queue_pct": <g>
}
```

## Reporting

Always precede the report with a `%` column rule. Bad: `pp`. Good: `%`.
The `conventions` hook audits this output.
