---
name: adjacent-data-surfaces
description: Use when the task needs docs, similar markets, candles, public snapshots, exports, news/latest, or capability status before calling a surface.
version: 2.0.0
category: research
---

# Adjacent data surfaces

Check `data/capabilities.json` before using a surface. Each recipe below
maps a live surface to the local script that turns its response into a
mid-based, Adjacent-branded artifact.

## Live surfaces

- `news/latest`: pull the latest news with `scripts/news-latest.py`.
  Add `--normalize` to emit `{market_id, published_at, headline}` rows,
  then rank them with `scripts/news-correlation.py` (see the
  `adjacent-news-correlation` skill). For a full topic update (news +
  markets + mids + charts), use `scripts/topic-brief.py` and the
  `adjacent-topic-brief` skill.
- `markets/{id}/candles`: fetch candles, then build a mid-based
  `ts,close` chart CSV with `scripts/candles-chart.py`. Add `--rebase`
  to index closes to 100 at the first candle. Never substitute last
  trade for mid.
- `markets/{id}/similar`: attach a signed mid correlation to each
  related market and rank them into hedges (negative) and proxies
  (positive) with `scripts/similar-hedges.py`.
- `/public/*`: grade snapshot freshness with
  `scripts/snapshot-health.py`. Zero-key; pass `--live` to fetch each
  descriptor `url` before grading.
- `/export/*`: fetch CSV / pandas / Polars exports with
  `scripts/http-get.py --url <export-url>`. See the export cookbook
  below.
- `/docs.zip`: retrieve builder answers from the published documentation
  instead of inventing API behavior. See the docs Q&A recipe below.

## Export cookbook

Use `scripts/http-get.py` (HTTPS Adjacent hosts only). Common exports:

- Markets, events, and indices catalogs for offline joins.
- Price history for a slug to back a candles chart or SMA.
- Trades for fill-quality and fee analysis.

```
python3 scripts/http-get.py --url https://<host>/export/<path> --output out.csv
```

Prefer exports over scraping list responses when you need a full,
stable table. Load the CSV with pandas or Polars downstream.

## Docs Q&A

To answer a builder question from ground truth rather than memory:

1. `python3 scripts/http-get.py --url https://<host>/docs.zip --output docs.zip`
2. Unzip and grep the Markdown for the relevant surface.
3. Quote the doc text; do not invent endpoint behavior.

## Unavailable surfaces

- `indices/{id}/correlation`: not live. Regime analysis runs offline
  only, on supplied observations, via `scripts/correlation-regime.py`.

Do not call an unavailable endpoint. The correlation workflow must emit
an unavailable message when no local input is provided.
