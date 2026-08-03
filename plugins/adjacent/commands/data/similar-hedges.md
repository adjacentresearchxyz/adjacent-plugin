---
name: similar-hedges
description: Rank similar markets into hedges (negative correlation) and proxies (positive).
allowed-tools:
  - Bash
  - Read
argument-hint: "--input <similar.json> [--min-abs-correlation 0.3]"
---

# Similar hedges

The `markets/{id}/similar` surface is live. For each related market,
attach a signed mid-return correlation to the target, save the rows as
JSON, then rank them:

```bash
python3 scripts/similar-hedges.py $ARGUMENTS
```

Input rows are `{market_id, correlation}` with correlation in `-1..1`.
Hedges are negatively correlated (move opposite the target); proxies are
positively correlated. Correlations are mid-based; never use last trade.
