# Adjacent charting: complete spec + inventory for plugin update

Consolidated from the live skills (`adjacent-chart-style`,
`adjacent-chart-production`), the canonical helper
(`scripts/adjacent_chart_style.py` in this repository), and the
working reference scripts. Purpose: give an updating agent everything
needed to keep the plugin's chart output on-brand without breaking the
patterns Lucas has approved in practice.

> **Source of truth and precedence.** The executable behavior of
> `scripts/adjacent_chart_style.py` is the canonical source. `AGENTS.md`
> and the host chart-style skills (`plugins/adjacent`,
> `.factory/skills`, `.hermes/plugins/adjacent`) describe it. This
> document is an operational companion: where it disagrees with the
> helper, the helper wins. Do not inline or fork the helper API into
> Markdown; reference it by its repository-relative path. The
> `/opt/data/...` paths that appear below are deployment examples from
> the production host, not canonical locations.

---

## 1. Brand spec (one-line rule)

If a chart does not read as Adjacent on first glance - beige canvas,
near-black ink, deep forest green (`#0e2a1f`) accent family, mono tick
labels, square corners, hairline rules, dotted grid, `Source: Adjacent`
- it is wrong.

### Palette (canonical hex, never hand-pick)

These mirror the `--comp-*` tokens exactly. Never hand-pick a divergent
hex; reach for another token from this table or from `adj.PALETTE`.

| Role | Token | Hex | Use |
| --- | --- | --- | --- |
| canvas | `--comp-canvas` | `#ece9e2` | figure / page background |
| paper | `--comp-paper` | `#ffffff` | non-plot panels only (axes use canvas) |
| ink | `--comp-ink` | `#0a0f0d` | title, axis labels, primary text |
| deep | `--comp-deep` | `#0e2a1f` | dark header surfaces, deep-tone charts |
| green | `--comp-green` | `#3fae5a` | primary accent, positive series |
| green-2 | `--comp-green-2` | `#22c55e` | hover / brighter accent |
| green-deep | Chart accent | `#0e6b3a` | featured / hero single-series accent |
| salmon | `--comp-salmon` | `#e66b55` | semantic negative, badges |
| sky | `--comp-sky` | `#6fb7e0` | info badge |
| mustard | `--comp-mustard` | `#d89a3f` | warning badge |
| sage | `--comp-sage` | `#a8c49a` | muted positive, series 5 |
| pink | `--comp-pink` | `#f0a8c8` | series 6 |
| chart-orange | ChartRenderer | `#e87d2a` | series 2 |
| chart-blue | ChartRenderer | `#4a90d9` | series 3 |
| chart-purple | ChartRenderer | `#b85cce` | series 4 |
| trend-down | TradingViewChart | `#c0392b` | down trend line / area |
| rule | `--comp-rule` | `#d6d2c8` | hairline, axis edge |
| grid | `--comp-grid` | `#ecebea` | dotted gridline |
| fg-2 | `--fg-2` | `#5c5a53` | secondary text, legend |
| fg-3 | `--fg-3` | `#7f7d7a` | meta, source credit |
| up | `--paper-up` | `#2a6a3a` | readable positive tick text |
| down | `--paper-down` | `#9b3a2e` | readable negative tick text |

### Categorical series cycle

Draw series in this exact order so multi-series charts read the same as
the product charts: `green` `#3fae5a`, `chart-orange` `#e87d2a`,
`chart-blue` `#4a90d9`, `chart-purple` `#b85cce`, then `sage` and
`pink` for a rare 5th / 6th series. This is the `ChartRenderer` default
cycle from Storybook. The helper exposes it as `adj.SERIES` and sets it
as the matplotlib `axes.prop_cycle`, so `ax.plot(...)` picks it up with
no color argument.

### Directional color

- up / positive: `adj.UP` = `green` (`#3fae5a`); use `up` (`#2a6a3a`)
  for tick text on the light canvas.
- down / negative: `adj.DOWN` = `trend-down` (`#c0392b`); use `down`
  (`#9b3a2e`) for tick text.
- `adj.SALMON` (`#e66b55`) is the semantic negative for badges.

A single line is off-black (`adj.LINE` = `#0a0f0d`). Do not color a lone
line by direction. `adj.ACCENT` / `adj.ACCENT_DEEP` (green) are for a
chart that is deliberately featured, never to signal direction.

