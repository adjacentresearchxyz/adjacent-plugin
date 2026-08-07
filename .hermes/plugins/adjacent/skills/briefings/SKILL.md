---
name: briefings
description: Morning briefing format rules - ASCII bullets, percent not percentage points, no em-dash, no emoji, mid-quote pricing.
version: 1.1.0
category: productivity
---

# Briefings

The format rules for every Adjacent briefing, alert, and published
output. The `conventions` hook enforces these.

## Hard rules

1. Bullets. Use ASCII `-`, never the unicode bullet glyph (codepoint
   U+2022).
2. Percent sign `%` always; `pp` (percentage points) is banned.
3. No em-dashes anywhere. Use `-` or `:` or rephrase.
4. No emojis in body, tables, chart titles, logs.
5. ASCII `-` inside numeric ranges like `4-7%` is fine.
6. Currency: `$100` not `100 USD`. Decimals: `0.012` not `.012`.
   Date: `YYYY-MM-DD`.

## Mid-quote pricing (the most violated rule)

All prices reported as `current`, `open`, `close`, `moving`, or
`tracking` are mid-quote. The `price` MCP returns `bid`, `ask`, `mid`.
Anywhere the model would say `bid` or `ask`, use `mid` instead, unless
deliberately reporting a spread.

## Tracking = mid vs mid in %

- tracking_error = mid_based_portfolio_return - mid_based_index_return
- reported as `%` (e.g. `-0.42%`), never `pp`
- rebuild the `tracking-index` script output only for new rebalances
  (do not recompute without a fresh plan)

## Output shapes

For a morning briefing, match the `/briefing/morning` command template:

```
YYYY-MM-DD HH:MM ET briefing
- <bullets, one idea each, mid-quoted>
```

For a rebalance report, match the `/trading/rebalance-index` template:

```
YYYY-MM-DD HH:MM ET rebalance
- sell: <market_id> size=<n> mid=<m>
- buy:  <market_id> size=<n> mid=<m>
- residual drift: <drift>%
```

For an index-mover alert, match `/data/index-movers`:

```
YYYY-MM-DD HH:MM ET movers
- <slug>: 1d <move>%, 7d <move>%, convention-break: yes|no
```

For a topic update, match `/data/topic-brief` and the
`adjacent-topic-brief` skill:

```
YYYY-MM-DD HH:MM ET topic brief: <topic>

News
- <headline> (<source>, <YYYY-MM-DD>)

Take
- <1-3 sentences grounded in mids>

Markets (mid)
- <name>: <mid%>  id=<platform:raw>

charts
- <csv or png path>
```
