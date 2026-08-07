---
name: adjacent-chart-style
description: Adjacent chart branding spec - palette, type, grid, accents, and source line for every chart this plugin produces (Seaborn, matplotlib, Plotly, Datawrapper). Mirrors the Adjacent Design System tokens. Apply before any chart is rendered or published.
version: 1.1.0
category: data-science
allowed-tools:
  - Bash
---

# Adjacent chart style

Every chart this plugin produces must look like Adjacent, not like a
stock library default. This skill is the canonical spec, derived from
the Adjacent Design System (`design-system/src/tokens.css` and the
`Chart`, `ChartRenderer`, `TradingViewChart`, and `FullscreenChart`
components in Storybook). Load it before rendering or publishing any
chart.

The reusable Python helper lives at
`<plugin-root>/scripts/adjacent_chart_style.py`. It carries the
palette, the matplotlib/seaborn theme, the Plotly template, and the
source-line stamper. Prefer it over re-deriving values by hand.

## Source of truth and precedence

1. The executable behavior and public exports in
   `scripts/adjacent_chart_style.py` - the canonical helper.
2. `AGENTS.md` (writing rules + safety).
3. This skill and its peer host chart-style skill copies, plus
   `docs/charting-plugin-update.md`.
4. Individual producer scripts.

Do not inline the helper source, palette values, or API into this
skill, and do not fork the helper API in a host package. Reference the
helper by its repository-relative path
(`scripts/adjacent_chart_style.py`); an installed runtime path may be
mentioned as an example but must not be the only path. The palette and
series cycle below mirror the helper - if they disagree, the helper
wins, and this skill, `AGENTS.md`, the other two host copies, and
`tests/test_chart_style_contract.py` must be updated together.

Resolved rules (do not change without updating the helper first):

- `SOURCE_DEFAULT` is `Adjacent`; rendered source credits append a UTC
  timestamp in `YYYY-MM-DD HH:MM UTC` format. No basis clause, wordmark,
  or divider.
- The `SERIES` cycle is deep green, salmon, sky, mustard, sage, pink.
- A lone series uses deep forest green; color distinguishes categories or
  signs, never a lone line by direction.
- No x-axis title is required when the deck or chart context already
  communicates the unit.
- Bar value labels sit outside the bar by default, with an explicit
  exception for sufficiently large stacked segments.
- `adj.bar_labels(ax, bars, values, fmt, color=...)` takes **no**
  `fontsize` kwarg - sizing is fixed in the helper. Use
  `ax.tick_params(...)` or manual `ax.text(...)` when label size must
  change.
- Charts are often read on a phone (narrow chat width). More than about
  six categories on a vertical bar chart is unreadable when downscaled.
  Prefer horizontal bars (`ax.barh`) with full labels, larger figsize,
  and a text bullet fallback when the image alone cannot carry the
  numbers.
- Fonts are Inter (main), the `--font-serif` stack for decks, and IBM Plex
  Mono for ticks and data values.
- Candles are Heikin-Ashi only, never raw candlesticks.
- All pricing is mid-quote; `%` never `pp`; no em-dash, no emoji.

## The one-line rule

An Adjacent chart is an editorial graphic, not a plot. It leads with a
sentence that states the finding, carries the Adjacent surface and
palette, and credits the source bottom-left (`Source: Adjacent`). If it
reads as a library default - centered label-style title, boxed legend,
grid on every axis, unit repeated down the y axis - it is wrong.

## Structure

Every chart is the same four bands, top to bottom. `adj.figure()`
declares them and `adj.save()` reserves the room and draws them, so
nothing is ever hand-placed:

| Band | Type | Content |
| --- | --- | --- |
| headline | Inter bold, 16pt, `ink` | the finding as a sentence, sentence case, wraps |
| deck | serif, 11pt, `fg-2` | the series identifier, usually one word: `RED` |
| plot | - | the data |
| source | Inter 8.5pt, `fg-3` | `Source: Adjacent YYYY-MM-DD HH:MM UTC`, bottom-left, no rule |

**Two lines of text, and nothing else.** Anything a reader can infer
from the axes stays off the chart: the timeframe, the pricing basis,
the word "index", a desk kicker, a wordmark. A deck reading
`RED · index membership, 1-hour mid` should read `RED`.

The headline is the single most important brand decision. Write what
the data shows, not what the chart contains:

- Yes: `Two headlines account for the whole 5.7% move`
- No: `RED index, 30 days`

