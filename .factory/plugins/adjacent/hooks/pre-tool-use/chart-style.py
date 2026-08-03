#!/usr/bin/env python3
"""Pre-tool-use chart-style hook for the adjacent plugin.

Enforces the Adjacent chart brand on any Python / chart-library code the
model is about to write or run. Pairs with the `adjacent-chart-style`
skill and the `scripts/adjacent_chart_style.py` helper.

Behavior:

- Detects chart-library usage: seaborn, matplotlib / pyplot, plotly,
  and Datawrapper metadata payloads.
- Detects the Adjacent-aware signal: an import of
  `adjacent_chart_style` or references to `adj.PALETTE`, `adj.SERIES`,
  `adj.UP`, `adj.DOWN`, `adj.apply_adjacent_theme` (alias
  `adj.apply_adjacent_style`), `adj.plotly_template`.
- On Create / Edit / ApplyPatch:
    * chart library + Adjacent-aware signal -> allow.
    * chart library + hardcoded hex NOT in the Adjacent palette and no
      Adjacent-aware signal -> DENY with a remediation hint. This is the
      divergence guard: a script reaching for viridis / tab10 / a random
      brand color is not on-brand.
    * chart library + no hardcoded hex + no Adjacent-aware signal ->
      allow, but inject additionalContext nudging toward the helper.
    * no chart library -> allow (skip).
- On Execute: never deny. If the command runs python on a chart script,
  inject additionalContext as a reminder to use the helper.

This file is byte-clean of the four codepoints the `conventions` hook
forbids (em-dash 0x2014, bullet 0x2022, emoji, and the `Npp` numeric
token) so it does not self-block.
"""

from __future__ import annotations

import json
import os
import re
import sys
from typing import Any

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _shared import (  # noqa: E402
    SHELL_TOOLS,
    allow,
    allow_with_context,
    collect_text,
    deny,
)

# Signals that the code is producing a chart.
CHART_LIB_RE = re.compile(
    r"\b("
    r"import\s+seaborn|from\s+seaborn|"
    r"import\s+matplotlib|from\s+matplotlib|"
    r"matplotlib\.pyplot|matplotlib\.use|"
    r"\bplt\.|\bsns\.|"
    r"import\s+plotly|from\s+plotly|plotly\.graph_objects|"
    r"plotly\.express|go\.Figure|px\.line|px\.bar|"
    r"datawrapper"
    r")\b",
    re.IGNORECASE,
)

# Signals that the code is already using the Adjacent helper.
ADJACENT_AWARE_RE = re.compile(
    r"adjacent_chart_style|"
    r"\badj\.PALETTE\b|\badj\.SERIES\b|\badj\.UP\b|\badj\.DOWN\b|"
    r"\badj\.apply_adjacent_theme\b|\badj\.apply_adjacent_style\b|\badj\.plotly_template\b|"
    r"\badj\.percent_formatter\b|\badj\.save\b|\badj\.source_line\b|"
    r"\badj\.figure\b|\badj\.frame\b|\badj\.y_axis\b|\badj\.area_series\b|"
    r"\badj\.last_value\b|\badj\.series_label\b|\badj\.swatch_legend\b",
    re.IGNORECASE,
)

# Hardcoded hex colors (3 or 6 digits).
HEX_RE = re.compile(r"#[0-9a-fA-F]{3}(?:[0-9a-fA-F]{3})?\b")

# Generic library palettes / colormaps that are never on-brand.
GENERIC_PALETTE_RE = re.compile(
    r"\b("
    r"viridis|plasma|inferno|magma|cividis|"
    r"tab10|tab20|tab20b|tab20c|"
    r"Set1|Set2|Set3|Paired|Pastel1|Pastel2|"
    r"muted|bright|colorblind|deep|pastel|dark|"
    r"RdBu|RdYlGn|coolwarm|jet"
    r")\b",
    re.IGNORECASE,
)

