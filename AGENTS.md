# AGENTS.md - adjacent-plugin

How any agent or human should behave when authoring, running, or
scaffolding anything via this Adjacent plugin repository.

## Pricing convention (the core rule)

All tracking, P&L, return, and percentage math uses mid quotes. The Adjacent
indices publish YES / NO ask + YES / NO bid; the `price` MCP tool returns
either compact summaries or raw timeseries with `bid` / `ask` / `mid`.
Modeling at ask or bid overstates or understates slippage and produces
misleading tracking error.

- Tracking report = `(mid_portfolio_return - mid_index_return)` in `%`.
- Rebalance decisions fire on mid price moves, not on last-trade prints.
- News correlation: align timestamps at the minute, compare mid deltas
  only.
- The `conventions` hook refuses any P&L line whose unit is `pp` instead of
  `%`.

## MCP tiers

| Tier | Used when |
| --- | --- |
| 15-min delayed | public, no `ADJACENT_API_KEY`, fine for non-cost-sensitive workflows |
| Realtime | `ADJACENT_API_KEY` set, required for rebalance and live alerts |

Default to `adjacent-markets-dev` for broadcasting and experimentation.
Promote to `adjacent-markets` when the workflow publishes or is being demoed
to a paying user.

## Exchange specifics (today: Kalshi)

The direct-index rebalance targets a single exchange flagged by `--exchange`.
Each adapter has its own auth and endpoints; they are exposed through a
small dispatcher in `scripts/rebalance-index.py`. Today only Kalshi is
implemented; the dispatcher is shaped so additional exchanges plug in
without touching the surrounding workflow.

Kalshi specifics:

- Use the V2 order endpoint (`/v2/portfolio/orders`); V1 is deprecated.
- RSA-PSS signing via `KALSHI_RSA_KEY_PATH`. `KALSHI_API_KEY` is the key
  id, `KALSHI_PASSPHRASE` is the human passphrase; neither is ever logged.
- Account balance quirks: settlements debit / credit on `close`, not on
  `fill`. The rebalance script reconciles `settled` vs `pending`.
- Tracking error components: drift, selection, fee impact, fill-queue
  penalty.

## Writing rules (enforced by `hooks/pre-tool-use/conventions.py`)

- ASCII `-` bullets; never the unicode bullet glyph (codepoint U+2022).
- `%` (percent); never `pp` (percentage points).
- No em-dash anywhere; use `-` or `:` or rephrase.
- No emojis in body, tables, chart titles, log lines.
- ASCII `-` inside numeric ranges (`4-7%`) is fine.
- Currency: `$100` not `100 USD`. Decimal: `0.012` not `.012`.
  Date: `YYYY-MM-DD`.

## Position file schema

Each `data/positions/<slug>.json` (read by `scripts/portfolio-snapshot.py`)
holds:

```json
{
  "format_version": 1,
  "_schema_ref": "fields_per_position and producers are documented in AGENTS.md section 'Position file schema'.",
  "index": "<slug>",
  "exchange": "kalshi",
  "positions": [],
  "last_fill_ts": null,
  "as_of": null
}
```

After `portfolio-snapshot.py --index <slug> --json` runs, each entry
in `positions` carries:

| Field | Meaning |
| --- | --- |
| `market_id` | `platform:raw` form; matches Adjacent MCP id |
| `size` | integer contract count, signed |
| `side` | `yes` or `no` |
| `notional` | abs cash notional at current mid |
| `mid` | current mid-quote price, `0.0`-`1.0` |
| `mid_open` | mid quote at fill time (for `move_1d`) |
| `cost_basis` | average fill price for P&L |
| `current_weight` | `notional / total_portfolio_NAV` |
| `index` | slug of the index this position belongs to |
| `exchange` | which adapter owns this position - `kalshi` today |
| `fees` | realized fees for this position, dollars |
| `fill_queue_pct` | absolute mid-vs-fill deviation, in `%` |
| `as_of` | ISO timestamp of the latest fill |