```python
fig, ax = adj.figure(
    headline="Political futures index closed the week at a 30-day high",
    deck="UPFI",
)
adj.area_series(ax, xs, ys)
adj.y_axis(ax, "level")
adj.last_value(ax, xs[-1], ys[-1], "105.4")
adj.format_date_axis(ax)
adj.save(fig, "upfi.png")
```

## Attribution

One credit, bottom-left, and nothing else: `Source: Adjacent`.

No wordmark beside it - `Source: Adjacent` already says who made it,
and printing `ADJACENT` next to it says the same thing twice. No
divider rule above it - that is a line the eye has to cross for
nothing. No basis clause: `Adjacent, mid-quote` reads as a two-part
publisher name, and the pricing basis is not a source. State the basis
in the prose beside the chart if it matters.

For another dataset use `Source: <publisher>`. `save()` stamps it
automatically; `source_line(fig, text)` overrides it.

## One surface

The plot area is the same beige as the page. No box, no white panel, no
border around the data. A lighter rectangle behind a chart is a second
background competing with the first, and it makes the graphic look like
a screenshot pasted into the page rather than part of it. The
horizontal gridlines and the x baseline are the whole frame.

## Axes

- Horizontal gridlines only, dotted, behind the data. No vertical grid.
- No left spine, no y tick marks. The x baseline is a solid rule with
  small outward tick marks.
- At most five gridlines. A dense axis reads as a spreadsheet.
- **Unit on the top tick only.** `adj.y_axis(ax, kind)` prints `7.5%`
  or `$1.2M` on the topmost tick and leaves the rest bare, so the axis
  reads as a column of numbers. `kind` is `percent` (values are 0-1
  fractions), `currency`, `number`, or `level`.
- No y-axis title when the deck already states the unit. `Rebased
  level` above `100 / 105 / 110` is redundant.
- `adj.format_date_axis(ax)` for any datetime x axis: concise labels,
  mono, horizontal, and a hard cap on tick count. It suppresses
  matplotlib's floating offset date (`2026-Aug-02` parked at the right
  of the axis) - that is a stray label outside the chart with nothing
  anchoring it. If the year matters, put it in the deck.

## Labelling the data

**Prefer a legend.** `adj.swatch_legend(fig, [(label, color), ...])`
puts filled squares under the deck, in the header where the reader
already is. It never covers data and it cannot be clipped.

`adj.series_label(ax, x_last, y_last, "Direct", color)` writes the name
on the line's right end. Use it when a legend would be ambiguous -
lines that cross repeatedly, or one series that needs calling out. A
matplotlib legend inside the plot is a last resort; it covers data.

Value callouts:

- `adj.last_value(ax, x, y, "96.35")` - the closing number in a filled
  square pill at the right edge with a dotted reference line across the
  plot. This is the product's index-chart signature.
- `adj.end_label(...)` for a plain endpoint callout with no pill.
- `adj.bar_labels(ax, bars, values, fmt, color=None)` - values on the
  bars so the axis can stay sparse. Handles negative bars.

### API pitfall: `bar_labels()` has no `fontsize`

Signature is fixed in the helper:

```python
adj.bar_labels(ax, bars, values, fmt=str, *, color=None)
```

Passing `fontsize=...` raises `TypeError`. Do not fork the helper to
accept it. When tick or category labels need to be larger (especially
for phone delivery):

- Category / axis ticks: `ax.tick_params(axis="y", labelsize=12)` (or
  `"x"` for vertical bars)
- One-off value labels: `ax.text(...)` with `fontsize=12` and
  `fontdict={"family": adj.FONTS["mono"][0]}` (or the mono stack)
- Keep `adj.bar_labels(...)` for the default mono end labels when the
  fixed 9pt size is fine

## Phone readability (chat / Telegram width)

Many charts land in narrow chat clients. Design for ~phone width, not a
desktop plot window.

- **Vertical bar charts with more than about six categories** become
  unreadable when downscaled. Prefer `ax.barh` so category names stay
  full-width and horizontal.
- **Labels:** write the full readable form (`at least 8%`, not `>=8%` or
  a truncated tick). Prefer fonts at least **12pt** for category and
  value text on multi-category bars.
- **Figure size:** for multi-category horizontal bars use roughly
  `figsize=(10, 7)` (or taller as categories grow). The house default
  `(7.6, 4.6)` is for line / area charts, not dense category ladders.
- **Template:** horizontal bars, large labels, brand palette - the
  tariff / probability ladder style. That is the bar default going
  forward when the chart is a ranked list of levels.
- **Text fallback:** if the image is still hard to read, ship the
  numbers as ASCII bullets **alongside** the image. Never make the PNG
  the only carrier of the values.

