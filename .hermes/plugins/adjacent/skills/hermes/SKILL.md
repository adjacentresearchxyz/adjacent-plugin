---
name: hermes
description: Hermes host guidance for the native Adjacent tools, skills, hook, and /adjacent command.
version: 1.0.0
category: productivity
---

# Hermes

Use the native Adjacent plugin through `/adjacent` or its registered
tools. Load the relevant bundled skill for detailed task guidance.

## Voice

- Terse and numeric. Lead with the number, then the one-line why.
- Mid-quote for every price, return, move, and tracking figure.
- ASCII `-` bullets, `%` never `pp`, no em-dash, no emoji.
- Never invent data. If a market has no data, say so and move on.

## Defaults (zero-config)

- MCP tier: `adjacent-markets-dev`. Promote to `adjacent-markets` only
  when `ADJACENT_API_KEY` is set and the task publishes or is demoed to
  a paying user.
- Discovery is always live: slugs come from
  `adjacent-markets-dev/list(type=index)` (and `find`, `get`, `price`)
  at runtime. Never assume a baked-in slug.
- Charts: always Adjacent-branded via the `adjacent-chart-style` skill
  and `scripts/adjacent_chart_style.py`. Never a stock library default.
- Chart output: write PNGs under `$ADJACENT_STATE_DIR/charts` when set,
  else a temp dir. Prefer Datawrapper when `DATAWRAPPER_API_KEY` is set;
  otherwise the branded Seaborn fallback.
- Trading is fail-closed: rebalance only runs against a catalog whose
  `_schema._placeholders.value` is `false`, weekdays only unless
  `--allow-weekend`, and never places orders without an exchange key.

## Native workflows

Run `/adjacent` for help. It exposes:

- `portfolio_snapshot`
- `tracking`
- `chart_csv`
- `mcp_query`
- `tracking_table`
- `rebalance_plan`
- `datawrapper_index`
- `capability_status`
- `news_correlation` (live or supplied JSON)
- `correlation_regime` (supplied JSON only)
- `news_latest` (live news/latest fetch)
- `candles_chart`
- `similar_hedges`
- `snapshot_health`
- `http_get` (exports and docs archive)

For a daily run, delegate mover scanning and data-surface checks to
separate workers when the host exposes `delegate_task`, then pass their
results to a briefing worker. Do not repeat worker tasks in the parent.

## What Hermes does not do

- Native rebalance tools never place orders.
- No publishing or tweeting unless the user asks; the brief prints to
  stdout and the host decides where it lands.
- No secret values in output.
