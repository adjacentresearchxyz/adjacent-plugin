---
description: Run the Adjacent daily loop - movers scan, live news correlation, branded charts, and the brief. Fail-closed on trading.
argument-hint: "[<slug1>,<slug2>,...] [--charts] [--rebalance] [--prod] [--quiet]"
---

# Daily workflow

Load the `adjacent-workflows` skill, then run the daily loop end to end.
This command orchestrates the existing pieces.

## Arguments

| Flag | Effect |
| --- | --- |
| `<slugs>` | comma-separated watchlist override; empty uses `data/watchlist.json`, and if that is empty a live `list(type=index)` |
| `--charts` | render a branded tracking chart per mover (default off; text only) |
| `--rebalance` | after the brief, propose `/trading-rebalance-index --dry-run` per eligible index; never places orders |
| `--prod` | use `adjacent-markets` (requires `ADJACENT_API_KEY`); default is dev |
| `--quiet` | short-circuit to the brief header + `briefing-too-quiet` when nothing clears threshold |

## Workflow

1. Resolve the watchlist: `$ARGUMENTS` slugs, else `data/watchlist.json`,
   else a live `adjacent-markets-dev/list(type=index)`.
2. Movers scan: delegate to the `index-monitor` droid (thresholds from
   `adjacent-index-movers`). Default MCP is dev unless `--prod`.
3. News correlation: pull the live `news/latest` surface with
   `scripts/news-latest.py --normalize` (or use supplied local article
   JSON), then rank headlines against mid moves with
   `scripts/news-correlation.py`.
4. Charts (only with `--charts`): for each hit, build the tracking CSV
   with `scripts/chart-index.py` and render an Adjacent-branded PNG using
   `scripts/adjacent_chart_style.py` (see the `adjacent-chart-style`
   skill). Prefer Datawrapper when `DATAWRAPPER_API_KEY` is set.
5. Brief: delegate to the `briefing-writer` droid to format per the
   `briefings` skill. Print to stdout only.
6. Rebalance (only with `--rebalance`): for each index whose catalog
   record has `_schema._placeholders.value: false`, run
   `/trading-rebalance-index --index <slug> --dry-run` and print the
   plan. Stop and wait for explicit confirmation before any live order.

## Output shape

```
YYYY-MM-DD HH:MM ET adjacent
- <slug>: 1d <move>%, 7d <move>% <one-line reason> [chart: <path|url>]
...
brief:
<briefing-writer output>
```

If fewer than 3 movers clear threshold, emit `briefing-too-quiet` after
the header (same as `--quiet`). Never place an order in this command;
`--rebalance` stops at the dry-run plan.
