---
description: Rank live or supplied news events by minute-aligned mid moves.
argument-hint: "--news <articles.json> --prices <mid-prices.json> [--window-minutes 30]"
---

# News correlation

The `news/latest` endpoint is live. Pull it into an articles file:

```bash
python3 scripts/news-latest.py --normalize > articles.json
```

Then rank against mid prices (supplied articles JSON also works):

```bash
python3 scripts/news-correlation.py $ARGUMENTS
```

Prices must contain `market_id`, `ts`, and `mid`. Articles must contain
`market_id`, `published_at`, and `headline`. Filter to whitelisted
sources (see the `adjacent-news-correlation` skill) before correlating.
