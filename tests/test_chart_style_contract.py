"""Contract tests for the canonical Adjacent charting spec.

These tests keep the chart-style helper, ``AGENTS.md``, and the three
host chart-style skill copies synchronized. The helper is the source of
truth; the skills and docs describe it. If any of them drift, a test
here fails before an agent ships the wrong palette, source line, or
label rule.

Follows the standard-library + pytest style of ``test_offline_signals``
and ``test_factory_hooks``: load the helper by path and read skill files
with ``pathlib``. No matplotlib import is required for the contract
checks, so the suite runs under system ``python3`` with no extras.
"""

from __future__ import annotations

import inspect
import importlib.util
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HELPER = ROOT / "scripts" / "adjacent_chart_style.py"

HOST_SKILLS = [
    ROOT / ".factory" / "skills" / "adjacent-chart-style" / "SKILL.md",
    ROOT / ".hermes" / "plugins" / "adjacent" / "skills" / "adjacent-chart-style" / "SKILL.md",
    ROOT / "plugins" / "adjacent" / "skills" / "adjacent-chart-style" / "SKILL.md",
]

CHARTING_DOC = ROOT / "docs" / "charting-plugin-update.md"


def _load_helper():
    scripts_path = str(HELPER.parent)
    if scripts_path not in sys.path:
        sys.path.insert(0, scripts_path)
    spec = importlib.util.spec_from_file_location("adjacent_chart_style", HELPER)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# -------------------------------------------------------------------
# Helper API shape and canonical defaults
# -------------------------------------------------------------------


def test_helper_exports_canonical_defaults():
    adj = _load_helper()
    assert adj.SOURCE_DEFAULT == "Adjacent"
    # The series cycle is the ChartRenderer default, in order.
    assert adj.SERIES == [
        "#3fae5a",  # chart-green
        "#e87d2a",  # chart-orange
        "#4a90d9",  # chart-blue
        "#b85cce",  # chart-purple
        "#a8c49a",  # sage
        "#f0a8c8",  # pink
    ]
    # A lone line is off-black, never colored by direction.
    assert adj.LINE == "#0a0f0d"
    # Directional colors come from the design-system tokens.
    assert adj.UP == "#3fae5a"
    assert adj.DOWN == "#c0392b"


def test_helper_palette_keys_match_design_tokens():
    adj = _load_helper()
    p = adj.PALETTE
    for key in ("canvas", "paper", "ink", "deep", "green", "rule", "grid",
                "fg-2", "fg-3"):
        assert key in p, f"missing palette key: {key}"
    assert p["canvas"] == "#ece9e2"
    assert p["ink"] == "#0a0f0d"
    assert p["deep"] == "#0e2a1f"
    assert p["rule"] == "#d6d2c8"
    assert p["grid"] == "#ecebea"


def test_helper_font_stacks_match_design_generics():
    adj = _load_helper()
    # Inter is the only face the site loads; serif / mono are the CSS
    # generics, so the stacks lead with what those resolve to. The
    # helper must NOT claim Lora or IBM Plex Mono.
    assert "Inter" == adj.FONTS["main"][0]
    assert adj.FONTS["serif"][0] != "Lora"
    assert adj.FONTS["mono"][0] != "IBM Plex Mono"
    assert adj.FONTS["serif"][-1] == "serif"
    assert adj.FONTS["mono"][-1] == "monospace"


def test_helper_formatting_functions_exist():
    adj = _load_helper()
    for name in ("percent_formatter", "currency_formatter",
                 "number_formatter", "apply_adjacent_theme",
                 "apply_adjacent_style", "figure", "frame", "y_axis",
                 "format_date_axis", "save", "source_line",
                 "swatch_legend", "area_series", "heikin_ashi",
                 "heikin_ashi_transform", "plotly_template"):
        assert callable(getattr(adj, name, None)), f"missing export: {name}"


def test_save_signature_has_no_reserve_params():
    """save() measures its own chrome; it has no reserve_bottom/right."""
    adj = _load_helper()
    params = inspect.signature(adj.save).parameters
    assert "source" in params
    assert "dpi" in params
    assert "reserve_bottom" not in params
    assert "reserve_right" not in params


def test_source_line_signature_is_text_only():
    adj = _load_helper()
    params = inspect.signature(adj.source_line).parameters
    assert list(params) == ["fig", "text"]
    # The default stamps exactly "Adjacent" - no timestamp baked in.
    assert params["text"].default == "Adjacent"


