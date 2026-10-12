---
name: adjacent-workflows
description: Use when routing an Adjacent request to a brief, movers scan, chart, Q&A, portfolio snapshot, or rebalance and the matching command is not already loaded.
version: 1.0.0
category: productivity
---

# Adjacent workflows

Use this skill to route Adjacent tasks to the correct command, skill,
and specialist agent. Load `using-adjacent` first at session start.

## Evidence before claims

No mid, move, tracking error, or P&L figure without a fresh `price`
call or producer script in this turn. Typed failures are answers.
Never invent an endpoint response.

## Specialist dispatch

When handing work to coordinator, index-monitor, data-monitor,
briefing-writer, or ask-assistant, send a fresh brief: ids or
watchlist, MCP tier, thresholds, and output shape. Do not forward
the full conversation. Each specialist loads its own skill.

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

## Routing table (intent -> load this)

| Intent | Command | Skill(s) | Agent |
| --- | --- | --- | --- |
| Run the whole daily loop | `/daily` | this skill | coordinator |
| Morning brief | `/briefing/morning` | briefings, adjacent-index-movers | briefing-writer |
| Scan for movers | `/data/index-movers` | adjacent-index-movers | index-monitor |
| Free-form question | `/data/ask` | adjacent-markets, briefings | ask-assistant |
| Find a market | `/data/market-find` | adjacent-markets | - |
| Pull the latest news | `/data/news-latest` | adjacent-news-correlation | - |
| Topic update (news + markets + charts) | `/data/topic-brief` | adjacent-topic-brief, adjacent-chart-style, briefings | - |
| Explain a move from news | `/data/news-correlation` | adjacent-news-correlation | - |
| Chart a market from candles | `/data/candles-chart` | adjacent-data-surfaces, adjacent-chart-style | - |
| Find hedges for a market | `/data/similar-hedges` | adjacent-data-surfaces | - |
| Check public snapshot health | `/data/snapshot-health` | adjacent-data-surfaces | - |
| Fetch a data export | `/data/export` | adjacent-data-surfaces | - |
| Answer a docs question | `/data/docs-ask` | adjacent-data-surfaces | - |
| Make a chart | `/charts/datawrapper-publish` | adjacent-chart-style, datawrapper-tables | - |
| Portfolio snapshot | `/trading/portfolio-snapshot` | adjacent-direct-index | - |
| Rebalance an index | `/trading/rebalance-index` | adjacent-direct-index, kalshi-direct-indexing, kalshi-api | - |

## The daily loop

When asked to run the daily workflow:

1. Scan movers on the watchlist (or a live `list` if the watchlist is
   empty). Thresholds: 1D `>= 1.5%`, 7D `>= 4%`, 30D `>= 8%`.
2. Pull the live `news/latest` surface (or supplied article JSON) and
   rank news-to-mid moves.
3. Render a branded tracking chart per hit with the
   `adjacent-chart-style` helper.
4. Write the brief per the `briefings` skill (timestamp line + 1 bullet
   per idea, mid-quoted).
5. If the user authorized trading, propose a rebalance with
   `/trading/rebalance-index --dry-run` and stop for confirmation.

## Limits

- No order placement without an explicit, non-dry-run instruction and a
  configured exchange key.
- No publishing or tweeting unless the user asks; the brief prints to
  stdout and the host decides where it lands.
- No secret ever printed; the `secret-redactor` hook enforces this.
