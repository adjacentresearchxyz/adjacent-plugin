---
description: Fetch an Adjacent CSV / data export for offline pandas or Polars analysis.
argument-hint: "--url https://<host>/export/<path> [--output out.csv]"
---

# Export

The `/export/*` surfaces are live. Fetch one (HTTPS Adjacent hosts only):

```bash
python3 scripts/http-get.py $ARGUMENTS
```

Cookbook:

- Markets, events, and indices catalogs for offline joins.
- Price history for a slug to back a candles chart or SMA.
- Trades for fill-quality and fee analysis.

Prefer exports over scraping list responses when you need a full, stable
table. Load the CSV with pandas or Polars downstream. See the
`adjacent-data-surfaces` skill for the full cookbook.
