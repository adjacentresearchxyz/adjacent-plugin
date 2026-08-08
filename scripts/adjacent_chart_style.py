#!/usr/bin/env python3
"""Adjacent chart style - build every Python chart as an Adjacent graphic.

Carries the Adjacent Design System token palette (canonical source:
design-system/src/tokens.css) and the house editorial layout, so that
any chart from this plugin - matplotlib, Seaborn, Plotly export - reads
like an Adjacent graphic rather than a library default: beige canvas,
near-black ink, deep-green accent, mono tick labels, horizontal dotted
grid, and a headline that states the finding.

Open the figure with figure(), plot, then save():

    import adjacent_chart_style as adj

    fig, ax = adj.figure(
        headline="Political futures index closed at a 30-day high",
        deck="UPFI",
    )
    adj.area_series(ax, xs, ys)
    adj.y_axis(ax, "level")
    adj.last_value(ax, xs[-1], ys[-1], "105.4")
    adj.save(fig, "out.png")

save() reserves the header and footer bands, positions the axes in what
is left, and draws the chrome - so headlines never sit on the data and
the source never collides with the tick labels.

This module is intentionally dependency-light: matplotlib is required
only when a drawing function is called. The PALETTE dict is always
available with no imports.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# -------------------------------------------------------------------
# Palette - mirrors design-system/src/tokens.css (Composer family).
# Keep in sync with the design system; never hand-pick divergent hex.
# -------------------------------------------------------------------

PALETTE: dict[str, str] = {
    # surfaces
    "canvas": "#ece9e2",   # beige page background (--comp-canvas)
    "paper": "#ffffff",    # white panel / axes face (--comp-paper)
    "deep": "#0e2a1f",     # deep forest green, header surfaces (--comp-deep)
    "deep-2": "#1d4a38",
    "deep-3": "#35634f",
    "deep-4": "#5a826f",
    "deep-5": "#7f9f88",
    "deep-6": "#a8c49a",
    # ink + text tiers
    "ink": "#0a0f0d",      # primary text / title (--comp-ink, --fg-1)
    "fg-2": "#5c5a53",     # secondary text (--fg-2)
    "fg-3": "#7f7d7a",     # meta / source credit (--fg-3)
    "on-deep": "#ffffff",  # text on deep (--fg-on-deep)
    # accents
    "green": "#3fae5a",    # primary accent / positive (--comp-green)
    "green-2": "#22c55e",  # brighter hover green (--comp-green-2)
    "green-deep": "#0e6b3a",  # deep accent for featured/hero charts (Chart, TradingViewChart)
    "salmon": "#e66b55",   # semantic negative / error badge (--comp-salmon)
    "sky": "#6fb7e0",      # sky token (--comp-sky), info badge
    "mustard": "#d89a3f",  # mustard token (--comp-mustard), warning badge
    "sage": "#a8c49a",     # muted positive (--comp-sage), success badge
    "pink": "#f0a8c8",     # pink token (--comp-pink)
    # chart-component series palette (ChartRenderer default cycle in Storybook)
    "chart-green": "#3fae5a",
    "chart-orange": "#e87d2a",
    "chart-blue": "#4a90d9",
    "chart-purple": "#b85cce",
    # directional red for trend/area charts (TradingViewChart down accent)
    "trend-down": "#c0392b",
    # rules + grid
    "rule": "#d6d2c8",     # hairline / axis edge (--comp-rule)
    "hover": "#f6f5f1",    # row hover fill (--comp-hover)
    "grid": "#ecebea",     # dotted gridline (--comp-grid)
    # readable tick colors on light canvas (paper family)
    "up": "#2a6a3a",       # positive tick text (--paper-up)
    "down": "#9b3a2e",     # negative tick text (--paper-down)
    "deep-down": "#9b3a2e",
}

# Categorical series cycle. This mirrors the ChartRenderer default cycle
# shipped in the Adjacent design-system Storybook (green, orange, blue,
# purple), then falls back to on-brand tokens (sage, pink) for the rare
# 5th / 6th series. Draw series in this exact order so multi-series
# charts read the same as the product charts.
SERIES: list[str] = [
    PALETTE["deep"],
    PALETTE["salmon"],
    PALETTE["sky"],
    PALETTE["mustard"],
    PALETTE["deep-6"],
    PALETTE["pink"],
]

# Single-series line color. Off-black by default: a lone line carries no
# categorical meaning, so coloring it green because it happens to rise is
# decoration that misreads as a signal. ACCENT / ACCENT_DEEP stay available
# for a deliberately featured chart (the Chart and TradingViewChart
# green-accent stories).
LINE: str = PALETTE["deep"]
ACCENT: str = PALETTE["deep"]
ACCENT_DEEP: str = PALETTE["deep-2"]

# Financial direction colors for trend / area / gain-loss charts. UP is
# the accent green; DOWN is the TradingViewChart down-red. SALMON stays
# the semantic negative token for categorical bars and badges.
UP: str = PALETTE["deep"]
DOWN: str = PALETTE["deep-down"]
SALMON: str = PALETTE["salmon"]

# Fonts, mirroring the design-system tokens exactly. Inter is the only
# pinned face on adjacent.markets (--font-main); --font-mono and
# --font-serif are the CSS generics, so these stacks lead with what the
# generics actually resolve to rather than naming a face the site never
# loads. Do not substitute a "nicer" mono or serif here - the chart would
# stop matching the page.
FONTS: dict[str, list[str]] = {
    # --font-main: Inter, sans-serif
    "main": ["Inter", "Helvetica Neue", "Helvetica", "Arial", "sans-serif"],
    # --font-serif: serif
    "serif": ["Times New Roman", "Times", "DejaVu Serif", "serif"],
    # --font-mono: monospace
    "mono": ["IBM Plex Mono", "SF Mono", "Menlo", "Courier New", "monospace"],
}

SOURCE_DEFAULT = "Adjacent"


def _timestamped_source() -> str:
    return f"{SOURCE_DEFAULT} {datetime.now(timezone.utc):%Y-%m-%d %H:%M UTC}"

# Editorial layout metrics, in inches. The header stacks downward from the
# top of the figure (headline, deck, swatch legend); the footer is the
# source credit alone. save() reserves exactly this much room so nothing is
# ever hand-placed.
_MARGIN_X = 0.20        # left/right figure margin for header + footer text
_HEADER_TOP = 0.20      # space above the headline
_HEADLINE_H = 0.32      # per wrapped line
_DECK_H = 0.24          # per wrapped line
_LEGEND_H = 0.26        # per legend row
_HEADER_GAP = 0.18      # space between the header block and the plot
_FOOTER_H = 0.34        # source credit band


def _font_main() -> str:
    return ",".join(FONTS["main"])


def _font_serif() -> str:
    return ",".join(FONTS["serif"])


def _font_mono() -> str:
    return ",".join(FONTS["mono"])


def _bundled_fonts_dir() -> Path | None:
    """Resolve the bundled OFL font directory, or None when absent.

    The shared plugin-root resolver (``_paths.plugin_root``) is preferred:
    it honors ``ADJACENT_PLUGIN_ROOT`` - which a bundled host runtime may
    set to relocate the tree - and applies ``expanduser().resolve()``.
    This module stays dependency-light, so the import is lazy and
    optional; if ``_paths`` is not importable the env var is read
    directly. In all cases this file's own location
    (``scripts/../assets/fonts``) is the final fallback, so the fonts
    still resolve from a copied runtime that preserved the layout.
    """
    bases: list[Path] = []
    try:
        from _paths import plugin_root
    except ImportError:
        override = os.environ.get("ADJACENT_PLUGIN_ROOT")
        if override:
            bases.append(Path(override).expanduser().resolve())
    else:
        bases.append(plugin_root())
    bases.append(Path(__file__).resolve().parent.parent)
    for base in bases:
        candidate = base / "assets" / "fonts"
        if candidate.is_dir():
            return candidate
    return None


_fonts_registered = False


def _register_bundled_fonts() -> None:
    """Register the bundled OFL static TTFs (Inter, IBM Plex Mono).

    This is what makes chart output deterministic across machines: the
    exact faces the design system names ship with the plugin and are
    loaded into matplotlib's font manager before the rcParams request
    them, so renders do not fall through to Helvetica / DejaVu Sans on a
    host that happens to lack Inter installed system-wide.

    Registers once per process. ``fontManager`` is a process-wide
    singleton and ``addfont`` appends without deduplication and clears the
    findfont cache on every call, so re-registering on each
    ``apply_adjacent_theme`` (twice per chart, once in figure() and once
    in save()) would grow ttflist unboundedly and thrash the cache. The
    module-level guard is set on every exit path, including when the
    assets are absent, so the env/dir lookup does not repeat either.

    Fail-safe: a missing file or a font manager without ``addfont`` is
    skipped silently, so environments without the bundled assets still
    render through the font stacks. Never raises.
    """
    global _fonts_registered
    if _fonts_registered:
        return
    from matplotlib import font_manager

    directory = _bundled_fonts_dir()
    if directory is None:
        _fonts_registered = True
        return
    # The public API is the method on the fontManager singleton
    # (font_manager.fontManager.addfont); guard with getattr so an
    # unexpected font manager without it is skipped rather than raising.
    addfont = getattr(font_manager.fontManager, "addfont", None)
    if addfont is None:
        _fonts_registered = True
        return
    for name in (
        "Inter-Regular.ttf",
        "Inter-SemiBold.ttf",
        "Inter-Bold.ttf",
        "IBMPlexMono-Regular.ttf",
        "IBMPlexMono-Bold.ttf",
    ):
        path = directory / name
        try:
            if path.is_file():
                addfont(str(path))
        except Exception:
            pass
    _fonts_registered = True


def apply_adjacent_theme() -> None:
    """Configure matplotlib + seaborn rcParams to the Adjacent brand.

    Safe to call multiple times. Imports matplotlib lazily so the palette
    stays usable in environments without matplotlib.
    """
    import matplotlib as mpl
    from matplotlib import font_manager

    # Register the bundled OFL static TTFs before setting rcParams so
    # matplotlib resolves "Inter" / "IBM Plex Mono" to the vendored faces
    # rather than falling through the stack. No-op when the assets dir is
    # absent (e.g. a host without the bundled runtime).
    _register_bundled_fonts()

    try:
        import seaborn as sns  # noqa: F401
        _seaborn = sns
    except Exception:
        _seaborn = None

    main, serif, mono = _font_main(), _font_serif(), _font_mono()
    p = PALETTE

    rc: dict[str, Any] = {
        # figure / canvas. The plot area is the same beige as the page -
        # one surface, always. A chart never sits on its own panel.
        "figure.facecolor": p["canvas"],
        "savefig.facecolor": p["canvas"],
        "axes.facecolor": p["canvas"],
        # ink + text
        "text.color": p["ink"],
        "axes.labelcolor": p["ink"],
        "axes.titlecolor": p["ink"],
        # fonts
        "font.family": "sans-serif",
        "font.sans-serif": main.split(","),
        "font.serif": serif.split(","),
        "font.monospace": mono.split(","),
        "axes.titleweight": "bold",
        "axes.titlesize": 14,
        "axes.titlelocation": "left",
        "axes.labelsize": 11,
        "axes.labelweight": "regular",
        "xtick.labelsize": 10,
        "ytick.labelsize": 10,
        "font.size": 11,
        # Spines: only the x baseline survives. The y axis is carried by the
        # horizontal gridlines, so a left spine would just be noise (FT / WSJ).
        "axes.edgecolor": p["rule"],
        "axes.linewidth": 0.8,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.spines.left": False,
        # Horizontal gridlines only; never drawn over the data.
        "axes.grid": True,
        "axes.grid.axis": "y",
        "axes.axisbelow": True,
        "grid.color": p["grid"],
        "grid.linestyle": ":",
        "grid.linewidth": 0.7,
        "grid.alpha": 1.0,
        # Small outward tick marks on the x baseline, none on y.
        "xtick.direction": "out",
        "xtick.major.size": 4,
        "xtick.major.width": 0.8,
        "xtick.color": p["rule"],
        "xtick.labelcolor": p["ink"],
        "ytick.major.size": 0,
        "ytick.labelcolor": p["ink"],
        # square corners (Adjacent radius is 0)
        "patch.antialiased": True,
        "legend.frameon": False,
        "legend.fontsize": 10,
        # categorical cycle
        "axes.prop_cycle": mpl.cycler(color=SERIES),
        # tabular figures for numeric alignment where supported
        "axes.formatter.use_mathtext": False,
    }
    mpl.rcParams.update(rc)

    # Tick labels + data values run in the mono stack when available.
    for tick in ("xtick", "ytick"):
        mpl.rcParams[f"{tick}.labelsize"] = 10

    # Inter is the only face the site actually loads; probe it so matplotlib
    # picks it up when installed and falls through the stack when not.
    for name in ("Inter",):
        try:
            font_manager.findfont(name, fallback_to_default=True)
        except Exception:
            pass

    if _seaborn is not None:
        # Set a seaborn theme that inherits the rcParams above.
        _seaborn.set_theme(
            context="notebook",
            style={"axes.facecolor": p["canvas"], "figure.facecolor": p["canvas"]},
            palette=SERIES,
            rc=rc,
        )


def apply_adjacent_style() -> None:
    """Backward-compatible alias for apply_adjacent_theme()."""
    apply_adjacent_theme()


def _meta(fig) -> dict[str, Any]:
    """Return (creating if needed) the editorial metadata bag on a figure."""
    meta = getattr(fig, "_adjacent", None)
    if meta is None:
        meta = {
            "headline": None,
            "deck": None,
            "legend": [],
            "source": _timestamped_source(),
            # Inches to keep clear on the right for pills and series labels.
            "right_gutter": 0.0,
        }
        fig._adjacent = meta  # noqa: SLF001 - read back by save()
    return meta


def figure(
    *,
    headline: str | None = None,
    deck: str | None = None,
    source: str | None = None,
    figsize: tuple[float, float] = (7.6, 4.6),
    panels: tuple[int, int] | None = None,
):
    """Open a branded figure with the editorial header and footer declared.

    This is the entry point for every chart. The header (headline, deck,
    swatch legend) and the source credit are recorded here and rendered by
    save(), which reserves exactly the room they need. Nothing in the chrome
    is hand-placed, so the headline never collides with data and the source
    never collides with tick labels.

        fig, ax = adj.figure(
            headline="Republican index broke out after the Senate vote",
            deck="RED",
        )
        adj.area_series(ax, xs, ys)
        adj.save(fig, "red.png")

    Two lines of text and nothing else: the headline states the finding and
    the deck names the series. Anything a reader can infer from the axes -
    the timeframe, the pricing basis, the word "index" - stays off the
    chart.

    Pass ``panels=(rows, cols)`` for a small-multiple grid, which returns
    the axes array instead of one axis.
    """
    import matplotlib.pyplot as plt

    apply_adjacent_theme()
    if panels:
        fig, axes = plt.subplots(*panels, figsize=figsize, squeeze=False)
        targets = list(axes.flat)
    else:
        fig, ax = plt.subplots(figsize=figsize)
        axes, targets = ax, [ax]

    meta = _meta(fig)
    meta.update(headline=headline, deck=deck)
    if source is not None:
        meta["source"] = source
    for target in targets:
        frame(target)
    return fig, axes


def frame(ax) -> Any:
    """Set the plot surface: beige, seamless, carried by grid and baseline.

    There is one surface. The plot area is the same beige as the page, with
    no box, no panel, and no border around the data - a lighter rectangle
    behind a chart is a second background competing with the first. The
    horizontal gridlines and the x baseline are the whole frame.
    """
    from matplotlib.ticker import MaxNLocator

    p = PALETTE
    ax.set_facecolor(p["canvas"])
    ax.spines["bottom"].set_visible(True)
    ax.spines["bottom"].set_color(p["ink"])
    ax.spines["bottom"].set_linewidth(0.8)
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.grid(axis="y", visible=True, color=p["rule"])
    ax.grid(axis="x", visible=False)
    # Few gridlines. A dense axis reads as a spreadsheet, not a chart.
    ax.yaxis.set_major_locator(MaxNLocator(nbins=5, steps=[1, 2, 2.5, 5, 10]))
    ax.tick_params(axis="y", length=0)
    ax.tick_params(axis="x", length=4, width=0.8, color=p["rule"])
    return ax


def _trim_number(value: float, decimals: int | None = None) -> str:
    if decimals is not None:
        return f"{value:,.{decimals}f}"
    if abs(value - round(value)) < 1e-9:
        return f"{round(value):,d}"
    return f"{value:,.2f}".rstrip("0").rstrip(".")


def _compact_number(value: float, decimals: int | None = None) -> str:
    """Shared magnitude ladder for axis ticks (k / M / B)."""
    magnitude = abs(value)
    if magnitude >= 1_000_000_000:
        return f"{value / 1_000_000_000:.1f}B"
    if magnitude >= 1_000_000:
        return f"{value / 1_000_000:.1f}M"
    if magnitude >= 1_000:
        return f"{value / 1_000:.1f}k"
    return _trim_number(value, decimals)


def y_axis(
    ax,
    kind: str = "number",
    *,
    unit_on_top: bool = True,
    decimals: int | None = None,
) -> Any:
    """Format the y axis the editorial way: bare numbers, unit on the top tick.

    FT and WSJ print ``25%`` and ``$90`` on the topmost tick and leave the
    rest bare, so the axis reads as a column of numbers rather than a column
    of repeated units. ``kind`` is one of:

    - ``percent``  - values are 0-1 fractions, rendered ``25`` with ``%`` on top
    - ``currency`` - compacted to ``1.2M`` with ``$`` on the top tick
    - ``number``   - compacted to ``1.2k`` / ``1.2M`` / ``1.2B``
    - ``level``    - plain numbers, for rebased index levels

    Pass ``unit_on_top=False`` to suffix every tick instead, and ``decimals``
    to pin the precision (the default trims trailing zeros so the axis stays
    narrow). Stated values in callouts and prose keep full precision - this
    governs tick labels only.
    """
    from matplotlib.ticker import FuncFormatter

    if kind == "percent":
        body, unit, prefix = (lambda v: _trim_number(v * 100, decimals)), "%", False
    elif kind == "currency":
        body, unit, prefix = (lambda v: _compact_number(v, decimals)), "$", True
    elif kind == "number":
        body, unit, prefix = (lambda v: _compact_number(v, decimals)), "", False
    elif kind == "level":
        body, unit, prefix = (lambda v: _trim_number(v, decimals)), "", False
    else:
        raise ValueError(f"unknown y_axis kind: {kind!r}")

    def _fmt(value: float, _pos: int) -> str:
        text = body(value)
        if not unit:
            return text
        lo, hi = ax.get_ylim()
        visible = [t for t in ax.get_yticks() if lo <= t <= hi]
        on_top = bool(visible) and abs(value - max(visible)) < 1e-9
        if unit_on_top and not on_top:
            return text
        return f"{unit}{text}" if prefix else f"{text}{unit}"

    ax.yaxis.set_major_formatter(FuncFormatter(_fmt))
    return ax


def swatch_legend(fig, entries: list[tuple[str, str]]) -> Any:
    """Declare a swatch legend for the header band, above the plot.

    ``entries`` is a list of ``(label, color)`` pairs, rendered under the
    deck as filled squares with labels. This is the house way to name
    series: it sits in the header where the reader already is, it never
    covers data, and it cannot be clipped by the figure edge.
    """
    _meta(fig)["legend"] = list(entries)
    return fig


def series_label(ax, x, y, text: str, color: str, *, dx: int = 8, dy: int = 0) -> Any:
    """Name a line at its right end instead of in a legend.

    The fallback when a swatch legend would be ambiguous - lines that cross
    repeatedly, or a chart where one series needs calling out by name.
    Reach for ``swatch_legend()`` first. Reserves room on the right so the
    name is never clipped by the figure edge.
    """
    meta = _meta(ax.figure)
    meta["right_gutter"] = max(meta["right_gutter"], 0.16 * len(text) + 0.20)
    ax.annotate(
        text,
        xy=(x, y),
        xytext=(dx, dy),
        textcoords="offset points",
        color=color,
        fontsize=10,
        fontweight="bold",
        family=FONTS["main"],
        ha="left",
        va="center",
        clip_on=False,
        annotation_clip=False,
    )
    return ax


def last_value(
    ax,
    x,
    y,
    text: str,
    color: str | None = None,
    *,
    reference: bool = True,
) -> Any:
    """Stamp the closing value as a filled pill, with a dashed reference line.

    Mirrors the index chart on adjacent.markets: a dotted horizontal rule
    across the plot at the last value, and a square-cornered filled pill at
    the right edge carrying the number in white mono. Defaults to the line
    color so the pill reads as part of the series.
    """
    color = color or LINE
    meta = _meta(ax.figure)
    meta["right_gutter"] = max(meta["right_gutter"], 0.11 * len(text) + 0.30)
    if reference:
        ax.axhline(y, color=color, linestyle=":", linewidth=1.0, alpha=0.5, zorder=4)
    ax.annotate(
        text,
        xy=(x, y),
        xytext=(8, 0),
        textcoords="offset points",
        color=PALETTE["on-deep"],
        fontsize=10,
        fontweight="bold",
        family=FONTS["mono"],
        ha="left",
        va="center",
        clip_on=False,
        annotation_clip=False,
        bbox={
            "boxstyle": "square,pad=0.4",
            "facecolor": color,
            "edgecolor": "none",
        },
    )
    return ax


def event_markers(
    ax,
    events: list[tuple],
    *,
    rule: bool = True,
    wrap: int = 14,
) -> Any:
    """Mark dated events with a full-height rule and a bold label.

    ``events`` holds ``(x, label)`` pairs, or ``(x, label, y)`` to also drop
    a filled dot on the series where the event landed. The rule is a solid
    ink line across the plot and the label is bold ink at the top - an event
    is part of the story, not chart furniture, so it is not whispered in the
    meta tier.

    Pass ``rule=False`` on a dense chart to get a short tick at the baseline
    instead of a line through the data.
    """
    import textwrap

    for event in events:
        x, label = event[0], event[1]
        y = event[2] if len(event) > 2 else None
        if rule:
            ax.axvline(x, color=PALETTE["ink"], linewidth=0.9, zorder=4)
        else:
            ax.plot(
                [x],
                [0],
                marker="|",
                markersize=9,
                color=PALETTE["ink"],
                transform=ax.get_xaxis_transform(),
                clip_on=False,
                zorder=4,
            )
        if y is not None:
            ax.plot([x], [y], marker="o", markersize=5, color=PALETTE["ink"], zorder=5)
        ax.annotate(
            "\n".join(textwrap.wrap(label, wrap)),
            xy=(x, 1.0),
            xycoords=("data", "axes fraction"),
            xytext=(5, -3),
            textcoords="offset points",
            ha="left",
            va="top",
            fontsize=9,
            fontweight="bold",
            color=PALETTE["ink"],
            family=FONTS["main"],
        )
    return ax


def bar_labels(ax, bars, values, fmt=str, *, color: str | None = None) -> Any:
    """Print each bar's value at its end in mono, so the axis can stay sparse."""
    color = color or PALETTE["fg-2"]
    for bar, value in zip(bars, values):
        # A negative bar's rectangle can be stored either way round, so take
        # the extremes rather than trusting get_y() to be the far edge - that
        # is what put the label inside the bar, unreadable against the fill.
        edges = (bar.get_y(), bar.get_y() + bar.get_height())
        below = value < 0
        ax.annotate(
            fmt(value),
            xy=(bar.get_x() + bar.get_width() / 2, min(edges) if below else max(edges)),
            xytext=(0, -6 if below else 6),
            textcoords="offset points",
            ha="center",
            va="top" if below else "bottom",
            fontsize=9,
            color=color,
            family=FONTS["mono"],
        )
    # Open up the ends so the labels sit inside the axes rather than in the
    # tick-label band below or the headline band above.
    lo, hi = ax.get_ylim()
    span = hi - lo
    ax.set_ylim(
        lo - span * 0.10 if any(v < 0 for v in values) else lo,
        hi + span * 0.08 if any(v >= 0 for v in values) else hi,
    )
    return ax


