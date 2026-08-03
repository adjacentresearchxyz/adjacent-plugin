---
name: adjacent
description: Explain and dispatch the safe Adjacent workflows exposed by the Hermes-native plugin. Lists the allowlisted native tools, shows the mid-quote / no-pp / no-em-dash conventions, and routes an intent to the right tool.
allowed-tools:
  - adjacent_portfolio_snapshot
  - adjacent_tracking
  - adjacent_chart_csv
  - adjacent_mcp_query
  - adjacent_tracking_table
  - adjacent_rebalance_plan
  - adjacent_datawrapper_index
  - adjacent_capability_status
  - adjacent_news_correlation
  - adjacent_correlation_regime
  - adjacent_news_latest
  - adjacent_candles_chart
  - adjacent_similar_hedges
  - adjacent_snapshot_health
  - adjacent_http_get
argument-hint: "[workflow <name>] [--explain]"
---

# /adjacent

The single slash command for the Hermes-native Adjacent plugin. Use it
to explain what the plugin can do safely, or to dispatch a supported
safe workflow.

## Arguments

| Arg | Effect |
| --- | --- |
| `workflow <name>` | dispatch the named workflow (see the table below) |
| `--explain` | print this help and the convention summary, then stop |

With no arguments, print the help summary and stop.

## Convention summary (the core rule)

All tracking, P&L, return, and percentage math uses mid quotes. The
native tools never model at ask or bid. Output units are `%`, never
`pp`. ASCII `-` bullets, no em-dash, no emoji - the `pre_tool_call`
hook blocks these in any write-capable payload.

## Supported safe workflows

Each workflow maps to one native tool that wraps an allowlisted local
script. The rebalance workflow is fail-closed: it computes a plan only
and never places an exchange order.

| Workflow | Tool | Script | Safe because |
| --- | --- | --- | --- |
| `portfolio_snapshot` | `adjacent_portfolio_snapshot` | portfolio-snapshot.py | read-only cached positions |
| `tracking` | `adjacent_tracking` | tracking-index.py | reads positions, writes tracking JSON |
| `chart_csv` | `adjacent_chart_csv` | chart-index.py | builds a CSV only |
| `mcp_query` | `adjacent_mcp_query` | mcp-cli.py | read-only list / find / get / price |
| `tracking_table` | `adjacent_tracking_table` | table-tracking.py | builds a CSV only |
| `rebalance_plan` | `adjacent_rebalance_plan` | rebalance-index.py | forced --dry-run / --json; never places |
| `datawrapper_index` | `adjacent_datawrapper_index` | datawrapper-index.py | defaults to --no-publish (CSV only) |
| `capability_status` | `adjacent_capability_status` | capability-status.py | reads local status only |
| `news_correlation` | `adjacent_news_correlation` | news-correlation.py | ranks live or supplied news vs mid moves |
| `correlation_regime` | `adjacent_correlation_regime` | correlation-regime.py | supplied JSON only; no live correlation call |
| `news_latest` | `adjacent_news_latest` | news-latest.py | read-only live news/latest fetch |
| `candles_chart` | `adjacent_candles_chart` | candles-chart.py | builds a mid-based CSV only |
| `similar_hedges` | `adjacent_similar_hedges` | similar-hedges.py | ranks supplied similar-market JSON |
| `snapshot_health` | `adjacent_snapshot_health` | snapshot-health.py | read-only public snapshot grading |
| `http_get` | `adjacent_http_get` | http-get.py | read-only GET of Adjacent surfaces only |

## Routing (intent -> workflow)

| Intent | Dispatch |
| --- | --- |
| "show my portfolio" / "what do I hold" | `portfolio_snapshot` |
| "tracking error for <slug>" | `tracking` |
| "build a chart CSV for <slug>" | `chart_csv` |
| "find / list / price a market" | `mcp_query` |
| "tracking table CSV for <slug>" | `tracking_table` |
| "rebalance plan for <slug>" / "preview rebalance" | `rebalance_plan` |
| "rebuild the <slug> Datawrapper chart" | `datawrapper_index` |
| "which APIs are available" | `capability_status` |
| "match these articles to price moves" | `news_correlation` |
| "pull the latest news" | `news_latest` |
| "flag correlation regime shifts" | `correlation_regime` |
| "chart the candles for <market>" | `candles_chart` |
| "find hedges for <market>" | `similar_hedges` |
| "are the public snapshots healthy" | `snapshot_health` |
| "download an export or the docs" | `http_get` |

## What this command does NOT do

- It never places an exchange order. `rebalance_plan` stops at the
  plan. Live order placement is owned by the standalone
  `scripts/rebalance-index.py` run by a human, never by this plugin.
- It never publishes without an explicit opt-in. `datawrapper_index`
  defaults to `no_publish=true`.
- It never logs a secret. The `secret-redactor` hook scrubs
  `ADJACENT_API_KEY`, `KALSHI_*`, and `DATAWRAPPER_API_KEY` from any
  captured output.

## Example

```
/adjacent workflow portfolio_snapshot
/adjacent workflow rebalance_plan --index example-index
/adjacent workflow mcp_query --tool list --type index
/adjacent --explain
```
