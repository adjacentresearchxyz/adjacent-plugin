---
name: adjacent-markets
description: Adjacent index monitoring - mid-quote pricing convention, SMA smoothing, dev vs prod MCP hygiene, and SPX cross-reference conventions.
version: 1.1.0
category: research
allowed-tools:
  - adjacent-markets/list
  - adjacent-markets/find
  - adjacent-markets/get
  - adjacent-markets/price
  - adjacent-markets-dev/list
  - adjacent-markets-dev/find
  - adjacent-markets-dev/get
  - adjacent-markets-dev/price
  - Bash
---

# Adjacent markets

The research-side conventions for monitoring Adjacent indices. This
skill collects the three findings that take the longest to discover
into one place.

## 1. Mid-quote pricing (the most-confirmed finding)

Always track at mid. Ask or bid makes tracking error look worse than it
is. The `price` MCP returns `bid`, `ask`, `mid`. Use `mid` for every
return, move, and tracking computation.

Bad: `move = (close_ask - open_ask) / open_ask`
Good: `move = (close_mid - open_mid) / open_mid`

## 2. SMA smoothing for stability

Wherever you compute a "level" for an index over time, prefer SMA-7
over the raw close. Daily raw prints include a lot of single-day noise
that fights the eye. SMA-7 still moves the same day-over-day but
smooths the chart. The Adjacent MCP `price(raw: true)` returns the
underlying daily series; compute SMA yourself.

## 3. Dev MCP for new workflows

When you prototype a workflow, use `adjacent-markets-dev`. Promote to
prod (`adjacent-markets`) only when:

- the workflow needs realtime quality (sub-minute latency)
- the workflow publishes to charts (no tolerance for staleness)
- the workflow is being demoed to a paying user

Default everything else to dev.

## Move thresholds

See the `adjacent-rate-movers` skill for the canonical formulas and
threshold table.

## News correlation

For each 1D or 7D move above threshold, call on
`adjacent-news-correlation` for the source match. The whitelist lives in
`<plugin-root>/data/watchlist.json` (shipped empty by design - the
plugin does not bake in any specific Adjacent index). Slugs come
from a live `adjacent-markets-dev/list(type=index)` call.

## SPX cross-reference

Cross-reference vs SPX for context. Use 1D correlation by default.
Flag any index whose weekly correlation with SPX exceeds 0.6 unless
the move is event-driven (politics, election, Fed rate decision) -
those are inherently SPX-resistant.
