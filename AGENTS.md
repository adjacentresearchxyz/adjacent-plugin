# AGENTS.md - adjacent-plugin

How any Claude agent (or human) should behave when authoring, running, or
scaffolding anything via this Adjacent plugin.

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

The `adjacent-rate-movers` skill has the canonical formulas.

## Output safety

The `secret-redactor` hook scrubs `ADJACENT_API_KEY`, `KALSHI_API_KEY`,
`KALSHI_PASSPHRASE`, `KALSHI_RSA_KEY_PATH`, `DATAWRAPPER_API_KEY`, and
`MCP_DUNE_API_KEY` from any Bash tool output before it is persisted to the
trajectory log. It does not modify command behavior; it only rewrites the
captured output.

## What this plugin intentionally does NOT include

- Manifold market-making tooling - a separate adj.news/labs experiment.
- Hyperliquid outcome deployer - a separate lab.
