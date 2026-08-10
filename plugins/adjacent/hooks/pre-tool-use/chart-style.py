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
- On Write / Edit / MultiEdit:
    * chart library + Adjacent-aware signal -> allow.
    * chart library + hardcoded hex NOT in the Adjacent palette and no
      Adjacent-aware signal -> DENY with a remediation hint. This is the
      divergence guard: a script reaching for viridis / tab10 / a random
      brand color is not on-brand.
    * chart library + no hardcoded hex + no Adjacent-aware signal ->
      allow, but inject additionalContext nudging toward the helper.
    * no chart library -> allow (skip).
- On Bash: never deny. If the command runs python on a chart script,
  inject additionalContext as a reminder to use the helper.

This file is byte-clean of the four codepoints the `conventions` hook
forbids (em-dash 0x2014, bullet 0x2022, emoji, and the `Npp` numeric
token) so it does not self-block.
"""

from __future__ import annotations

import json
import re
import sys
from typing import Any

WRITE_TOOLS = {"Write", "Edit", "MultiEdit"}

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


def collect_text(tool_name: str, tool_input: dict[str, Any]) -> str:
    if tool_name == "Bash":
        cmd = tool_input.get("command", "")
        return cmd if isinstance(cmd, str) else ""
    parts: list[str] = []
    for key in ("content", "new_string"):
        v = tool_input.get(key, "")
        if isinstance(v, str):
            parts.append(v)
    if "edits" in tool_input and isinstance(tool_input["edits"], list):
        for e in tool_input["edits"]:
            if isinstance(e, dict) and isinstance(e.get("new_string"), str):
                parts.append(e["new_string"])
    return "\n".join(parts)


def divergent_colors(text: str) -> list[str]:
    found: list[str] = []
    for m in HEX_RE.finditer(text):
        hx = _expand_hex(m.group(0))
        if hx not in ADJACENT_HEX:
            found.append(m.group(0))
    return found


def uses_generic_palette(text: str) -> bool:
    return bool(GENERIC_PALETTE_RE.search(text))


def decide(tool_name: str, tool_input: dict[str, Any]) -> dict[str, Any]:
    text = collect_text(tool_name, tool_input)
    if not text:
        return _allow("chart-style: no text to scan")

    is_chart = bool(CHART_LIB_RE.search(text))
    if not is_chart:
        return _allow("chart-style: no chart library detected")

    is_aware = bool(ADJACENT_AWARE_RE.search(text))

    # Bash: never deny; nudge with context.
    if tool_name == "Bash":
        if is_aware:
            return _allow("chart-style: bash run uses adjacent_chart_style")
        return _allow_with_context(
            "chart-style: this command runs a chart library. "
            "Apply the Adjacent brand: import adjacent_chart_style as adj; "
            "open the figure with adj.figure(headline=..., deck=...); use adj.SERIES / adj.UP / adj.DOWN; "
            "save via adj.save(fig, path). See the adjacent-chart-style skill."
        )

    # Write / Edit / MultiEdit
    generics = uses_generic_palette(text)
    bad_colors = divergent_colors(text)

    if is_aware and not generics:
        return _allow("chart-style: adjacent_chart_style in use")

    if generics or (bad_colors and not is_aware):
        reasons: list[str] = []
        if generics:
            m = GENERIC_PALETTE_RE.search(text)
            reasons.append(
                f"uses a generic library palette/colormap ({m.group(0) if m else '?'}); "
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
        return _deny(reason)

    # Chart library present, no Adjacent signal, but no divergent colors:
    # allow and nudge toward the helper.
    return _allow_with_context(
        "chart-style: chart library detected without adjacent_chart_style. "
        "For an on-brand chart, import adjacent_chart_style as adj and call "
        "adj.figure(headline=..., deck=...) to open the chart; save via adj.save(fig, path). "
        "See the adjacent-chart-style skill."
    )


def _allow(reason: str) -> dict[str, Any]:
    return {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "allow",
            "permissionDecisionReason": reason,
        }
    }


def _allow_with_context(context: str) -> dict[str, Any]:
    return {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "allow",
            "permissionDecisionReason": "chart-style: allowed with guidance",
            "additionalContext": context,
        }
    }


def _deny(reason: str) -> dict[str, Any]:
    return {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
        }
    }


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except json.JSONDecodeError:
        json.dump(_allow("chart-style: unreadable payload"), sys.stdout)
        return 0
    try:
        result = decide(payload.get("tool_name", ""), payload.get("tool_input") or {})
    except Exception:
        result = _allow("chart-style: unexpected error")
    json.dump(result, sys.stdout)
    return 0


if __name__ == "__main__":
    sys.exit(main())
