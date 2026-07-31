---
name: adjacent-news-correlation
description: Joins Adjacent news articles to market / index moves on minute-precision timestamps.
version: 1.1.0
category: research
allowed-tools:
  - adjacent-markets/list
  - adjacent-markets/find
  - adjacent-markets/get
  - adjacent-markets/price
---

# Adjacent news correlation

Join news cause to market effect. The `adjacent-markets` skill feeds
you moved indices; this skill feeds you the news that likely caused
them.

## Source policy

Whitelist of reputable financial news sources. The exact list is
configurable per deployment; defaults are stored under
`<plugin-root>/data/watchlist.json` in `sources_for_news_correlation`.
The defaults cover top-tier business outlets, top wire services, and
a small set of policy-focused outlets.

Treat any source outside the whitelist as ambiguous. Do not correlate
on social-media or aggregator pages alone.

## Workflow

1. Get a list of 1D and 7D movers from `adjacent-rate-movers`.
2. For each mover, call `find(topic=event-slug, "news")` filtered to the
   past 24h (1D alerts) or 7d (7D alerts) window.
3. For each returned news article, check whether the publication
   timestamp is within +/- 30 minutes of the move timestamp.
4. If yes: attach a `(news -> slug, move%)` row to the alert.
5. If no: emit `unaccounted-move: <slug>, <move%>` for the briefing.

## Time alignment

Adjacent markets quotes update at :00 of each minute. News timestamps
are usually `HH:MM:SS`. Round news times down to the minute and align
against the most recent index tick before the news publication.

## What this skill does NOT do

- It does not generate news copy. The `briefings` skill handles that.
- It does not publish to any third-party service.
- It does not place orders. The direct-index rebalancer owns that side.

## Output

```
YYYY-MM-DD HH:MM ET news correlation
- <slug>: <move>% whitelisted -> <headline-truncated-50>
- <slug>: <move>% unaccounted-move
```
