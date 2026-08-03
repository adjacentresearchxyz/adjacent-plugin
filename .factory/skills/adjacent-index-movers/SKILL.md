---
name: adjacent-index-movers
description: Adjacent index move thresholds with explicit formulas and a clean alerting policy. Drives the /data/index-movers scan and the movers log.
version: 1.2.0
category: research
allowed-tools:
  - adjacent-markets/price
  - adjacent-markets/get
  - adjacent-markets-dev/price
  - adjacent-markets-dev/get
---

# Adjacent index movers

Every Adjacent index reports a `price(id, type="index", timeframe="24h")`
and a `price(id, type="index", timeframe="7d")`. This skill codifies how
to act on those numbers.

## Formulas

For an index returning mid_open, mid_close, high, low:

- `move_1d = (mid_close - mid_open) / mid_open`
- `move_7d = (mid_close_day7 - mid_close_day0) / mid_close_day0`
- `move_30d = same shape, monthly horizon`

## Thresholds

| Horizon | Threshold | Action |
| --- | --- | --- |
| 1D | `|move_1d| >= 1.5%` | `/data/index-movers` print + movers log |
| 7D | `|move_7d| >= 4%` | `/data/index-movers` print + movers log |
| 30D | `|move_30d| >= 8%` | `/briefing/morning` highlight only |

## Sign-flips

`convention-break` = sign of `move_1d` differs from sign of `move_7d`.
When this fires, the move is unusual. Print `convention-break: yes` in
the alert. Add a news explanation from the live `news/latest` surface
(or supplied article JSON) when a headline explains the move; see the
`adjacent-news-correlation` skill.

## Smoothing

For any user-facing summary, do not raw-print `move_1d`. Quote the
SMA-7 alongside; smoothed values are easier to read than a single
noisy day. The Adjacent MCP `price(raw: true)` returns the underlying
daily series; compute SMA yourself.

## What does NOT fire the alert

- Same-magnitude drift that is the index mean-reverting - count
  sign-flips, not raw direction, to avoid alerting on noise.
- 1D moves less than 1.5%.
- Indices with less than $500 of 24h notional volume (illiquid; do not
  report).

## Composition rules

When you add a new index to the watchlist:

1. Add the slug to `<data-dir>/watchlist.json`.
2. Update `AGENTS.md` index-mover thresholds only if the new index
   needs a different threshold (rare; default to the table above).
3. After 1 week of live data, evaluate any spurious alerts and tune.
