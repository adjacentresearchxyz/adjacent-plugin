---
name: candles-chart
description: Build a mid-based ts,close chart CSV from Adjacent market candles.
allowed-tools:
  - Bash
  - Read
argument-hint: "--input <candles.json> [--output out.csv] [--rebase]"
---

# Candles chart

The `markets/{id}/candles` surface is live. Save its response to a JSON
file, then build the chart CSV:

```bash
python3 scripts/candles-chart.py $ARGUMENTS
```

Each candle contributes a mid-based close (explicit `mid`, else
`(bid + ask) / 2`, else a mid-derived `close`). Add `--rebase` to index
closes to 100 at the first candle. Pipe the CSV into
`/charts/datawrapper-publish` for an Adjacent-branded chart.