Producers: `scripts/portfolio-snapshot.py` writes the file from
exchange API + Adjacent price snapshots; `scripts/tracking-index.py`
reads it and emits `data/tracking/<slug>.json`;
`scripts/rebalance-index.py` then modifies `size`, `mid_open`,
`cost_basis`, and `as_of` after each weekday 16:00 ET cycle.

## Direct index rebalance cron

Runs weekdays 16:00 ET for any index whose catalog record is present. The
plugin slash-command equivalent is `/trading/rebalance-index`:

1. Pull constituents + weights from the `adjacent-direct-index` skill
   guidance and the trading catalog under
   `data/adjacent_direct_indices.json`. The plugin does not ship
   public Adjacent slugs baked in - any per-slug metadata for briefs
   / charts / Q&A is discovered at runtime via
   `mcp__adjacent_markets_dev__list(type=index)` and is never the
   input to a plan.
2. Pull live prices via `price` MCP with `raw: false` for each market.
3. Compute drift = `(current_weight - target_weight) / target_weight`.
4. Sell constituents with drift >= +1% (mid-based) and any name flagged
   for removal in the catalog.
5. Buy new constituents with positive target weight, sized to fill the
   notional target.
6. Track-fill reconcile; emit tracking table.

The shipped catalog ships with `_schema._placeholders.value: true`, so any
attempt to place orders before the user has replaced the example tickers
is refused by the fail-closed guard.

## Index-mover thresholds

| Horizon | Threshold | Action |
| --- | --- | --- |
| 1D | `|move| >= 1.5%` | alert + append to movers log |
| 7D | `|move| >= 4%` | alert + append to movers log |
| 30D | `|move| >= 8%` | morning-briefing highlight |

The `adjacent-index-movers` skill has the canonical formulas.

## Output safety

Two hooks defend against secrets leaking into the trajectory log:

- The **pre-tool-use** `secret-redactor` hook BLOCKS commands that would
  print secrets (`echo`, `cat`, `printenv`, `env`, `curl -H "Authorization:
  Bearer $..."`, etc.) and Write/Edit/ApplyPatch content containing raw
  secret tokens. It denies the call before it runs.
- The **post-tool-use** `secret-scrubber` hook scans tool output
  (`stdout`, `stderr`, and other response string fields) for raw secret
  patterns (`sk_live_*`, `dwk_*`, `Bearer` tokens, PEM private keys) and
  reports what was redacted via `additionalContext`. It is defense-in-depth:
  any secret that slips past the pre-tool-use block is flagged after the
  call returns.

Neither hook modifies command behavior. The pre-tool-use hook denies the
call; the post-tool-use hook reports what was redacted. The blocked env var
names cover `ADJACENT_API_KEY`, `KALSHI_API_KEY`, `KALSHI_PASSPHRASE`,
`KALSHI_RSA_KEY_PATH`, `DATAWRAPPER_API_KEY`, and `MCP_DUNE_API_KEY`. The
post-tool-use scrubber only catches raw secret values, not env-var-expanded
output; the pre-tool-use blocker is the primary defense against env-var
expansion.

## Chart branding (every chart is an Adjacent chart)

All charts this plugin produces - Datawrapper embeds, the Seaborn
fallback, Plotly exports, any matplotlib output - must look like
Adjacent, not like a stock library default. The canonical spec is the
`adjacent-chart-style` skill, derived from the Adjacent Design System
tokens (`design-system/src/tokens.css`) and the Storybook chart
components (`Chart`, `ChartRenderer`, `TradingViewChart`,
`FullscreenChart`).

The reusable Python helper is
`scripts/adjacent_chart_style.py`. It carries the palette, the
matplotlib/seaborn theme, the Plotly template, and the source-line
stamper. Prefer it over re-deriving values by hand.

Source of truth and precedence (charting):

1. The executable behavior and public exports in
   `scripts/adjacent_chart_style.py` - the canonical helper.
2. This `AGENTS.md` section (writing rules + safety).
3. The host chart-style skill copies and
   `docs/charting-plugin-update.md`, which describe the helper.
