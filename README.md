# adjacent-plugin

An open-source Claude Code plugin for the
[Adjacent prediction-market MCP](https://docs.adjacent.markets/explore/mcp).
Bundles skills, slash commands, sub-agents, safety hooks, and a few scripts
that turn the MCP into:

1. **Daily briefs** - `/briefing/morning` plus the `briefing-writer` sub-agent
   render a one-line timestamp + 1-bullet-per-idea report from the
   index-movers scan.
2. **Free-form Q&A** - `/data/ask <question>` plus the `ask-assistant` sub-agent
   route any topic through `adjacent-markets/find` -> `get` -> `price`.
3. **Easy charting** - `/charts/datawrapper-publish` plus the
   `datawrapper-tables` skill turn any CSV into a Datawrapper chart with
   emphasized % formatting.
4. **Index-mover scans** - `/data/index-movers` plus the `index-monitor`
   sub-agent report 1D / 7D / 30D moves on a configurable watchlist with
   thresholds at 1.5% / 4% / 8%.
5. **Direct indexing** - `/trading/rebalance-index` plus
   `rebalance-index.py` propose or place orders on any connected exchange
   (Kalshi today; the dispatcher is structured for additional adapters).

## Install

```
/plugin marketplace add adjacentresearchxyz/adjacent-plugin
/plugin install adjacent@adjacent-plugin
```

After install, every slash command is namespaced under `adjacent:` -
`/briefing/morning` resolves to `/adjacent:briefing/morning`,
`/data/ask` to `/adjacent:data/ask`, etc. The body of this README drops
the namespace for readability.

Paid tier (realtime) requires:

```
export ADJACENT_API_KEY=...
```

Without it the MCP falls back to the 15-minute-delayed snapshot tier, which
is fine for most briefs and scans.

## Default-install safety

**A fresh install does NOT place orders.** Daily briefs, charting,
`/data/ask`, and `/data/index-movers` work against real Adjacent data
out of the box. Placing real exchange orders requires a positive
opt-in: replacing the seeded catalog tickers via
`scripts/portfolio-snapshot.py --index <slug> --json`, then flipping
`_schema._placeholders.value: true -> false`. The fail-closed guard
in `scripts/rebalance-index.py` refuses the rest.

## The shipped fixtures

The plugin splits its seeded data into two catalogs with distinct
safety postures, plus a watchlist with real Adjacent slugs:

- `plugins/adjacent/data/adjacent_direct_indices.json` - the
  **trading catalog** read by `scripts/rebalance-index.py`. Keyed by
  `example-index` with constituents `example:INDEX-A`..`E` and
  `_schema._placeholders.value: true`. This is the file with the
  fail-closed safety net.
- `plugins/adjacent/data/adjacent_direct_indices.public.json` is NOT
  shipped. The plugin does not bake in any specific Adjacent slug.
  Catalog metadata for briefs, charts, scans, and Q&A comes from a
  live `mcp__adjacent_markets_dev__list(type=index)` call and is
  cached at runtime by the briefing / ask / index-monitor agents. To
  trade a slug, replace each constituent via a live MCP
  `get(type=index, id=slug)` call or via
  `scripts/portfolio-snapshot.py --index <slug> --json`.
- `plugins/adjacent/data/positions/example-index.json` - empty
  position seed for the trading catalog.
- `plugins/adjacent/data/positions/<your-slug>.json` - user-created
  per slug. The shipping target shape is `example-index.json`; the
  user copies it once they pick a slug and run their first
  `scripts/portfolio-snapshot.py --index <slug> --json`.

`scripts/rebalance-index.py` is fail-closed against the trading
catalog: it refuses to place orders until
`_schema._placeholders.value` is `false`, which it cannot become until
you replace each `example:INDEX-*` market id with a real one from a
live `scripts/portfolio-snapshot.py --index <slug> --json` run, then
flip the flag. The public catalog file is never read by the rebalance
script - structurally distinct from the trading catalog so the
fail-closed guard cannot be bypassed by a public install.

The default watchlist (`data/watchlist.json`) ships **empty by
design** so the plugin never bakes in any specific Adjacent slug.
The 1.5% / 4% / 8% thresholds and the news-correlation sources still
ship. The user populates the watchlist after the agents read
`mcp__adjacent_markets_dev__list(type=index)` on first run and
persist the slugs the user confirms they want followed.

## Layout

```
adjacent-plugin/
  AGENTS.md                          # enforced house conventions
  README.md
  .gitignore
  .claude-plugin/marketplace.json    # /plugin marketplace add source
  plugins/adjacent/
    .claude-plugin/plugin.json       # plugin manifest
    .mcp.json                        # adjacent + adjacent-dev MCP servers
    commands/
      briefing/morning.md            # /briefing/morning - daily brief
      data/ask.md                    # /data/ask - free-form Q&A
      data/index-movers.md           # /data/index-movers - watchlist scan
      data/market-find.md            # /data/market-find - find single market
      trading/portfolio-snapshot.md  # /trading/portfolio-snapshot
      trading/rebalance-index.md      # /trading/rebalance-index
      charts/datawrapper-publish.md  # /charts/datawrapper-publish
    agents/
      ask-assistant.md               # routes /data/ask
      briefing-writer.md             # writes the /briefing/morning output
      index-monitor.md               # produces /data/index-movers scan
    hooks/
      pre-tool-use/conventions.py    # writing-rules enforcer
      pre-tool-use/secret-redactor.py # secret-print blocker
      post-tool-use/mover-logger.py  # logs threshold hits for the brief
    skills/
      adjacent-direct-index/         # rebalance framing
      adjacent-markets/              # mid-quote + dev-MCP conventions
      adjacent-rate-movers/          # 1.5% / 4% / 8% thresholds
      adjacent-news-correlation/     # cause -> effect joining
      briefings/                     # morning brief format
      datawrapper-tables/            # CSV -> chart pipeline
      kalshi-api/                    # RSA-PSS + V2 conventions
      kalshi-direct-indexing/        # allocation math + fees
    data/
      adjacent_direct_indices.json          # trading catalog (fail-closed)
      adjacent_direct_indices.public.json   # public Adjacent metadata, no constituents
      watchlist.json                        # default slugs + thresholds
      positions/example-index.json             # only seed; user copies for their own slugs
  scripts/
    rebalance-index.py               # --index <slug> --exchange kalshi
    tracking-index.py
    chart-index.py
    table-tracking.py
    portfolio-snapshot.py
    datawrapper-create.py
    datawrapper-publish.py
    datawrapper-index.py
    mcp-cli.py                       # find / get / list / price CLI
```

## Secrets

All from the environment, never written to files:

| Var | Used by |
| --- | --- |
| `ADJACENT_API_KEY` | Adjacent realtime MCP tier |
| `KALSHI_API_KEY` | Kalshi HTTP API key id |
| `KALSHI_PASSPHRASE` | Kalshi RSA key passphrase |
| `KALSHI_RSA_KEY_PATH` | Kalshi RSA key file (RSA-PSS) |
| `DATAWRAPPER_API_KEY` | Datawrapper publishing |

The `secret-redactor` hook scrubs these from Bash output before it is
persisted to the trajectory log. The `conventions` hook enforces the
house writing rules on every Write / Edit / Bash input.

## House conventions

See `AGENTS.md` for the full ruleset. The abbreviated summary:

- Mid-quote pricing throughout. Tracking, P&L, moves all at mid.
- ASCII `-` bullets, never the unicode bullet glyph.
- `%` (percent), never `pp` (percentage points).
- No em-dash anywhere (`-` or `:` or rephrase).
- No emojis.
- Direct-index drift threshold: 1%. Index-mover thresholds: 1.5% (1D),
  4% (7D), 8% (30D).

## Exchange support

The `rebalance-index.py` script ships with a Kalshi V2 adapter. The
dispatcher is a small registry - `EXCHANGES = {"kalshi": kalshi_handler}`
- so additional exchanges (Polymarket CLOB, Manifold AMM, Hyperliquid,
  etc.) plug in without rewriting the surrounding workflow. Pass
`--exchange kalshi` today; more adapters land in future versions.

## What this plugin intentionally does NOT include

- Manifold market-making tooling - separate adj.news/labs experiment.
- Hyperliquid outcome deployer - separate lab.
