---
name: brief-daily
description: Run the Adjacent daily brief - movers scan, thresholds, and formatted brief text. Routes through scripts/brief-daily.py.
allowed-tools:
  - Bash
  - Read
argument-hint: "[<slug1>,<slug2>,...] [--with-news] [--limit N] [--prod] [--output path]"
---

# Daily brief

Run the end-to-end daily brief via `scripts/brief-daily.py`.

## Arguments

| Flag | Effect |
| --- | --- |
| `<slugs>` | comma-separated index slugs; empty uses the watchlist or a live list |
| `--with-news` | attach live news headlines to flagged movers |
| `--limit N` | max slugs when discovering live (default 10) |
| `--prod` | use the realtime tier (needs ADJACENT_API_KEY) |
| `--output path` | also write the JSON result to this path |

## Workflow

1. Resolve the watchlist: `$ARGUMENTS` slugs, else
   `data/watchlist.json`, else a live `list(type=index)`.
2. Fetch mid-quote moves for each slug (1D, 7D, 30D).
3. Apply thresholds from the `adjacent-index-movers` skill.
4. When `--with-news`, pull the live news/latest surface and attach
   headlines to flagged movers.
5. Format the brief per the `briefings` skill.

Mid-quote pricing throughout. No em-dash, no emoji, `%` never `pp`.