### Typography

Three stacks, mirroring the design-system tokens exactly. Inter is the
only face adjacent.markets actually loads; `--font-mono` and
`--font-serif` are the CSS generics, so these stacks lead with what
those generics resolve to. Do not substitute a "nicer" mono or serif.

| Token | Stack | Use in chart |
| --- | --- | --- |
| `--font-main` | Inter, Helvetica Neue, Helvetica, Arial, sans-serif | headline, axis titles, legend, source credit |
| `--font-serif` | Times New Roman, Times, DejaVu Serif, serif | the deck under the headline |
| `--font-mono` | Menlo, DejaVu Sans Mono, Courier New, monospace | tick labels, data values, tabular numeric |

Never name a font directly in chart code; use `adj.FONTS["main"]`,
`["serif"]`, `["mono"]`.

- Title: Inter, bold, left-aligned, ink. No em-dash, no emoji.
- Subtitle / deck: serif, regular, `fg-2`. The identifier, one word.
- Tick labels + data callouts: mono, tabular, ink.
- Source eyebrow: Inter, 8.5px, `fg-3`, bottom-left.

### Layout + grid

- Square corners everywhere. `--radius: 0`; no rounded bars or patches.
- All-beige: axes facecolor = canvas `#ece9e2`. No white panel.
- No borders: the x baseline is a solid rule; top / right / left spines
  are hidden (`adj.frame(ax)` and `adj.save()` enforce this).
- Grid: dotted (`:`), color `#ecebea`, 0.7px, behind data, horizontal
  only.
- Figure facecolor = canvas.
- Legend: no frame. Prefer `adj.swatch_legend(fig, entries)` in the
  header band, or `adj.series_label(...)` at a line's right end. A
  matplotlib legend inside the plot is a last resort and must not cover
  data.

### Number formatting

- Percent: `0.00%`. Never `pp`. `adj.percent_formatter()` renders 0-1
  fractions as `12.34%` (fraction data ONLY).
- Currency: `$100`, `$1.2M`, `$1.2B`. Use `adj.currency_formatter()`.
- Counts: `1.2k`, `1.2M`, `1.2B`. Use `adj.number_formatter()`.
- Dates: `YYYY-MM-DD`. Decimals: `0.012` not `.012`.
- All pricing is mid-quote, but the source line says ONLY `Adjacent`.

### Source line

Every published chart carries a source eyebrow bottom-left:

`Source: Adjacent`

`adj.SOURCE_DEFAULT` is exactly `"Adjacent"`. `adj.save()` stamps it
automatically; `adj.source_line(fig, text)` overrides it. Nothing else:
no "mid-quote", no basis clause, no wordmark, no divider rule. Do not
add a timestamp to the source text - the helper, `AGENTS.md`, the host
skills, and the contract tests would all need to change together first.

---

## 2. Hard rules (Lucas's corrections, in order of pain)

1. Source line is exactly `Source: Adjacent`. No "mid-quote", no basis
   clause, no wordmark, no divider, no timestamp.
2. Titles and axis labels short and direct. No clarifying clauses,
   parentheticals, or comma chains. Good: `GOVBGD vs direct
   replication`, `Rebased level`. Bad: `GOVBGD vs direct replication,
   hourly mids (rebased)`.
2a. No explanatory footer notes under the chart. If a takeaway is worth
    saying, put it in the chat message, not on the chart.
2b. Titles ALWAYS left-aligned (`axes.titlelocation: left` in rcParams).
3. Never conventional candlesticks. Use Heikin-Ashi monochrome
   Investopedia style (recipe in section 5). `adj.heikin_ashi(...)` is
   the only candle entry point.
4. Give charts room: generous margins. `adj.figure()` defaults to
   `figsize=(7.6, 4.6)`.
5. Deep forest green `#0e2a1f` is the deep anchor; `#3fae5a` green is
   the primary accent. The series cycle above is canonical.
5b. Generous spacing everywhere EXCEPT value labels (tight to ends).
6. All-beige background - NO white panel (axes facecolor = canvas).
7. No borders around charts - top / right / left spines hidden.
8. Data value labels never inside a chart item: vertical bars label
   above positive / below negative, offset outside; horizontal bars
   label beside the bar end, close. `adj.bar_labels(...)` handles this.