def percent_formatter():
    """Return a matplotlib FuncFormatter that renders 0-1 fractions as 0.00%."""
    from matplotlib.ticker import FuncFormatter

    return FuncFormatter(lambda value, _pos: f"{value * 100:.2f}%")


def currency_formatter():
    """Return a matplotlib FuncFormatter that renders values as $-prefixed."""
    from matplotlib.ticker import FuncFormatter

    return FuncFormatter(lambda value, _pos: f"${_compact_number(value)}")


def number_formatter():
    """Return a FuncFormatter rendering plain counts as 1.2k / 1.2M / 1.2B.

    Mirrors the ChartRenderer `yAxisFormat: number` behavior (lowercase
    k, uppercase M / B) for volume and count axes. Shares the ladder with
    ``y_axis``.
    """
    from matplotlib.ticker import FuncFormatter

    return FuncFormatter(lambda value, _pos: _compact_number(value))


def title_block(ax, title: str, subtitle: str | None = None) -> Any:
    """Declare the headline and deck on an axis whose figure you already own.

    Equivalent to passing ``headline`` / ``deck`` to ``figure()``, for code
    that built its figure with plain ``plt.subplots()``. The text renders in
    the reserved header band at save() time, not inside the axes, so a long
    headline wraps instead of overrunning the plot.
    """
    meta = _meta(ax.figure)
    meta["headline"] = title
    if subtitle:
        meta["deck"] = subtitle
    return ax


