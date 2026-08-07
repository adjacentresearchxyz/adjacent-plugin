---
name: market-snapshot
description: Build a normalized tradable market snapshot from a topic, index, or ids. Every row has mid, bid, ask, spread, volume, and 1D move. Routes through scripts/market-snapshot.py.
allowed-tools:
  - Bash
  - Read
argument-hint: "--query <topic> | --index <slug> | --ids <id1,id2> [--limit N] [--timeframe 24h] [--quotes] [--csv path] [--prod]"
---

# Market snapshot

Build a normalized snapshot via `scripts/market-snapshot.py`.

## Arguments

| Flag | Effect |
| --- | --- |
| `--query <topic>` | free-text topic to resolve into markets |
| `--index <slug>` | snapshot an index's constituents |
| `--ids <id1,id2>` | comma-separated ids in platform:raw form |
| `--limit N` | max rows (default 25) |
| `--timeframe` | quote timeframe (default 24h) |
| `--quotes` | fetch the bid/ask quote leg per row |
| `--csv path` | also write the rows to a CSV |
| `--prod` | use the realtime tier |

Pass exactly one of `--query`, `--index`, or `--ids`.

Every row carries: market id, name, mid, bid, ask, spread, 24h volume,
1D move in `%`. Mid-quote pricing throughout.