9. Axis furniture: y-label pad 12, unit on the top tick only
   (`adj.y_axis(ax, kind)`). An x-axis title is NOT required when the
   deck or chart context already communicates the unit. x-axis shows
   pure dates only via `adj.format_date_axis(ax)`; offset suppressed, no
   hour/date mixing.
10. All data tables are chart images (matplotlib `table()` as PNG in
    the brand), never inline markdown tables. The chat message carries
    the read; the data lives in the image.

### percent_formatter() pitfall (hit twice)

`adj.percent_formatter()` renders 0-1 fractions as `0.00%` (multiplies
by 100). ONLY for fraction-unit data. If the series is ALREADY in
percent units (rebased levels ~100-107, or %-change computed as
`(v/v0-1)*100`), use a plain FuncFormatter:

```python
import matplotlib.ticker as mticker
ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda v, p: f"{v:.0f}%"))  # %-unit data
ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda v, p: f"{v:.1f}"))   # rebased levels
```

Rule: fraction data (`0.05` = 5%) -> `percent_formatter()`; percent-unit
data (`-2.91` = -2.91%) -> plain FuncFormatter.

---

## 3. Canonical helper API

Path (repository-relative, canonical):
`scripts/adjacent_chart_style.py`. A deployment may keep a synced copy
elsewhere (for example `/opt/data/scripts/adjacent_chart_style.py`);
keep it identical, and treat the repository path as canonical.

Load:

```python
import sys
sys.path.insert(0, "scripts")  # or the plugin scripts dir on the host
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import adjacent_chart_style as adj

adj.apply_adjacent_theme()   # call before any plt.*/sns.*
```

### Key exports

| Export | Purpose |
| --- | --- |
| `PALETTE` | token -> hex dict (canvas, paper, ink, deep, green, green-2, green-deep, salmon, sky, mustard, sage, pink, chart-green, chart-orange, chart-blue, chart-purple, trend-down, rule, hover, grid, fg-2, fg-3, on-deep, up, down) |
| `SERIES` | categorical cycle: chart-green, chart-orange, chart-blue, chart-purple, sage, pink |
| `LINE` / `ACCENT` / `ACCENT_DEEP` | lone-series / featured accents |
| `UP` / `DOWN` / `SALMON` | directional / semantic colors |
| `FONTS` | main / serif / mono stacks |
| `SOURCE_DEFAULT` | exactly `"Adjacent"` |
| `apply_adjacent_theme()` / `apply_adjacent_style()` | rcParams + seaborn theme; sets axes.facecolor = canvas |
| `figure(headline, deck, source, figsize, panels)` | themed figure factory; declares the header + footer |
| `frame(ax)` | spine / grid styling per brand |
| `y_axis(ax, kind, unit_on_top, decimals)` | y-axis styling; `kind` in percent / currency / number / level |
| `format_date_axis(ax, concise, fmt, rotation, maxticks)` | dates only, concise by default, offset suppressed, hard tick cap |
| `end_label(ax, x, y, text, color, above, dx, dy)` | endpoint callout, offset off the line |
| `series_label(ax, x, y, text, color, dx, dy)` | inline series label at the right end |
| `last_value(ax, x, y, text, color, reference)` | closing-value filled pill + dotted reference line |
| `event_markers(ax, events, rule, wrap)` | dated event rules + labels |
| `bar_labels(ax, bars, values, fmt, color)` | bar value labels (handles negatives) |
| `percent_formatter()` / `currency_formatter()` / `number_formatter()` | tick formatters |
| `title_block(ax, title, subtitle)` | declare headline + deck on an existing figure |
| `area_series(ax, x, y, color, label, linewidth, alpha, baseline)` | filled area series (default off-black) |
| `swatch_legend(fig, entries)` | frameless header legend from `(label, hex)` pairs |
| `source_line(fig, text)` | override the source credit |
| `save(fig, path, source, dpi)` | layout + stamp source + write PNG; returns the absolute path |
| `plotly_template()` | Plotly layout dict |
| `heikin_ashi_transform(...)` / `heikin_ashi(...)` | HA transform + monochrome renderer |
| `stacked_area`, `waterfall`, `waffle`, `range_dumbbell`, `heatmap_row`, `radar`, `quote_board`, `prob_stack`, `small_multiples` | chart forms |

### save() details

