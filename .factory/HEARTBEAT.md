# HEARTBEAT - Adjacent cadence

Suggested schedule for a host loop or cron. Times are America/New_York
(ET). Nothing here publishes or places orders on its own.

## Schedule

| When (ET) | Action | Command |
| --- | --- | --- |
| 08:00 weekdays | Morning brief | `/daily --charts` |
| Hourly 09:00-16:00 weekdays | Movers scan, append to mover log | `/data-index-movers` |
| 16:00 weekdays | Rebalance dry-run per eligible index | `/daily --rebalance` |
| 17:00 weekdays | End-of-day brief | `/briefing-morning` |
| 09:00 Saturday | Weekly recap (optional) | `/daily` |

## Rules

- Weekend gate: the rebalance step never places orders on Saturday or
  Sunday unless `--allow-weekend` is set. Dry-runs are always allowed.
- Tier: dev MCP by default. The host promotes to prod by setting
  `ADJACENT_API_KEY` and passing `--prod`.
- Quiet days: if a scan clears fewer than 3 movers above threshold, the
  brief step emits `briefing-too-quiet` and produces no bullets.
- Idempotency: re-running a slot is safe. The mover log appends; the
  brief prints; charts overwrite by index slug.

## Watchlist

The shipped `data/watchlist.json` is empty by design - the plugin bakes
in no Adjacent slugs. Resolve an empty watchlist with a live
`adjacent-markets-dev/list(type=index)`, or pass an explicit slug list.
Edit `data/watchlist.json` to pin a set.

## Environment

- `ADJACENT_API_KEY` - realtime tier and prod MCP. Optional; dev works
  without it.
- `ADJACENT_STATE_DIR` - base dir for `logs/` and `charts/`. Defaults
  to the current directory.
- `DATAWRAPPER_API_KEY` - publish charts to Datawrapper. Without it,
  render the Adjacent-branded Seaborn fallback locally.
- `KALSHI_API_KEY`, `KALSHI_PASSPHRASE`, `KALSHI_RSA_KEY_PATH` - only for
  live rebalance order placement; never needed for briefs, scans, or
  charts.