```python
# Multi-category ladder (phone-safe)
fig, ax = adj.figure(
    headline="Tariff outcomes still cluster below 20%",
    deck="KALSHI",
    figsize=(10, 7),
)
bars = ax.barh(labels, mids, color=adj.SERIES[0])
ax.tick_params(axis="y", labelsize=12)
adj.bar_labels(ax, bars, mids, fmt=lambda v: f"{100 * v:.1f}%")
adj.save(fig, "ladder.png")
# Also print a bullet list of the same numbers in the message body.
```

## Events

Mark a dated event with a full-height vertical rule and a bold label at
the top:

```python
adj.event_markers(ax, [
    (t_vote, "Cloture vote fails", level_at_vote),
    (t_call, "Runoff called", level_at_call),
])
```

The rule is a solid ink line across the plot and the label is bold ink,
wrapped short. An event is part of the story, so it is not whispered in
the meta tier. Pass a third value per event to also drop a filled dot
on the series where the event landed. On a dense chart pass
`rule=False` for a short tick at the baseline instead of a line through
the data.

## Chart forms

| Form | When | How |
| --- | --- | --- |
| area | one index or price series | `adj.area_series(...)` (default deep green) |
| line | two or three series compared | `ax.plot` + `adj.series_label` or `adj.swatch_legend` |
| step | changes only at discrete events | `ax.plot(..., drawstyle="steps-post")` |
| diverging bars | movers scans, gain/loss (few categories) | `ax.bar` with `UP`/`DOWN` + `adj.bar_labels` |
| horizontal ladder | ranked levels, many categories, chat delivery | `ax.barh` + large y labels + text bullet fallback |
| small multiples | four or more series, shared scale | `adj.figure(panels=(2, 2))` + `adj.small_multiples` |
| heikin-ashi | OHLC price path | `adj.heikin_ashi(...)` only - never raw candles |
| stacked area | composition over time | `adj.stacked_area` |
| waterfall | sequential signed contributions | `adj.waterfall` |
| waffle | composition shares (no pies) | `adj.waffle` |
| range dumbbell | low/high per category | `adj.range_dumbbell` |
| heatmap row | correlation / contribution strip | `adj.heatmap_row` |
| radar | multi-metric profile on polar axes | `adj.radar` |
| quote board | small set of mids and moves | `adj.quote_board` |
| prob stack | mutually exclusive outcomes | `adj.prob_stack` |

Never a pie chart, a dual y axis, a raw candlestick, or a 3D anything.

## Heikin-Ashi (house candle)

Heikin-Ashi is the only candle type this plugin draws. Transform OHLC first:

- HA-close = (O + H + L + C) / 4
- HA-open = (prev HA-open + prev HA-close) / 2; first bar uses (O + C) / 2
- HA-high = max(H, HA-open, HA-close)
- HA-low = min(L, HA-open, HA-close)

Render with `adj.heikin_ashi(ax, x, opens, highs, lows, closes)`:

- bullish: hollow beige body, ink edge
- bearish: solid charcoal body
- thin ink wicks, graph-paper grid, y axis on the right with arrowheads

Never plot raw candlesticks.

## Palette (canonical hex)

These mirror `--comp-*` tokens exactly. Never hand-pick a divergent
hex; if you need a new color, reach for another token from this table.

| Role | Token | Hex | Use |
| --- | --- | --- | --- |
| canvas | `--comp-canvas` | `#ece9e2` | figure / page background |
| paper | `--comp-paper` | `#ffffff` | non-plot panels only (axes use canvas) |
| ink | `--comp-ink` | `#0a0f0d` | title, axis labels, primary text |
| deep | `--comp-deep` | `#0e2a1f` | dark header surfaces, deep-tone charts |
| green | `--comp-green` | `#3fae5a` | primary accent, positive series |
| green-2 | `--comp-green-2` | `#22c55e` | hover / brighter accent |
| salmon | `--comp-salmon` | `#e66b55` | negative series, down tick |
| sky | `--comp-sky` | `#6fb7e0` | series 3 |
| mustard | `--comp-mustard` | `#d89a3f` | series 4 |
| sage | `--comp-sage` | `#a8c49a` | muted positive, series 5 |
| pink | `--comp-pink` | `#f0a8c8` | series 6 |
| green-deep | Chart accent | `#0e6b3a` | featured / hero single-series accent |
| deep-down | chart down color | `#9b3a2e` | down trend line / area |
| rule | `--comp-rule` | `#d6d2c8` | hairline, axis edge, borders |
| grid | `--comp-grid` | `#ecebea` | dotted gridline |
| fg-2 | `--fg-2` | `#5c5a53` | secondary text, legend |
| fg-3 | `--fg-3` | `#7f7d7a` | meta, source credit |
| up | `--paper-up` | `#2a6a3a` | readable positive tick text |
| down | `--paper-down` | `#9b3a2e` | readable negative tick text |