- Signature: `save(fig, path, *, source=None, dpi=200)`. There is no
  `reserve_bottom` / `reserve_right` parameter; `save()` measures the
  declared header and footer and reserves the room itself. Right-side
  callouts (`last_value`, `series_label`) reserve their own gutter.
- Do NOT call `fig.savefig` or `bbox_inches="tight"` - `adj.save()`
  owns layout; it returns the absolute path written.
- `save()` re-applies the theme, sets canvas facecolor on every axes,
  hides top / right / left spines, and styles tick labels mono.

---

## 4. Chart types Lucas likes (approved)

- Stacked horizontal bars (Energy Institute / FT style): bold headline
  + one-line subtitle + legend row above, one row per entity, segments
  share a common zero, thin gaps, bold white value labels, dashed
  reference line at 50.
- Dumbbell / range chart: low-high line per series, circles at range
  ends, black diamond at current, bold current value above.
- Heatmap strips: one-row imshow panels, brand diverging colormap
  (NEVER library colormaps like RdYlGn - build
  `LinearSegmentedColormap.from_list("adjacent_div",
  ["#9b3a2e", "#ece9e2", "#0e2a1f"])` with `TwoSlopeNorm`), values in
  cells, `origin="lower"` (else rows invert and the chart silently
  lies).
- Sparkline + quote-board table: Bloomberg dense table (direction-coded
  change, mono decimal-aligned, dark header, zebra) under a WSJ-clean
  headline sparkline. Use matplotlib `table()`, never hand-placed text.
- Waterfall: index level construction (base 50 + weighted contributions
  = level). `attribution[].contribution` is a FRACTION (x100 first).
- Waffle: 100-square grid per entity = probability. Header in a
  dedicated row ABOVE the grid.
- Radar: multi-axis polygon on polar axes. `adj.save()` is incompatible
  with polar axes - manual path: hide spines, `fig.patch` canvas,
  `adj.source_line`, `fig.savefig`. Brand fill sage tint at ~0.55 alpha,
  never deep at 0.25 (reads library-gray).
- Lollipop: dot-on-stem move ranking.
- Donut: weight composition (`ax.pie(vals, wedgeprops={"width": 0.42})`
  + center text). `state_exposure[].probability` is ALREADY percent
  units (`31.94` = 31.94%) - do NOT x100.
- Slope / crossing: two party lines over time, rebased to 100, solid
  deep vs dashed lighter green.
- Bullet: 7d range per index with current-level dot.
- Small multiples: grid of titled panels, ink lines, no legend.
- Index 7d ranges (bullet) + 7d paths small-multiples: force `pts[-7:]`
  (dev REST returns FULL history despite `period=7d`); per-panel y step
  scales with span; `DayLocator(interval=1)` + `%b %d` on multi-col
  grids.
- Long-window multi-index trend (Silicon Data style): rebase to 100,
  dashed base line at 100 with `Base = 100` annotation, monthly ticks
  (`MonthLocator` + `%b %y`), inline current values in the legend. dev
  REST caps ~100 daily points per call.
- Battleground state leanings: two-panel horizontal 100% stacked bars
  (GOP deep left, Dem lighter green right), dashed 50% reference, white
  value labels inside segments, sorted by GOP share. Parse state label
  from `display_ticker` (`SENATEMI-26-R` -> `MI '26`), NEVER from the
  long market name. Small segments (<12%): white label inside at
  fontsize 8 - an explicit exception to the "labels outside bars"
  default, because the segment is large enough to hold it legibly.
- Single-district highlight: featured district `down` `#9b3a2e`, rest
  deep, `xlim(0,110)` with labels right of bar end.
- Candidate/affiliation breakout: target candidates deep green, others
  lighter, red italic candidate name inside dark bar, value at bar end.
  Label races with state AND cycle (`NC '26` vs `NC '28`) via a
  `-(\d{2})-` regex on `display_ticker`.
- Candidate cohort + field-discount: cohort lollipop (dot on stem,
  colored by chamber, 50% line) + field-discount grouped bar.
  METHODOLOGY PITFALL: compare candidates against a field average of
  COMPARABLE seats only (price >= 50 floor) - including R-favored seats
  makes safe-seat candidates look wrongly discounted. LABEL
  CONSISTENCY: bar values and gap labels at the SAME precision (1
  decimal) so the gap visibly equals the difference.
