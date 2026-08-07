---
description: Build a per-index 24h return chart CSV (index vs portfolio, rebased to 100). Routes through scripts/chart-index.py.
argument-hint: "--index <slug> [--output path]"
---

# Chart CSV

Build a per-index return chart CSV via `scripts/chart-index.py`.

## Arguments

| Flag | Effect |
| --- | --- |
| `--index <slug>` | index slug (required) |
| `--output path` | write the CSV to this path |

Both the index series and the portfolio series are rebased to 100 at the
last fill. Pipe the CSV into `/charts-datawrapper-publish` for an
Adjacent-branded chart. For live candle charts use the chart-build
script directly.