# The on-brand hex set: design-system tokens plus the chart component
# defaults shipped in Storybook (ChartRenderer cycle, TradingViewChart
# story accents). Lowercase, 6-digit, with leading #.
ADJACENT_HEX: set[str] = {
    "#" + h.lower()
    for h in (
        # tokens.css (Composer + paper tick colors)
        "ece9e2", "ffffff", "0e2a1f", "0a0f0d", "5c5a53", "7f7d7a",
        "3fae5a", "22c55e", "e66b55", "6fb7e0", "d89a3f", "a8c49a",
        "f0a8c8", "d6d2c8", "f6f5f1", "ecebea", "2a6a3a", "9b3a2e",
        # chart component defaults from Storybook
        "0e6b3a", "c0392b", "3498db", "4a90d9", "e87d2a", "b85cce",
    )
}


def _expand_hex(token: str) -> str:
    h = token[1:].lower()
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    return "#" + h


def divergent_colors(text: str) -> list[str]:
    found: list[str] = []
    for m in HEX_RE.finditer(text):
        hx = _expand_hex(m.group(0))
        if hx not in ADJACENT_HEX:
            found.append(m.group(0))
    return found


def decide(tool_name: str, tool_input: dict[str, Any]) -> dict[str, Any]:
    text = collect_text(tool_name, tool_input)
    if not text:
        return allow("chart-style: no text to scan")

    is_chart = bool(CHART_LIB_RE.search(text))
    if not is_chart:
        return allow("chart-style: no chart library detected")

    is_aware = bool(ADJACENT_AWARE_RE.search(text))

    # Shell: never deny; nudge with context.
    if tool_name in SHELL_TOOLS:
        if is_aware:
            return allow("chart-style: shell run uses adjacent_chart_style")
        return allow_with_context(
            "chart-style: allowed with guidance",
            "chart-style: this command runs a chart library. "
            "Apply the Adjacent brand: import adjacent_chart_style as adj; "
            "open the figure with adj.figure(headline=..., deck=...); use adj.SERIES / adj.UP / adj.DOWN; "
            "save via adj.save(fig, path). See the adjacent-chart-style skill.",
        )

    # Create / Edit / ApplyPatch
    generic = GENERIC_PALETTE_RE.search(text)
    if is_aware and not generic:
        return allow("chart-style: adjacent_chart_style in use")

    bad_colors = divergent_colors(text)
    if generic or (bad_colors and not is_aware):
        reasons: list[str] = []
        if generic:
            reasons.append(
                f"uses a generic library palette/colormap ({generic.group(0)}); "
                "use adj.SERIES or a token from adj.PALETTE"
            )
        if bad_colors and not is_aware:
            sample = ", ".join(sorted(set(bad_colors))[:6])
            reasons.append(
                f"hardcoded color(s) not in the Adjacent palette ({sample}); "
                "import adjacent_chart_style and use adj.PALETTE / adj.SERIES / adj.UP / adj.DOWN"
            )
        reason = (
            "blocked by adjacent/chart-style: chart code is not on-brand. "
            + "; ".join(reasons)
            + ". Load the adjacent-chart-style skill and call "
            "adj.figure() to open the chart. Do not call "
            "plt.style.use or sns.set_theme with a non-Adjacent palette."
        )
        return deny(reason)

    # Chart library present, no Adjacent signal, but no divergent colors:
    # allow and nudge toward the helper.
    return allow_with_context(
        "chart-style: allowed with guidance",
        "chart-style: chart library detected without adjacent_chart_style. "
        "For an on-brand chart, import adjacent_chart_style as adj and call "
        "adj.figure(headline=..., deck=...) to open the chart; save via adj.save(fig, path). "
        "See the adjacent-chart-style skill.",
    )


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except json.JSONDecodeError:
        json.dump(allow("chart-style: unreadable payload"), sys.stdout)
        return 0
    result = decide(payload.get("tool_name", ""), payload.get("tool_input") or {})
    json.dump(result, sys.stdout)
    return 0


if __name__ == "__main__":
    sys.exit(main())