- Constituent detail table (10 columns): State | Ticker | Contracts |
  Purchase | Price | Value | Weight | Return | OI (k) | Vol (k).
  Header deep green white bold, body beige no borders no zebra, total
  row bold, footer summary, wide figure 16x8.5, `matplotlib.table()`
  with `cellLoc`/`colLoc` left. Pitfall: place empty string in State
  col (index 0) and `TOTAL` in Ticker col (index 1) or the total lands
  in the wrong column.

---

## 5. Heikin-Ashi recipe (monochrome Investopedia style)

Transform (matches `adj.heikin_ashi_transform`):

```python
ha_c[i] = (o[i] + h[i] + l[i] + c[i]) / 4.0
ha_o[0] = (o[0] + c[0]) / 2.0
ha_o[i] = (ha_o[i-1] + ha_c[i-1]) / 2.0
ha_h[i] = max(h[i], ha_o[i], ha_c[i])
ha_l[i] = min(l[i], ha_o[i], ha_c[i])
```

Render with `adj.heikin_ashi(ax, x, opens, highs, lows, closes)`:

- bullish (HA-close >= HA-open): hollow body filled with canvas beige,
  ink edge
- bearish: solid charcoal (ink) body
- thin ink wicks, optional graph-paper grid, y axis on the right with
  arrowheads on the top tick

Never draw raw candlesticks.

---

## 6. Direct index value chart (hourly mid)

Recurring ask: "chart my GOVBGD direct index value over the last few
days" - portfolio value vs the GOVBGD index, both rebased to 0% at
start, from true hourly mids.

- Pull hourly candlesticks per constituent from Kalshi; mid per hour =
  `(yes_bid.close_dollars + yes_ask.close_dollars) / 2`.
- CRITICAL: forward-fill every ticker to a common hourly grid, then
  restrict to hours where ALL constituents have a value (uneven
  coverage: NC can print ~4 candles in 10 days vs MI ~105). Without
  this, early hours produce a wildly wrong portfolio value.
- Portfolio value = `sum(contracts_i * mid_i)`; index level =
  `100 * (0.50 + sum(weight_i * mid_i))`; rebase both `(v/v0 - 1) * 100`.
- Style: title `GOVBGD direct vs index`, y `change from start, %`,
  source exactly `Source: Adjacent`, black line direct + sky `#6fb7e0`
  index, endpoint labels bold mono `+/-X.X%`, legend above plot.
- Read: the gap between endpoints is the story.

---

## 7. Data sources + quirks

- Index price history: `mcp-cli.py price <index_id> <timeframe> --raw`
  (routes to `/api/v1/indices/{id}/prices` - 404s for market ids).
  Response shape `points[]` with `{timestamp, price, ohlc}`.
- Market price history: `mcp-cli.py price --type market "<market_id>"
  <timeframe> --raw` where `market_id` is the FULL `kalshi:...` string
  from `composition.attribution[].market_id` (bare `display_ticker`
  404s). THIN-MARKET QUIRK: the endpoint IGNORES timeframe and returns
  FULL history; thinly-traded markets print few points a day, so a
  COUNT slice still spans months. Filter by DATE, then collapse to
  daily close (last print per day).
- Index levels / attribution: `mcp-cli.py get --type index <id>`.
  `composition.attribution[]` carries `display_ticker`, `market_id`,
  `price` (mid), `weight` (fraction), `contribution` (fraction, x100
  for pts). `state_exposure[]` carries `state_code`, `weight`
  (fraction, x100), `probability` (ALREADY percent units).