## Categorical series cycle

For multi-series charts, draw series in this exact order so the brand
reads the same as the product charts:

`deep` `#0e2a1f`, `salmon` `#e66b55`, `sky` `#6fb7e0`, `mustard` `#d89a3f`,
then `sage` and `pink` for the 5th / 6th series. The
helper exposes it as `adj.SERIES` and sets it as the matplotlib
`axes.prop_cycle`, so `ax.plot(...)` picks it up with no color argument.

For a single-series chart use one accent, not the cycle:
`adj.ACCENT` (`#0e2a1f`) normally, `adj.ACCENT_DEEP` (`#1d4a38`) for a
featured or hero chart.

## Directional color

**A single line is deep forest green.** `adj.LINE` (`#0e2a1f`) is the
default for `area_series` and for any lone series. Do not color a line green
because it rose or red because it fell - a lone line carries no
categorical meaning, so the color is decoration that reads as a signal.
The same applies to every panel of a small-multiple grid.

Color enters only where it distinguishes categories: two or more series
on one axis take `adj.SERIES` in order.

Directional color is for marks where the sign is the category - gain
and loss bars, up and down badges:

- up / positive: `adj.UP` = deep green (`#0e2a1f`).
- down / negative: `adj.DOWN` = `deep-down` (`#9b3a2e`).
- `adj.SALMON` (`#e66b55`) is the semantic negative for badges.

`adj.ACCENT` / `adj.ACCENT_DEEP` (green) are for a chart that is
deliberately featured - a hero graphic or a product surface - never to
signal direction. Never use generic `red`/`green` from a library
default.

## Typography

Three stacks, mirroring the design-system tokens exactly. Inter is used
for headlines and IBM Plex Mono for data values. Do not substitute a
different mono face - the chart would stop matching the pulse treatment.

| Token | Stack | Use in chart |
| --- | --- | --- |
| `--font-main` | Inter, Helvetica Neue, Helvetica, Arial, sans-serif | headline, axis titles, legend, source credit |
| `--font-serif` | Times New Roman, Times, DejaVu Serif, serif | the deck under the headline |
| `--font-mono` | IBM Plex Mono, SF Mono, Menlo, Courier New, monospace | tick labels, data values, any tabular numeric |

Never name a font directly in chart code; use `adj.FONTS["main"]`,
`["serif"]`, `["mono"]`.

Conventions:

- Headline: Inter, bold, left-aligned, `--comp-ink`. No em-dash, no emoji.
- Deck: serif, regular, `--fg-2`. The identifier, usually one word.
- Tick labels + data callouts: mono, tabular, `--comp-ink`.
- Source credit: Inter, 8.5px, `--fg-3`, bottom-left of the figure.

## Layout + grid

- Square corners everywhere. `--radius: 0`; no rounded bars or patches.
- Figure and plot area are both `--comp-canvas` (beige). Always.
- Grid: dotted, 0.7px, `--comp-rule`, behind the data, horizontal only.
- Legend: no frame, `--fg-2` text, Inter - and prefer not to need one.

## Number formatting

Axis ticks and stated values follow different rules. Ticks stay as
narrow as possible; stated values keep their precision.

- **Axis ticks**: `adj.y_axis(ax, kind)`. Trailing zeros trimmed, unit
  on the top tick only: `7.5%`, `5`, `2.5`, `0`.
- **Stated values** (callouts, pills, prose, tables): two decimals with
  the unit - `+5.73%`, `$1.2M`, `96.35`. Never `pp`.
- Percent inputs are 0-1 fractions everywhere. `0.0573` is 5.73%.
- Currency: `$100`, `$1.2M`, `$1.2B`. Counts: `1.2k`, `1.2M`, `1.2B`.
- Dates: `YYYY-MM-DD`. Decimals: `0.012` not `.012`.
- All pricing is mid-quote (see the `adjacent-markets` skill).

`percent_formatter()`, `currency_formatter()`, and `number_formatter()`
remain for a tick axis that needs the unit on every label.

## Signature area chart

The house look for a single index or price series is a solid deep-green
line over a vertical gradient that fades to transparent at the
baseline - the `TradingViewChart` look. `adj.area_series(ax, x, y)`
draws the line, clips the gradient to the series, anchors the y axis to
the baseline, and leaves headroom above the peak so a callout lands
inside the plot. Pass `baseline=` when the series does not cross zero
and the fill should start somewhere other than the series minimum.
Leave `color` alone unless the chart is a deliberate hero.

