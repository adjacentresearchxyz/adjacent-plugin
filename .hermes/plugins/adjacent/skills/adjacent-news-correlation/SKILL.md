---
name: adjacent-news-correlation
description: News-to-mid correlation from the live news/latest surface or supplied JSON.
version: 1.2.0
category: research
allowed-tools:
  - adjacent-markets/list
  - adjacent-markets/find
  - adjacent-markets/get
  - adjacent-markets/price
---

# Adjacent news correlation

The `news/latest` endpoint is live. Pull it with
`scripts/news-latest.py --normalize` (or the `list(type=news)` MCP
tool), or supply article JSON from another trusted local process. This
skill ranks articles against minute-aligned mid-price observations.

## Source policy

Whitelist of reputable financial news sources. The exact list is
configurable per deployment; defaults are stored under
`<data-dir>/watchlist.json` in `sources_for_news_correlation`.
The defaults cover top-tier business outlets, top wire services, and
a small set of policy-focused outlets.

Treat any source outside the whitelist as ambiguous. Do not correlate
on social-media or aggregator pages alone.

## Workflow

1. Get article JSON: `scripts/news-latest.py --normalize` for the live
   feed, or a supplied local file. Get mid-price JSON from
   `price(raw: true)` snapshots.
2. Run `scripts/news-correlation.py`.
3. Align timestamps at the minute.
4. Rank results by absolute mid move.
5. Filter articles to whitelisted sources before correlating.

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