def test_heikin_ashi_transform_matches_house_formulas():
    adj = _load_helper()
    ha = adj.heikin_ashi_transform(
        opens=[10, 11], highs=[12, 13], lows=[9, 10], closes=[11, 12],
    )
    # First HA-open = (O+C)/2 = 10.5; HA-close = (10+12+9+11)/4 = 10.5
    assert ha[0] == (10.5, 12.0, 9.0, 10.5)
    # Second HA-open = (10.5+10.5)/2 = 10.5; HA-close = 11.5
    assert ha[1][0] == 10.5
    assert ha[1][3] == 11.5


# -------------------------------------------------------------------
# Host skill presence and cross-host references
# -------------------------------------------------------------------


def test_three_host_chart_skill_copies_exist():
    assert HOST_SKILLS, "HOST_SKILLS must list the three host copies"
    for path in HOST_SKILLS:
        assert path.is_file(), f"missing host chart skill: {path}"


def test_host_skills_are_synchronized():
    """All three host copies must agree byte-for-byte."""
    texts = [p.read_text(encoding="utf-8") for p in HOST_SKILLS]
    assert texts[0] == texts[1], ".factory and .hermes chart skills differ"
    assert texts[1] == texts[2], ".hermes and plugins chart skills differ"


def test_each_host_skill_references_repository_relative_helper():
    rel = "scripts/adjacent_chart_style.py"
    for path in HOST_SKILLS:
        text = path.read_text(encoding="utf-8")
        assert rel in text, f"{path} does not reference {rel}"


def test_no_host_skill_presents_opt_data_as_only_canonical_path():
    """An absolute /opt/data path may appear as an example, but the
    repository-relative path must also appear so it is not the only
    canonical path."""
    rel = "scripts/adjacent_chart_style.py"
    for path in HOST_SKILLS:
        text = path.read_text(encoding="utf-8")
        if "/opt/data/adjacent-plugin" in text:
            assert rel in text, (
                f"{path} cites /opt/data/adjacent-plugin without the "
                "repository-relative helper path"
            )
        # The skill must never inline the helper source as a code block
        # that re-defines PALETTE / SERIES from scratch.
        assert "SOURCE_DEFAULT = \"Adjacent\"" not in text, (
            f"{path} inlines the helper API; reference it instead"
        )


def test_host_skills_state_resolved_source_line_rule():
    for path in HOST_SKILLS:
        text = path.read_text(encoding="utf-8")
        assert "Source: Adjacent" in text
        # No timestamp baked into the source contract.
        assert "UTC" not in text.split("Resolved rules")[1].split("\n\n")[0]


def test_host_skills_state_resolved_series_cycle():
    for path in HOST_SKILLS:
        text = path.read_text(encoding="utf-8")
        assert "SERIES" in text
        # The resolved cycle lists green first, never a deep-green-only cycle.
        assert "chart-orange" in text or "#e87d2a" in text


def test_host_skills_state_mid_quote_and_heikin_ashi_rules():
    for path in HOST_SKILLS:
        text = path.read_text(encoding="utf-8")
        assert "Heikin-Ashi" in text
        assert "mid-quote" in text or "mid quote" in text.lower()


def test_agents_md_states_resolved_chart_rules():
    text = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "scripts/adjacent_chart_style.py" in text
    assert "Source: Adjacent" in text
    assert "SERIES" in text
    assert "Heikin-Ashi" in text
    assert "precedence" in text.lower()


# -------------------------------------------------------------------
# Charting companion document
# -------------------------------------------------------------------


def test_charting_doc_exists_and_uses_repository_relative_paths():
    assert CHARTING_DOC.is_file(), "docs/charting-plugin-update.md missing"
    text = CHARTING_DOC.read_text(encoding="utf-8")
    assert "scripts/adjacent_chart_style.py" in text
    # The doc must mark /opt/data paths as deployment examples, not
    # present them as the canonical location.
    if "/opt/data" in text:
        assert "deployment" in text.lower() or "example" in text.lower()
    # The doc must not claim Lora or IBM Plex Mono as the brand fonts.
    assert "Lora" not in text
    assert "IBM Plex Mono" not in text
    # The doc must not claim the helper is 512 lines.
    assert "512 lines" not in text