## Seaborn + matplotlib

The `/charts/datawrapper-publish` command falls back to Seaborn when
`DATAWRAPPER_API_KEY` is unset. Open the figure with `adj.figure()` and
pass the axis to Seaborn - the theme is already applied:

```python
import sys
sys.path.insert(0, "<plugin-root>/scripts")
import matplotlib
matplotlib.use("Agg")
import seaborn as sns
import adjacent_chart_style as adj

fig, ax = adj.figure(
    headline="The direct index tracked 25bp behind the benchmark",
    deck="GOVBGD",
)
sns.lineplot(data=df, x="ts", y="index", ax=ax, color=adj.SERIES[0])
sns.lineplot(data=df, x="ts", y="portfolio", ax=ax, color=adj.SERIES[1])
adj.swatch_legend(fig, [("Index", adj.SERIES[0]), ("Direct", adj.SERIES[1])])
adj.y_axis(ax, "percent")
adj.format_date_axis(ax)
adj.save(fig, "out.png")
```

Rules:

- Never pass a library-default palette (`sns.color_palette("muted")`,
  `viridis`, `tab10`). Use `adj.SERIES`, `adj.UP`, `adj.DOWN`, or a
  token from `adj.PALETTE`.
- Never call `plt.style.use(...)`. The helper owns the style.
- Never call `fig.savefig` directly, and never
  `bbox_inches="tight"` - it crops away the reserved chrome bands.

## Spacing (do not hand-place text)

Spacing is what most often breaks the brand. The helper owns it:

- Declare the header in `adj.figure()` and let `adj.save()` place it.
  A hand-placed `fig.text` header gets no reserved room and will land
  on the data. `adj.title_block(ax, title, deck)` does the same thing
  for a figure you built with plain `plt.subplots()`.
- `adj.save()` also draws the footer. Do not add your own source text.
- `adj.last_value()` and `adj.series_label()` reserve their own room on
  the right, so they are never clipped.
- `adj.format_date_axis(ax)` for any datetime x axis. It caps the tick
  count for real (the locator otherwise overshoots), uses concise
  labels with the shared date in an offset, and keeps them horizontal
  and mono. Pass `rotation=30` only for long labels.
- `figsize=(7.6, 4.6)` is the house default for line / area charts;
  `(7.6, 5.0)` for a 2x2 panel grid; about `(10, 7)` for multi-category
  horizontal bar ladders aimed at phone width.

## Plotly

For Plotly figures, build the layout from the template:

```python
import plotly.graph_objects as go
import adjacent_chart_style as adj
fig = go.Figure(layout=adj.plotly_template())
```

The template sets the beige canvas, mono ticks, `colorway` to the
Adjacent series cycle, and the source annotation. The matplotlib path
is preferred for anything published.

## Datawrapper

Datawrapper charts are styled through the API, not Python. Apply the
same brand in the metadata PATCH:

- `theme`: light, base color `#0a0f0d`, background `#ece9e2`.
- Title font: Inter; data labels: the `--font-mono` generic.
- Axis and grid lines: `#d6d2c8` / `#ecebea`.
- Series colors: the `SERIES` hex list above.
- Headline: the finding as a sentence. Identifier goes in the intro.
- Source line: `Source: Adjacent`. No wordmark, no basis clause.
- Number format: `0.00%` for percent series; `$` prefix for currency.
- No emojis, no `pp`, no em-dash in title or intro. The `conventions`
  hook enforces this on the metadata payload.

## What this skill does NOT allow

- Hardcoded hex outside the palette table (a clear divergence signal;
  the `chart-style` hook blocks it on Write/Edit).
- Library default palettes (`viridis`, `tab10`, `muted`, `Set2`).
- Rounded chart elements. `--radius: 0`.
- Em-dash, unicode bullet, emoji, or `pp` in any chart text (also
  enforced by the `conventions` hook).
- A chart without a source line when it is being published or shown to
  a user.
- A label-style headline (`RED index, 30 days`) where the finding
  belongs. The identifier goes in the deck.
- Vertical gridlines, a left spine, a dual y axis, a pie chart, or the
  unit repeated on every y tick.
- A wordmark, a footer divider rule, or a basis clause in the source.
- A white panel or any plot background other than the beige canvas.
- The floating offset date beside the x axis.
- A lone line colored by direction. Deep green unless it is a hero.
- `adj.bar_labels(..., fontsize=...)` - that kwarg does not exist.
- A dense vertical bar chart (>~6 categories) shipped as the only
  carrier of the numbers in a phone-width chat.
