# Adjacent prediction-market plugin

Claude Code plugin for the
[Adjacent prediction-market MCP](https://docs.adjacent.markets/explore/mcp).

## Features

1. **Daily briefs**: `/briefing/morning` produces a one-line + 1-bullet
   per-idea report from the index-movers scan.
2. **Free-form Q&A**: `/data/ask <question>` routes any topic through
   the Adjacent MCP.
3. **Easy charting**: `/charts/datawrapper-publish` turns any CSV into
   a Datawrapper chart with emphasized % formatting.
4. **Index-mover scans**: `/data/index-movers` flags 1D / 7D / 30D
   moves on a configurable watchlist (1.5% / 4% / 8% thresholds).
5. **Direct indexing**: `/trading/rebalance-index` proposes or places
   exchange orders, fail-closed by default.

## Install

```
/plugin marketplace add adjacentresearchxyz/adjacent-plugin
/plugin install adjacent@adjacent-plugin
```

Prefix every command with `adjacent:` (e.g. `/adjacent:briefing/morning`).

## Configuration

- Adjacent realtime: `ADJACENT_API_KEY`. Skip it for the 15-min
  delayed tier (briefs and scans still work).
- Kalshi direct indexing: `KALSHI_API_KEY`, `KALSHI_PASSPHRASE`,
  `KALSHI_RSA_KEY_PATH` (RSA-PSS).
- Datawrapper charting: `DATAWRAPPER_API_KEY`.