4. Individual producer scripts.

Do not inline the helper source, palette values, or API into Markdown,
and do not fork the helper API in a host skill. Reference the helper by
its repository-relative path (`scripts/adjacent_chart_style.py`); an
installed runtime path may be mentioned as an example but must not be
the only path. When the helper changes, update this section, the three
host skill copies, and `tests/test_chart_style_contract.py` together.
Resolved rules: keep the six-color `SERIES` cycle (deep green, salmon,
sky, mustard, sage, pink), use a UTC timestamp in rendered
`Source: Adjacent` credits, do not require an x-axis title when the deck or
context already communicates the unit, and label bars outside by
default with explicit exceptions for large stacked segments.

Canonical chart artifact: the matplotlib PNG produced via
`scripts/adjacent_chart_style.py` is the canonical chart artifact for
this plugin. It carries the full editorial layout - headline, deck,
last-value pill, Heikin-Ashi candles, source credit - and is what
tracking reports, briefs, and movers scans embed. Datawrapper is for
interactive embeds only; it shares the brand tokens (palette, series
cycle, font stacks) but does not replicate the editorial layout. Fonts
are now bundled under `assets/fonts/` (OFL-licensed Inter and IBM Plex
Mono static TTFs) and registered by the helper's
`apply_adjacent_theme()` before rcParams are set, so chart output is
deterministic across machines and does not fall through to a host's
system fonts. The helper resolves the font directory relative to its
own path (or `ADJACENT_PLUGIN_ROOT` when set) and skips silently when
the assets are absent, so environments without the bundle still render
through the font stacks.

On-brand summary (see the skill for the full table):

- Canvas `#ece9e2` (figure and plot area - one surface); paper
  `#ffffff` is a token for non-plot panels only.
- Ink `#0a0f0d`; deep `#0e2a1f`.
- Lone series: deep forest green `#0e2a1f`. Directional up `#0e2a1f`; down
  `#9b3a2e`. The six-series cycle is deep green, salmon, sky, mustard,
  sage, and pink.
- Series cycle: deep `#0e2a1f`, salmon `#e66b55`, sky `#6fb7e0`,
  mustard `#d89a3f`, sage `#a8c49a`, pink `#f0a8c8`.
- Hairline `#d6d2c8`; grid `#ecebea` (dotted, behind data).
- Fonts mirror the design-system tokens: `--font-main` is Inter and
  `--font-mono` uses IBM Plex Mono for ticks and data values. Never name
  a font directly; use the stacks.
- Square corners (`--radius: 0`); only the x baseline spine.
- Horizontal gridlines only. Color is for distinguishing two or more
  series, never a lone line by direction.
- Source credit bottom-left: `Source: Adjacent YYYY-MM-DD HH:MM UTC`. No wordmark, no
  divider rule, no basis clause.
- Headline states the finding; the deck is just the identifier.
- Axis ticks carry the unit on the top tick only; stated values use
  `0.00%`. Never `pp`. No em-dash, no emoji.
- Candles: Heikin-Ashi only (never raw candlesticks).

Enforcement:

- The `chart-style` pre-tool-use hook blocks Write/Edit of chart code
  that hardcodes a hex outside the Adjacent palette or uses a generic
  library colormap (`viridis`, `tab10`, `muted`, ...) without importing
  `adjacent_chart_style`. It nudges (additionalContext) on chart code
  that has no Adjacent signal yet.
- The `conventions` hook still enforces no-em-dash / no-`pp` / no-emoji
  on chart titles and metadata payloads.

## Agent packages

Keep shared behavior, scripts, and data platform-neutral. Place host
metadata and integration details only in that host's package directory.

All hosts use the same defaults: dev MCP unless `ADJACENT_API_KEY` is
set, mid-quote math, Adjacent-branded charts, live slug discovery, and
fail-closed trading.

## What this plugin intentionally does NOT include

- Manifold market-making tooling - a separate adj.news/labs experiment.
- Hyperliquid outcome deployer - a separate lab.
