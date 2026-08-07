---
description: Per-position mid-based tracking table for an index - size, mid, cost basis, notional, weight, return. Routes through scripts/tracking-index.py.
argument-hint: "--index <slug> [--json]"
---

# Tracking

Produce a per-position mid-based table via
`scripts/tracking-index.py`.

## Arguments

| Flag | Effect |
| --- | --- |
| `--index <slug>` | index slug (required) |
| `--json` | structured output for downstream consumers |

## Workflow

1. Read the position document from
   `data/positions/<slug>.json`.
2. For each position, fetch the current mid quote.
3. Compute: size, mid, cost basis, notional, %-weight, return against
   cost basis.
4. Format per the `briefings` skill.

Mid-quote pricing throughout. No em-dash, no emoji, `%` never `pp`.