- TR indices (`red_tr` / `blue_tr`) are NOT on the prod MCP (404 "Index
  not found"). They live on the dev REST API. The dev key is the
  `ak_...` from `config.yaml` for `mcp.dev.adjacent.markets`; use the
  lowercase `api_key` query param, NOT an `apiKey=` header (403 on the
  dev host via the `_http.get()` helper). The `period` param is IGNORED
  - returns ~100pt full history; slice `pts[-7:]` for 7d windows.
- News feed (LIVE): prod MCP `list(type=news)` returns up to 100 items,
  20/page. `news-latest.py --normalize` maps to
  `{market_id, published_at, headline}`. Broad global stream - filter
  for market relevance and whitelist sources at delivery. Dedup by
  title (ANSA re-publishes 3-4x). An hourly news-watch cron exists.
- Equity/ETF daily bars: Robinhood MCP
  (`get_equity_historicals`, symbols + start_time, interval="day").
  Bars carry `interpolated`; drop `interpolated:true` rows (gap-fill
  placeholders). Crypto is NOT on the Robinhood MCP (stocks/ETFs only)
  - use CoinGecko `market_chart` for BTC, then forward-fill missing
  days with last close. NEVER hardcode fallback data arrays - fetch
  live or fail loudly.
- Correlation thresholds: 2% daily index move triggers a scan, 5%
  news-correlation for tweet-worthy events (see the
  `adjacent-index-movers` and `adjacent-news-correlation` skills).

---

## 8. Running chart scripts + cron delivery

- Guard quirk (production host): the terminal lifecycle guard crashes
  with "embedded null character in path" when a command references an
  absolute venv binary or `python -c` heredocs. Reliable invocations
  use a `PATH` prefix or plain `python3 script.py` from the scripts
  directory. (Deployment example from `/opt/data`; not relevant to the
  repository test suite, which runs under system `python3`.)
- `execute_code` runs in a sandbox WITHOUT matplotlib - chart scripts
  must go through a terminal.
- Cron: the `script` parameter takes a bare filename relative to the
  host scripts dir (absolute paths rejected) - keep the real script in
  the scripts directory and symlink if the host expects a different
  location. `schedule: "30m"` creates a ONE-SHOT job; use
  `"every 30m"` / `"every 1h"` and confirm repeat: forever. A cron
  `.py` that runs under system python3 (no matplotlib) should be
  wrapped in a `.sh` calling the venv python.
- Cron prompts are self-contained: the script prints `CHART=` /
  `CAPTION=` lines, the agent delivers `MEDIA:` + a short caption per
  the style rules.
- Deliver ONE image per message on Telegram (multiple `MEDIA:` lines in
  one reply do not reliably render).

---

## 9. Reference script inventory

Chart producers in this repository (under `scripts/` unless noted):

- `adjacent_chart_style.py` - canonical helper
- `chart-index.py` - index chart producer
- `candles-chart.py` - candle charts (Heikin-Ashi via the helper)
- `chart-build.py` - chart build entry point
- `news-latest.py`, `news-correlation.py` - news fetch + correlation
- `portfolio-snapshot.py`, `rebalance-index.py` - direct index ops
- `snapshot-health.py`, `capability-status.py`, `correlation-regime.py`
  - monitoring
- `mcp-cli.py`, `_mcp.py`, `_http.py`, `_paths.py`, `_datawrapper.py` -
  shared plugin infra
- `datawrapper-create.py`, `datawrapper-publish.py`,
  `datawrapper-index.py`, `verify_dw_chart.py`, `check_dw_chart.py` -
  Datawrapper pipeline
- `tracking-index.py`, `table-tracking.py` - tracking charts + tables

Production-only reference scripts (kept on the `/opt/data` host, not
part of this repository): the broader batch / battleground / DSA /
TKNZ / GOVBGD-direct / pulse / surface-watch producers. They are
deployment examples and are not proof that a producer follows the
style contract; add a focused producer test when a specific chart type
is promoted to the approved set.

---

## 10. Workflow (regeneration gate)

When asked to recreate or resend charts, REGENERATE from the producing
scripts - never deliver existing PNGs (they may predate the canonical
helper: legacy palette, inline legends, centered titles, direct
`fig.savefig`, qualified source text).

1. Pull live data through the plugin MCP (`mcp-cli.py` / tools).
2. Brand via `apply_adjacent_theme()` from the canonical helper.
3. Inspect the producer script for legacy palettes, direct
   `fig.savefig()`, in-plot legends, centered titles, qualified source
   text. Replace with canonical tokens, `swatch_legend` / labels, left
   titles, `adj.save()`.
4. Render the PNG, verify the palette, beige canvas, left title, source
   line, axes, dates, and label contrast. Pitfall: vision misreads
   `%b %y` month ticks as day-of-month - verify against raw timestamps
   before "fixing" phantom anomalies.
5. Fix, re-render, re-verify. Never leave black value labels on dark
   bars.
6. Deliver via `MEDIA:` with a 3-5 line read. ONE image per message.
7. "send me more charts" requests: render a batch of 2-4 DISTINCT
   approved types from live data, QA each, deliver one image per
   message with a 3-5 line read naming the type and one takeaway.
