---
name: index-movers
description: Scan a watchlist of Adjacent index slugs and report the largest movers on 1D and 7D horizons.
allowed-tools:
  - adjacent-markets/list
  - adjacent-markets/find
  - adjacent-markets/get
  - adjacent-markets/price
  - adjacent-markets-dev/list
  - adjacent-markets-dev/find
  - adjacent-markets-dev/get
  - adjacent-markets-dev/price
argument-hint: "[<slug1>,<slug2>,...] or empty for default watchlist"
---

# Index movers

Produce a movers scan. Use `adjacent-markets-dev` by default; if
`ADJACENT_API_KEY` is set, prefer `adjacent-markets`.

If $ARGUMENTS is empty:

- Read the default watchlist from `<data-dir>/watchlist.json`.

If $ARGUMENTS is non-empty:

- Treat it as a comma-separated list of Adjacent slugs. Validate each with
  `find(slug, "index")`; warn on misses but continue.

For each slug call:
- `price(id=slug, type="index", timeframe="24h")` -> `move_1d`
- `price(id=slug, type="index", timeframe="7d")`  -> `move_7d`
- `price(id=slug, type="index", timeframe="30d")` -> `move_30d` (only if move_7d >= 2%)

Apply the thresholds from the `adjacent-index-movers` skill:
- 1D spontaneous alert: `|move_1d| >= 1.5%`
- 7D weekly alert:    `|move_7d| >= 4%`

Output, sorted by `|move_1d|` descending, with the convention-only surprises
(i.e. names whose 1D sign differs from 7D sign) flagged.

Format rules from `briefings` skill. No emojis. No em-dash. "% not pp".
Mid-quote pricing throughout. If a slug has no live data, mark it `--` and
accumulate in a "skipped" line at the bottom of the report.