def area_series(
    ax,
    x,
    y,
    *,
    color: str | None = None,
    label: str | None = None,
    linewidth: float = 2.0,
    alpha: float = 0.15,
    baseline: float | None = None,
) -> Any:
    """Plot a line with the Adjacent gradient area fill under it.

    This is the signature TradingViewChart look: a solid line with a
    vertical gradient that fades from the line color down to transparent at
    the baseline. Works with numeric or datetime x. Pass ``baseline`` to
    anchor the fill (defaults to 0 for series that cross zero, else the
    series minimum).

    The default color is the off-black ``LINE``. Reach for ``ACCENT_DEEP``
    only when a chart is deliberately featured - never to signal that the
    series went up.
    """
    import numpy as np
    import matplotlib.dates as mdates
    from matplotlib.colors import to_rgb
    from matplotlib.patches import Polygon

    color = color or LINE
    (line,) = ax.plot(x, y, color=color, linewidth=linewidth, label=label, zorder=3)

    first = x[0]
    if isinstance(first, datetime):
        xnum = mdates.date2num(x)
    else:
        xnum = np.asarray(x, dtype=float)
    ynum = np.asarray(y, dtype=float)

    if baseline is None:
        baseline = 0.0 if ynum.min() <= 0.0 <= ynum.max() else float(ynum.min())
    top = float(ynum.max())
    if top == baseline:
        return line

    rgb = to_rgb(color)
    gradient = np.empty((256, 1, 4))
    gradient[:, 0, :3] = rgb
    gradient[:, 0, 3] = np.linspace(alpha, 0.0, 256)
    image = ax.imshow(
        gradient,
        aspect="auto",
        extent=(float(xnum.min()), float(xnum.max()), baseline, top),
        origin="upper",
        zorder=1,
    )
    vertices = [(xnum[0], baseline), *zip(xnum, ynum), (xnum[-1], baseline)]
    clip = Polygon(vertices, closed=True, transform=ax.transData)
    ax.add_patch(clip)
    image.set_clip_path(clip)
    clip.set_visible(False)
    # Anchor the fill to the baseline and keep headroom above the peak so an
    # end_label() callout lands inside the plot instead of in the title band.
    ax.set_ylim(baseline, top + (top - baseline) * 0.12)
    return line


