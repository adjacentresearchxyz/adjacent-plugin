---
name: rebalance-index
description: Direct-index rebalance for any Adjacent index. Reads the catalog, computes drift via MCP, posts orders to the configured exchange, or prints the plan with --dry-run.
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
argument-hint: "--index <slug> [--exchange kalshi] [--dry-run | --json] [--allow-weekend]"
---

# Rebalance index

Run the direct-index rebalance for any Adjacent index. Loads the
`adjacent-direct-index` skill plus the per-exchange skill
(`kalshi-direct-indexing` + `kalshi-api` today) first.

## Arguments

| Flag | Effect |
| --- | --- |
| `--index <slug>` | required; catalog key in `data/adjacent_direct_indices.json` |
| `--exchange <name>` | optional; defaults to catalog `exchange` field, then `kalshi` |
| `--dry-run` | compute plan, print, do not place orders; bypasses weekend gate |
| `--json` | compute plan, emit JSON to stdout, do not place; bypasses weekend gate |
| `--allow-weekend` | bypass the weekday-only default when actually placing orders |

## Workflow

1. Read `<data-dir>/adjacent_direct_indices.json`. Refuse to
   run if `_schema._placeholders.value` is not `false` (the
   `scripts/rebalance-index.py` fail-closed guard does this).
2. Refuse to run on weekends (Saturday or Sunday UTC at placement time)
   unless `--allow-weekend` is set. `--dry-run` and `--json` skip this
   gate so users can preview weekend plans.
3. Call `list` on the target index for live constituents + weights.
4. For each constituent, call `price(market_id, "1d")` with
   `raw: false` for a compact summary.
5. Compute `drift = (current_weight - target_weight) / target_weight`.
6. Sell queue: drift >= +1% (over-allocated), or names flagged for
   removal in the catalog.
7. Buy queue: positive target_weight and currently under-allocated or
   new, sorted by target_weight descending.
8. For `--dry-run` / `--json`: stop here and print the plan.
9. Else: pipe the plan into `scripts/rebalance-index.py --index <slug>
   --exchange <name>`.
10. After fills: run `scripts/tracking-index.py --index <slug> --json`,
    then `/charts/datawrapper-publish <chart-id> --csv /dev/stdin` on
    the rebuilt tracking table.

Use `adjacent-markets-dev` when `ADJACENT_API_KEY` is unset; otherwise
prod (`adjacent-markets`). The `secret-redactor` hook strips any
`ADJACENT_API_KEY` or `KALSHI_*` value from Bash output before the
host persists the trajectory log.
