---
description: Fetch the live Adjacent news/latest surface, optionally shaped for correlation.
argument-hint: "[--normalize]"
---

# News latest

The `news/latest` surface is live. Fetch it:

```bash
python3 scripts/news-latest.py $ARGUMENTS
```

Add `--normalize` to emit `{market_id, published_at, headline}` rows
ready for `/data-news-correlation`. Without a key the public
15-min-delayed tier is used; set `ADJACENT_API_KEY` for realtime.
