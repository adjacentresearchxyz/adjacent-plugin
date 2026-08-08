"""Golden / structural-invariant test for the Adjacent chart helper.

Locks the brand and layout so a refactor of ``adjacent_chart_style.py``
cannot silently change every chart. Uses matplotlib with the Agg backend
and the canonical helper to render a small deterministic chart, then
asserts structural invariants - not pixel-diff golden images, which are
too brittle across matplotlib versions.

Standard-library + pytest style like ``test_offline_signals``. The whole
module is skipped when matplotlib is absent (system ``python3`` in CI may
lack it - that is acceptable; the contract tests in
``test_chart_style_contract.py`` cover the palette and API without
matplotlib).
"""

from __future__ import annotations

import importlib.util
import re
import sys
from datetime import datetime, timedelta
from pathlib import Path

import pytest

matplotlib = pytest.importorskip("matplotlib")
matplotlib.use("Agg")  # noqa: E402 - headless backend before pyplot import

ROOT = Path(__file__).resolve().parents[1]
HELPER = ROOT / "scripts" / "adjacent_chart_style.py"
FONTS_DIR = ROOT / "assets" / "fonts"

_SOURCE_RE = re.compile(r"Source: Adjacent \d{4}-\d{2}-\d{2} \d{2}:\d{2} UTC")

_T0 = datetime(2026, 7, 30, 17, 0)
_XS = [_T0 + timedelta(hours=3 * i) for i in range(8)]
_YS = [100.0, 100.4, 100.9, 101.2, 100.8, 101.6, 102.1, 102.4]


def _load_helper():
    scripts_path = str(HELPER.parent)
    if scripts_path not in sys.path:
        sys.path.insert(0, scripts_path)
    spec = importlib.util.spec_from_file_location("adjacent_chart_style", HELPER)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _make_chart(adj, *, headline: str = "Invariant check", deck: str = "TEST"):
    """Build a small deterministic chart and return (fig, ax, line)."""
    fig, ax = adj.figure(headline=headline, deck=deck)
    line = adj.area_series(ax, _XS, _YS)
    adj.y_axis(ax, "level")
    return fig, ax, line


# -------------------------------------------------------------------
# Structural invariants (no pixel diffing)
# -------------------------------------------------------------------


def test_figure_and_axes_facecolor_equal_canvas():
    import matplotlib.colors as mcolors

    adj = _load_helper()
    fig, ax, _line = _make_chart(adj)
    canvas = adj.PALETTE["canvas"]
    assert mcolors.to_hex(fig.get_facecolor()) == canvas
    assert mcolors.to_hex(ax.get_facecolor()) == canvas


def test_only_bottom_spine_visible():
    adj = _load_helper()
    _fig, ax, _line = _make_chart(adj)
    assert ax.spines["bottom"].get_visible() is True
    for side in ("top", "right", "left"):
        assert ax.spines[side].get_visible() is False


def test_y_grid_on_x_grid_off():
    adj = _load_helper()
    _fig, ax, _line = _make_chart(adj)
    # frame() turns the y grid on and the x grid off explicitly. Probe the
    # gridline Line2D visibility rather than a private axis attribute (the
    # ``_gridOnMajor`` field was removed in matplotlib 3.11).
    y_visible = [g.get_visible() for g in ax.get_ygridlines()]
    x_visible = [g.get_visible() for g in ax.get_xgridlines()]
    assert y_visible and all(y_visible), "y gridlines should all be visible"
    assert x_visible and not any(x_visible), "x gridlines should all be hidden"


def test_lone_series_color_is_line():
    adj = _load_helper()
    _fig, _ax, line = _make_chart(adj)
    assert line.get_color() == adj.LINE == "#0e2a1f"


def test_source_line_text_matches_contract(tmp_path):
    adj = _load_helper()
    fig, _ax, _line = _make_chart(adj, headline="Source check")
    adj.save(fig, str(tmp_path / "source.png"))
    # The footer is drawn as a figure-level text artist by _draw_footer.
    source_texts = [
        t.get_text()
        for t in fig.texts
        if t.get_text().startswith("Source: Adjacent")
    ]
    assert source_texts, "no Source: Adjacent footer text rendered"
    assert _SOURCE_RE.fullmatch(source_texts[0]), (
        f"source line does not match contract: {source_texts[0]!r}"
    )


def test_saved_png_exists_and_is_nontrivial(tmp_path):
    adj = _load_helper()
    fig, ax, _line = _make_chart(adj, headline="Saved PNG check")
    adj.last_value(ax, _XS[-1], _YS[-1], "102.4")
    out = tmp_path / "golden.png"
    adj.save(fig, str(out))
    assert out.is_file()
    assert out.stat().st_size > 2048, (
        f"PNG too small ({out.stat().st_size} bytes) to be a real render"
    )


# -------------------------------------------------------------------
# Font bundling wiring
# -------------------------------------------------------------------


@pytest.mark.skipif(
    not FONTS_DIR.is_dir(),
    reason="bundled fonts absent; font registration skipped",
)
def test_bundled_fonts_registered_after_theme():
    """apply_adjacent_theme() loads the vendored Inter / IBM Plex Mono faces."""
    adj = _load_helper()
    from matplotlib import font_manager as fm

    adj.apply_adjacent_theme()
    names = {f.name for f in fm.fontManager.ttflist}
    assert "Inter" in names, "Inter not registered after apply_adjacent_theme()"
    assert "IBM Plex Mono" in names, (
        "IBM Plex Mono not registered after apply_adjacent_theme()"
    )


@pytest.mark.skipif(
    not FONTS_DIR.is_dir(),
    reason="bundled fonts absent; font directory check skipped",
)
def test_bundled_font_files_present():
    """The lean set of vendored static TTFs and OFL license texts ship."""
    for name in (
        "Inter-Regular.ttf",
        "Inter-SemiBold.ttf",
        "Inter-Bold.ttf",
        "IBMPlexMono-Regular.ttf",
        "IBMPlexMono-Bold.ttf",
        "OFL-Inter.txt",
        "OFL-IBMPlexMono.txt",
    ):
        assert (FONTS_DIR / name).is_file(), f"missing bundled font asset: {name}"
