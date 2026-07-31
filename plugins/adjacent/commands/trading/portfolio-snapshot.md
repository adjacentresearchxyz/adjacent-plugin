---
name: portfolio-snapshot
description: Portfolio snapshot - position count, exposure, per-position P&L when requested. Routes through scripts/portfolio-snapshot.py.
allowed-tools:
  - Bash
  - adjacent-markets/get
  - adjacent-markets/price
argument-hint: "[--index <slug>] [--include-pnl] [--json]"
---

# Portfolio snapshot

Read the cached position document(s) and emit a status report via
`scripts/portfolio-snapshot.py`.

## Arguments

| Flag | Effect |
| --- | --- |
| empty | report every index document in `data/positions/*.json` |
| `--index <slug>` | restrict to one slug |
| `--include-pnl` | mid-based today's P&L per position |
| `--json` | structured output for downstream consumers (charting, briefs) |

## Workflow

1. Read position documents from
   `<plugin-data-dir>/data/positions/*.json` (filtered by `--index`).
2. For each position, when `--include-pnl` is set, call
   `price(market_id, "1d")` and compute today's mid-based move on the
   position size.
3. Aggregate: today's P&L (mid), total exposure, drift per index.
4. Format per the `briefings` skill:
   - 1 line per position
   - `-` (ASCII hyphen-minus) bullets, never the unicode bullet codepoint
     U+2022
   - no em-dashes, no emojis
   - mid-quote pricing
5. Always include a `last-sync` line showing the most recent
   `portfolio-snapshot.py` file modification time.