def format_date_axis(
    ax,
    *,
    concise: bool = True,
    fmt: str | None = None,
    rotation: int = 0,
    maxticks: int = 6,  # clamped to >= 4; below that the locator cannot pick an interval
) -> Any:
    """Style a datetime x-axis the Adjacent way: mono labels, few ticks, no crowding.

    By default uses matplotlib's ConciseDateFormatter, which keeps each tick
    label narrow (for example ``18:00`` with the shared ``Jul 31`` factored
    into an offset) so adjacent day boundaries never overlap - the collision
    seen with a fixed ``%b %d %H:%M`` format. Pass ``concise=False`` with an
    explicit ``fmt`` only when you need a specific format and know the span is
    short enough to fit.

    Keeps labels horizontal by default (rotation=0) so they never collide with
    the source line. Use rotation=30 only when labels are long; the anchor is
    set to 'right' so rotated labels hang under their tick.
    """
    import matplotlib.dates as mdates

    locator = mdates.AutoDateLocator(maxticks=max(4, maxticks))
    ax.xaxis.set_major_locator(locator)
    if concise:
        # show_offset=False kills the floating "2026-Aug-02" that
        # ConciseDateFormatter parks at the right of the axis. It is a
        # stray date sitting outside the chart with nothing to anchor it;
        # if the year matters, put it in the deck.
        ax.xaxis.set_major_formatter(
            mdates.ConciseDateFormatter(locator, show_offset=False)
        )
    else:
        ax.xaxis.set_major_formatter(mdates.DateFormatter(fmt or "%b %d %H:%M"))

    # AutoDateLocator treats maxticks as a hint and routinely overshoots it,
    # which is what crowds the axis on narrow panels. Thin the result so the
    # cap actually holds.
    ticks = ax.get_xticks()
    if len(ticks) > maxticks:
        stride = -(-len(ticks) // maxticks)
        ax.set_xticks(ticks[::stride])

    ha = "center" if rotation == 0 else "right"
    for lbl in ax.get_xticklabels():
        lbl.set_rotation(rotation)
        lbl.set_ha(ha)
        lbl.set_fontfamily(FONTS["mono"])
        lbl.set_fontstyle("normal")

    ax.xaxis.get_offset_text().set_visible(False)
    return ax


def end_label(
    ax,
    x,
    y,
    text: str,
    color: str,
    *,
    above: bool = True,
    dx: int = -6,
    dy: int = 10,
) -> Any:
    """Place a value callout at a series endpoint without hitting the axis.

    Offsets the label off the line (up by default) so the series line does not
    cross the text and the callout does not drop into the x-axis tick-label
    band. For the lowest series on the chart pass ``above=True`` (the default)
    so the label sits inside the plot rather than under the axis.
    """
    ax.annotate(
        text,
        xy=(x, y),
        xytext=(dx, dy if above else -dy),
        textcoords="offset points",
        color=color,
        fontsize=10,
        fontweight="bold",
        family=FONTS["main"],
        ha="right",
        va="bottom" if above else "top",
        clip_on=False,
        annotation_clip=False,
    )
    return ax


# -------------------------------------------------------------------
# Chart forms - reusable drawing helpers
# -------------------------------------------------------------------


def heikin_ashi_transform(
    opens: list[float],
    highs: list[float],
    lows: list[float],
    closes: list[float],
) -> list[tuple[float, float, float, float]]:
    """Transform OHLC into Heikin-Ashi OHLC.

    Formulas (house candle style - HA is the only candle type we draw):

    - HA-close = (O + H + L + C) / 4
    - HA-open  = (prev HA-open + prev HA-close) / 2
      (first bar uses (O + C) / 2)
    - HA-high  = max(H, HA-open, HA-close)
    - HA-low   = min(L, HA-open, HA-close)
    """
    if not (len(opens) == len(highs) == len(lows) == len(closes)):
        raise ValueError("opens/highs/lows/closes must be the same length")
    out: list[tuple[float, float, float, float]] = []
    ha_open = ha_close = 0.0
    for i, (o, h, low, c) in enumerate(zip(opens, highs, lows, closes)):
        ha_close = (float(o) + float(h) + float(low) + float(c)) / 4.0
        if i == 0:
            ha_open = (float(o) + float(c)) / 2.0
        else:
            prev_o, _, _, prev_c = out[-1]
            ha_open = (prev_o + prev_c) / 2.0
        ha_high = max(float(h), ha_open, ha_close)
        ha_low = min(float(low), ha_open, ha_close)
        out.append((ha_open, ha_high, ha_low, ha_close))
    return out


def heikin_ashi(
    ax,
    x,
    opens,
    highs,
    lows,
    closes,
    *,
    width: float = 0.6,
    graph_paper: bool = True,
) -> Any:
    """Draw Heikin-Ashi candles - the only candle form this plugin uses.

    Monochrome house style:

    - bullish (HA-close >= HA-open): hollow body filled with canvas beige,
      ink edge
    - bearish: solid charcoal (ink) body
    - thin wicks in ink
    - optional graph-paper grid (finer dotted y grid)
    - y axis on the right with arrowheads on the top tick

    Never draw raw candlesticks. Transform OHLC first with
    ``heikin_ashi_transform`` if you need the numbers without plotting.
    """
    from matplotlib.patches import Rectangle
    from matplotlib.lines import Line2D
    import numpy as np

    ha = heikin_ashi_transform(list(opens), list(highs), list(lows), list(closes))
    xs = list(x)
    if len(xs) != len(ha):
        raise ValueError("x and OHLC series must match in length")

    # Numeric positions for width math even when x is datetime.
    import matplotlib.dates as mdates

    if xs and isinstance(xs[0], datetime):
        xnum = mdates.date2num(xs)
    else:
        xnum = np.asarray(xs, dtype=float)

    if len(xnum) > 1:
        step = float(np.median(np.diff(xnum)))
    else:
        step = 1.0
    body_w = step * width

    y_lo = min(bar[2] for bar in ha)
    y_hi = max(bar[1] for bar in ha)
    for xi, (o, h, low, c) in zip(xnum, ha):
        bullish = c >= o
        body_bottom = min(o, c)
        body_height = abs(c - o) or (y_hi - y_lo) * 0.01 or 0.01
        ax.add_line(
            Line2D(
                [xi, xi],
                [low, h],
                color=PALETTE["ink"],
                linewidth=0.8,
                solid_capstyle="butt",
                zorder=3,
            )
        )
        ax.add_patch(
            Rectangle(
                (xi - body_w / 2, body_bottom),
                body_w,
                body_height,
                facecolor=PALETTE["canvas"] if bullish else PALETTE["ink"],
                edgecolor=PALETTE["ink"],
                linewidth=0.9,
                zorder=4,
            )
        )

    # Patches do not autoscale reliably; pin limits to the HA range.
    pad = (y_hi - y_lo) * 0.08 or 1.0
    ax.set_xlim(float(xnum.min()) - step * 0.6, float(xnum.max()) + step * 0.6)
    ax.set_ylim(y_lo - pad, y_hi + pad)

    if graph_paper:
        ax.grid(axis="y", visible=True, linestyle=":", linewidth=0.6, color=PALETTE["rule"])
        ax.grid(axis="x", visible=True, linestyle=":", linewidth=0.5, color=PALETTE["grid"])

    # Right axis with a small arrowhead at the top of the spine.
    ax.yaxis.tick_right()
    ax.yaxis.set_label_position("right")
    ax.spines["right"].set_visible(True)
    ax.spines["right"].set_color(PALETTE["rule"])
    ax.spines["right"].set_linewidth(0.8)
    ax.spines["left"].set_visible(False)
    ax.tick_params(axis="y", length=3, width=0.7, colors=PALETTE["ink"], labelcolor=PALETTE["ink"])
    y0, y1 = ax.get_ylim()
    ax.annotate(
        "",
        xy=(1.0, y1),
        xytext=(1.0, y1 - (y1 - y0) * 0.04),
        xycoords=("axes fraction", "data"),
        textcoords=("axes fraction", "data"),
        arrowprops={"arrowstyle": "-|>", "color": PALETTE["ink"], "lw": 0.7},
        annotation_clip=False,
    )
    return ax


def stacked_area(ax, x, series: list[tuple[str, list[float]]], *, colors: list[str] | None = None) -> Any:
    """Stacked area chart using the Adjacent series cycle."""
    import numpy as np

    colors = colors or SERIES
    ys = [np.asarray(values, dtype=float) for _label, values in series]
    labels = [label for label, _values in series]
    ax.stackplot(x, *ys, labels=labels, colors=colors[: len(ys)], alpha=0.85, linewidth=0)
    for i, values in enumerate(ys):
        top = sum(ys[j] for j in range(i + 1))
        ax.plot(x, top, color=colors[i % len(colors)], linewidth=1.0, zorder=3)
    return ax


def waterfall(
    ax,
    labels: list[str],
    values: list[float],
    *,
    total_label: str = "Total",
) -> Any:
    """Waterfall bars: sequential signed contributions plus a total.

    Positive steps use ``UP``, negative use ``DOWN``, the total uses ink.
    """
    import numpy as np

    vals = [float(v) for v in values]
    running = 0.0
    bottoms: list[float] = []
    heights: list[float] = []
    colors: list[str] = []
    for v in vals:
        bottoms.append(running if v >= 0 else running + v)
        heights.append(abs(v))
        colors.append(UP if v >= 0 else DOWN)
        running += v
    bottoms.append(0.0)
    heights.append(abs(running))
    colors.append(PALETTE["ink"])
    xs = np.arange(len(vals) + 1)
    tick_labels = list(labels) + [total_label]
    bars = ax.bar(xs, heights, bottom=bottoms, color=colors, width=0.62, edgecolor="none", zorder=3)
    ax.set_xticks(xs)
    ax.set_xticklabels(tick_labels)
    for label in ax.get_xticklabels():
        label.set_fontfamily(FONTS["main"])
    signed = vals + [running]
    bar_labels(
        ax,
        bars,
        signed,
        fmt=lambda v: f"{v:+.2f}" if abs(v) < 100 else f"{v:+.1f}",
    )
    return bars


def waffle(
    ax,
    parts: list[tuple[str, float]],
    *,
    rows: int = 5,
    cols: int = 20,
    colors: list[str] | None = None,
) -> Any:
    """Waffle grid for composition shares that sum to ~100.

    ``parts`` is ``(label, share)`` where share is a fraction (0-1) or a
    percent (0-100). Prefer this over a pie chart.
    """
    import numpy as np
    from matplotlib.patches import Rectangle

    colors = colors or SERIES
    total_cells = rows * cols
    shares = []
    for label, share in parts:
        value = float(share)
        if value > 1.0:
            value = value / 100.0
        shares.append((label, max(0.0, value)))
    counts = [int(round(share * total_cells)) for _label, share in shares]
    # Fix rounding so the grid fills exactly.
    while sum(counts) > total_cells and counts:
        i = max(range(len(counts)), key=lambda k: counts[k])
        counts[i] -= 1
    while sum(counts) < total_cells and counts:
        i = max(range(len(counts)), key=lambda k: shares[k][1])
        counts[i] += 1

    cell = 1.0
    gap = 0.12
    idx = 0
    for (label, _share), count, color in zip(shares, counts, colors):
        for _ in range(count):
            r = idx // cols
            c = idx % cols
            ax.add_patch(
                Rectangle(
                    (c * (cell + gap), (rows - 1 - r) * (cell + gap)),
                    cell,
                    cell,
                    facecolor=color,
                    edgecolor=PALETTE["canvas"],
                    linewidth=0.5,
                )
            )
            idx += 1
    ax.set_xlim(-gap, cols * (cell + gap))
    ax.set_ylim(-gap, rows * (cell + gap))
    ax.set_aspect("equal")
    ax.axis("off")
    # Caller should stamp names with swatch_legend(fig, [(label, color), ...]).
    return ax


def range_dumbbell(
    ax,
    labels: list[str],
    lows: list[float],
    highs: list[float],
    *,
    low_color: str | None = None,
    high_color: str | None = None,
) -> Any:
    """Horizontal range dumbbells: low/high dots connected by a hairline."""
    low_color = low_color or SERIES[1]
    high_color = high_color or SERIES[0]
    ys = list(range(len(labels)))
    for y, lo, hi in zip(ys, lows, highs):
        ax.plot([lo, hi], [y, y], color=PALETTE["rule"], linewidth=1.2, zorder=2)
        ax.scatter([lo], [y], color=low_color, s=36, zorder=3, edgecolors="none")
        ax.scatter([hi], [y], color=high_color, s=36, zorder=3, edgecolors="none")
    ax.set_yticks(ys)
    ax.set_yticklabels(labels)
    for label in ax.get_yticklabels():
        label.set_fontfamily(FONTS["main"])
    ax.invert_yaxis()
    return ax


def heatmap_row(
    ax,
    labels: list[str],
    values: list[float],
    *,
    vmin: float | None = None,
    vmax: float | None = None,
) -> Any:
    """Single-row heatmap for correlation / contribution strips."""
    import numpy as np

    data = np.asarray(values, dtype=float).reshape(1, -1)
    lo = float(np.min(data)) if vmin is None else vmin
    hi = float(np.max(data)) if vmax is None else vmax
    # Diverging through canvas: down -> canvas -> up using trend colors is
    # heavy; use ink intensity on sage/salmon via a simple two-stop blend.
    cmap_colors = [DOWN, PALETTE["canvas"], UP]
    from matplotlib.colors import LinearSegmentedColormap

    cmap = LinearSegmentedColormap.from_list("adjacent_div", cmap_colors)
    im = ax.imshow(data, aspect="auto", cmap=cmap, vmin=lo, vmax=hi)
    ax.set_yticks([])
    ax.set_xticks(range(len(labels)))
    ax.set_xticklabels(labels)
    for label in ax.get_xticklabels():
        label.set_fontfamily(FONTS["mono"])
        label.set_fontsize(9)
    ax.spines["bottom"].set_visible(False)
    return im


def radar(
    ax,
    labels: list[str],
    values: list[float],
    *,
    color: str | None = None,
    max_value: float | None = None,
) -> Any:
    """Radar / spider chart for multi-metric profiles.

    ``ax`` must already be a polar axes. Build one with::

        import matplotlib.pyplot as plt
        fig, ax = plt.subplots(subplot_kw={"projection": "polar"}, figsize=(7.6, 4.6))
        adj.apply_adjacent_theme()
        adj.radar(ax, labels, values)
        adj.title_block(ax, "Profile", "DEMO")
        adj.save(fig, "radar.png")

    ``figure()`` does not take a polar projection; use the pattern above.
    """
    import numpy as np

    color = color or ACCENT_DEEP
    n = len(labels)
    if n < 3:
        raise ValueError("radar needs at least 3 axes")
    angles = np.linspace(0, 2 * np.pi, n, endpoint=False).tolist()
    vals = [float(v) for v in values]
    vals_closed = vals + vals[:1]
    angles_closed = angles + angles[:1]
    if getattr(ax, "name", None) != "polar":
        raise ValueError(
            "radar() requires a polar axes; "
            'use plt.subplots(subplot_kw={"projection": "polar"})'
        )
    peak = max_value if max_value is not None else max(vals) * 1.1 or 1.0
    ax.set_theta_offset(np.pi / 2)
    ax.set_theta_direction(-1)
    ax.set_thetagrids(np.degrees(angles), labels)
    ax.set_ylim(0, peak)
    ax.plot(angles_closed, vals_closed, color=color, linewidth=1.6)
    ax.fill(angles_closed, vals_closed, color=color, alpha=0.18)
    ax.grid(color=PALETTE["rule"], linestyle=":", linewidth=0.7)
    ax.spines["polar"].set_color(PALETTE["rule"])
    return ax


def quote_board(
    ax,
    rows: list[dict[str, Any]],
    *,
    columns: tuple[str, ...] = ("name", "mid", "change"),
) -> Any:
    """Minimal quote board table for a small set of markets / indices.

    Each row is a dict. ``mid`` and ``change`` render in mono; positive
    change uses ``UP``, negative ``DOWN``.
    """
    ax.axis("off")
    if not rows:
        return ax
    cell_text: list[list[str]] = []
    cell_colors: list[list[str]] = []
    for row in rows:
        line = []
        colors = []
        for col in columns:
            value = row.get(col, "")
            if col in ("mid", "price", "last"):
                text = f"{float(value):.2f}" if isinstance(value, (int, float)) else str(value)
                line.append(text)
                colors.append(PALETTE["ink"])
            elif col in ("change", "move", "change_pct"):
                if isinstance(value, (int, float)):
                    text = f"{value * 100:+.2f}%" if abs(value) <= 1 else f"{value:+.2f}%"
                    colors.append(UP if value >= 0 else DOWN)
                else:
                    text = str(value)
                    colors.append(PALETTE["ink"])
                line.append(text)
            else:
                line.append(str(value))
                colors.append(PALETTE["ink"])
        cell_text.append(line)
        cell_colors.append(colors)

    table = ax.table(
        cellText=cell_text,
        colLabels=[c.upper() for c in columns],
        loc="center",
        cellLoc="left",
    )
    table.auto_set_font_size(False)
    table.set_fontsize(10)
    table.scale(1.0, 1.4)
    for (r, c), cell in table.get_celld().items():
        cell.set_edgecolor(PALETTE["rule"])
        cell.set_linewidth(0.4)
        if r == 0:
            cell.set_facecolor(PALETTE["canvas"])
            cell.set_text_props(color=PALETTE["fg-3"], fontfamily=FONTS["main"][0], fontsize=8)
        else:
            cell.set_facecolor(PALETTE["canvas"])
            color = cell_colors[r - 1][c] if c < len(cell_colors[r - 1]) else PALETTE["ink"]
            family = FONTS["mono"][0] if columns[c] in ("mid", "price", "last", "change", "move", "change_pct") else FONTS["main"][0]
            cell.set_text_props(color=color, fontfamily=family)
    return table


def prob_stack(
    ax,
    labels: list[str],
    probs: list[float],
    *,
    colors: list[str] | None = None,
) -> Any:
    """Horizontal probability stack (mutually exclusive outcomes).

    ``probs`` are 0-1 fractions and should sum to ~1. Each segment is
    labelled in mono with the percent.
    """
    colors = colors or SERIES
    left = 0.0
    for label, prob, color in zip(labels, probs, colors):
        width = float(prob)
        ax.barh([0], [width], left=left, color=color, edgecolor=PALETTE["canvas"], height=0.55)
        if width >= 0.08:
            ax.text(
                left + width / 2,
                0,
                f"{width * 100:.0f}%",
                ha="center",
                va="center",
                color=PALETTE["on-deep"] if color in (PALETTE["ink"], ACCENT_DEEP, DOWN) else PALETTE["ink"],
                fontsize=9,
                fontfamily=FONTS["mono"][0],
                fontweight="bold",
            )
        left += width
    ax.set_yticks([])
    ax.set_xlim(0, max(left, 1.0))
    ax.set_xticks([])
    for spine in ax.spines.values():
        spine.set_visible(False)
    # Labels under the bar via swatch_legend is preferred; also stamp names.
    pen = 0.0
    for label, prob, color in zip(labels, probs, colors):
        if float(prob) >= 0.05:
            ax.text(
                pen + float(prob) / 2,
                -0.45,
                label,
                ha="center",
                va="top",
                fontsize=9,
                color=PALETTE["fg-2"],
                fontfamily=FONTS["main"][0],
                clip_on=False,
            )
        pen += float(prob)
    ax.set_ylim(-0.8, 0.6)
    return ax


def small_multiples(
    fig,
    axes,
    series: list[tuple[str, Any, Any]],
    *,
    color: str | None = None,
) -> Any:
    """Plot one off-black series per panel of a figure created with panels=.

    ``series`` is a list of ``(label, x, y)``. Extra panels are turned off.
    """
    color = color or LINE
    panels = list(axes.flat) if hasattr(axes, "flat") else list(axes)
    for ax, (label, x, y) in zip(panels, series):
        ax.plot(x, y, color=color, linewidth=1.6)
        ax.set_title(label, loc="left", fontsize=10, color=PALETTE["fg-2"], fontfamily=FONTS["main"][0])
        frame(ax)
    for ax in panels[len(series) :]:
        ax.axis("off")
    return axes


def _style_ticklabels(fig) -> None:
    """Render every tick label in the mono stack, upright, tabular."""
    mono = FONTS["mono"]
    for ax in fig.axes:
        for lbl in (*ax.get_xticklabels(), *ax.get_yticklabels()):
            lbl.set_fontfamily(mono)
            lbl.set_fontstyle("normal")


def source_line(fig, text: str | None = None) -> Any:
    """Set the source credit rendered in the footer band by save()."""
    _meta(fig)["source"] = text if text is not None else _timestamped_source()
    return fig


def _wrap(text: str, width_in: float, points: float) -> list[str]:
    """Wrap text to a column width, estimating from the font size.

    Inter averages a little over half an em per character at these sizes, so
    ``0.52 * points`` is a good width estimate and keeps wrapping stable
    across the font fallbacks (the brand fonts are often absent on a host).
    """
    import textwrap

    per_char_in = 0.52 * points / 72.0
    columns = max(16, int(width_in / per_char_in))
    return textwrap.wrap(text, columns) or [""]


def _header_height(fig, meta: dict[str, Any]) -> float:
    """Inches of figure height the declared header block needs."""
    if not any((meta["headline"], meta["deck"], meta["legend"])):
        return _HEADER_TOP
    width = fig.get_figwidth() - 2 * _MARGIN_X
    height = _HEADER_TOP
    if meta["headline"]:
        height += _HEADLINE_H * len(_wrap(meta["headline"], width, 16))
    if meta["deck"]:
        height += _DECK_H * len(_wrap(meta["deck"], width, 11))
    if meta["legend"]:
        height += _LEGEND_H
    return height + _HEADER_GAP


def _draw_header(fig, meta: dict[str, Any]) -> None:
    """Render headline, deck, and swatch legend from the top down."""
    from matplotlib.patches import Rectangle

    fig_h, fig_w = fig.get_figheight(), fig.get_figwidth()
    width = fig_w - 2 * _MARGIN_X
    x = _MARGIN_X / fig_w
    pen_y = fig_h - _HEADER_TOP  # inches from the bottom, walking down

    def _y(inches: float) -> float:
        return inches / fig_h

    if meta["headline"]:
        for line in _wrap(meta["headline"], width, 16):
            pen_y -= _HEADLINE_H
            fig.text(
                x,
                _y(pen_y),
                line,
                family=FONTS["main"],
                fontsize=16,
                fontweight="bold",
                color=PALETTE["ink"],
                ha="left",
                va="bottom",
            )
    if meta["deck"]:
        for line in _wrap(meta["deck"], width, 11):
            pen_y -= _DECK_H
            fig.text(
                x,
                _y(pen_y),
                line,
                family=FONTS["serif"],
                fontsize=11,
                color=PALETTE["fg-2"],
                ha="left",
                va="bottom",
            )
    if meta["legend"]:
        pen_y -= _LEGEND_H
        swatch = 0.11  # inches
        pen = _MARGIN_X
        for label, color in meta["legend"]:
            fig.add_artist(
                Rectangle(
                    (pen / fig_w, _y(pen_y + 0.02)),
                    swatch / fig_w,
                    swatch / fig_h,
                    facecolor=color,
                    edgecolor="none",
                    transform=fig.transFigure,
                )
            )
            pen += swatch + 0.07
            fig.text(
                pen / fig_w,
                _y(pen_y),
                label,
                family=FONTS["main"],
                fontsize=9.5,
                color=PALETTE["fg-2"],
                ha="left",
                va="bottom",
            )
            # Advance past the label using the same width estimate as _wrap.
            pen += len(label) * 0.52 * 9.5 / 72.0 + 0.22


def _draw_footer(fig, meta: dict[str, Any]) -> None:
    """Render the source credit, bottom-left. No rule, no wordmark.

    ``Source: Adjacent`` already carries the attribution, so a wordmark
    beside it just says the same thing twice, and a divider rule adds a
    line the eye has to cross for nothing.
    """
    if not meta["source"]:
        return
    fig.text(
        _MARGIN_X / fig.get_figwidth(),
        0.12 / fig.get_figheight(),
        f"Source: {meta['source']}",
        family=FONTS["main"],
        fontsize=8.5,
        color=PALETTE["fg-3"],
        ha="left",
        va="bottom",
    )


def save(
    fig,
    path: str,
    *,
    source: str | None = None,
    dpi: int = 200,
) -> str:
    """Lay out the chrome, draw the header and footer, and write the figure.

    Reserves exactly the room the declared header and footer need, positions
    the axes and their tick labels in what is left, then draws the chrome
    into the reserved bands. Because the bands are measured rather than
    guessed, headlines never sit on the data and the source never collides
    with the tick labels. No ``bbox_inches="tight"`` crop, so the reserved
    whitespace survives and the beige canvas matches the Adjacent page.

    ``source`` overrides the source declared in ``figure()``; pass ``None``
    (the default) to keep it. Returns the absolute path written.
    """
    apply_adjacent_theme()
    meta = _meta(fig)
    if source is not None:
        meta["source"] = source

    fig.patch.set_facecolor(PALETTE["canvas"])
    for ax in fig.axes:
        ax.set_facecolor(PALETTE["canvas"])
    _style_ticklabels(fig)

    fig_h = fig.get_figheight()
    bottom = _FOOTER_H / fig_h
    top = 1.0 - _header_height(fig, meta) / fig_h
    fig_w = fig.get_figwidth()
    left = _MARGIN_X / fig_w
    right = 1.0 - (_MARGIN_X + meta["right_gutter"]) / fig_w
    try:
        # h_pad keeps a small-multiple row clear of the row above's tick labels.
        fig.tight_layout(rect=(left, bottom, right, top), pad=0.3, h_pad=1.6)
    except Exception:
        fig.subplots_adjust(left=0.12, right=right, bottom=bottom, top=top)

    _draw_header(fig, meta)
    _draw_footer(fig, meta)
    out = os.path.abspath(path)
    fig.savefig(out, dpi=dpi, facecolor=PALETTE["canvas"])
    return out


def plotly_template() -> dict[str, Any]:
    """Return a Plotly layout template dict mirroring the Adjacent brand.

    For code paths that render Plotly figures instead of matplotlib.
    Usage:
        import plotly.graph_objects as go
        import adjacent_chart_style as adj
        fig = go.Figure(layout=adj.plotly_template())
    """
    p = PALETTE
    return {
        "paper_bgcolor": p["canvas"],
        "plot_bgcolor": p["canvas"],
        "font": {
            "family": _font_main(),
            "color": p["ink"],
            "size": 12,
        },
        "title": {"font": {"family": _font_main(), "size": 16, "color": p["ink"]}},
        "colorway": SERIES,
        "margin": {"l": 48, "r": 24, "t": 56, "b": 40},
        "xaxis": {
            "gridcolor": p["grid"],
            "gridwidth": 1,
            "zerolinecolor": p["rule"],
            "linecolor": p["rule"],
            "tickfont": {"family": _font_mono(), "size": 10, "color": p["ink"]},
            "titlefont": {"family": _font_main(), "size": 11, "color": p["ink"]},
        },
        "yaxis": {
            "gridcolor": p["grid"],
            "gridwidth": 1,
            "zerolinecolor": p["rule"],
            "linecolor": p["rule"],
            "tickfont": {"family": _font_mono(), "size": 10, "color": p["ink"]},
            "titlefont": {"family": _font_main(), "size": 11, "color": p["ink"]},
            "tickformat": ",.0%",
        },
        "hoverlabel": {
            "bgcolor": p["paper"],
            "bordercolor": p["rule"],
            "font": {"family": _font_mono(), "size": 11, "color": p["ink"]},
        },
        "showlegend": True,
        "legend": {
            "bgcolor": "rgba(0,0,0,0)",
            "font": {"family": _font_main(), "size": 10, "color": p["fg-2"]},
        },
        "annotations": [
            {
                "text": f"Source: {_timestamped_source()}",
                "showarrow": False,
                "xref": "paper",
                "yref": "paper",
                "x": 0.0,
                "y": -0.12,
                "xanchor": "left",
                "font": {"family": _font_main(), "size": 9, "color": p["fg-3"]},
            }
        ],
    }


if __name__ == "__main__":
    # Smoke test: render a tiny branded chart to <tmp>/adjacent_chart_style_smoke.png
    import tempfile

    try:
        import matplotlib

        matplotlib.use("Agg")
    except Exception as exc:  # pragma: no cover
        raise SystemExit(f"matplotlib unavailable: {exc}")

    from datetime import timedelta

    # The house chart: editorial header, gradient area fill, last-value pill.
    t0 = datetime(2026, 7, 30, 17, 0)
    xs = [t0 + timedelta(hours=3 * i) for i in range(17)]
    idx = [100.0, 100.4, 100.9, 101.2, 100.8, 101.6, 102.1, 101.7, 102.9,
           103.4, 103.1, 103.8, 104.2, 104.0, 104.6, 105.1, 105.4]
    fig, ax = figure(
        headline="Political futures index closed the week at a 30-day high",
        deck="UPFI",
    )
    area_series(ax, xs, idx)
    y_axis(ax, "level")
    last_value(ax, xs[-1], idx[-1], "105.4")
    format_date_axis(ax)
    out = save(fig, os.path.join(tempfile.gettempdir(), "adjacent_chart_style_smoke.png"))
    print(out)
