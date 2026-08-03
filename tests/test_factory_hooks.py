from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from tests._hookutil import ROOT, load_hook

PACKAGE = ".factory"
EM_DASH = chr(0x2014)


def conventions():
    return load_hook(f"{PACKAGE}/hooks/pre-tool-use/conventions.py")


def redactor():
    return load_hook(f"{PACKAGE}/hooks/pre-tool-use/secret-redactor.py")


def chart_style():
    return load_hook(f"{PACKAGE}/hooks/pre-tool-use/chart-style.py")


def decision(result: dict) -> str:
    return result["hookSpecificOutput"]["permissionDecision"]


def test_conventions_blocks_em_dash_in_created_file():
    result = conventions().decide("Create", {"content": f"a {EM_DASH} b"})
    assert decision(result) == "deny"


def test_conventions_ignores_pre_edit_text():
    """Removing an em-dash requires naming it in the old text."""
    result = conventions().decide(
        "Edit",
        {"old_string": f"a {EM_DASH} b", "new_string": "a - b"},
    )
    assert decision(result) == "allow"


def test_conventions_judges_a_patch_on_its_added_lines():
    hook = conventions()
    removal_only = "@@ -1,2 +1,2 @@\n-old {dash} line\n+new - line\n".format(dash=EM_DASH)
    assert decision(hook.decide("ApplyPatch", {"patch": removal_only})) == "allow"

    addition = "@@ -1,2 +1,2 @@\n-old - line\n+new {dash} line\n".format(dash=EM_DASH)
    assert decision(hook.decide("ApplyPatch", {"patch": addition})) == "deny"


def test_conventions_ignores_shell_input():
    result = conventions().decide("Execute", {"command": f"printf '{EM_DASH}'"})
    assert decision(result) == "allow"


def test_conventions_blocks_percentage_point_token():
    result = conventions().decide("Create", {"content": "tracking error 4 pp"})
    assert decision(result) == "deny"


def test_redactor_blocks_secret_print_on_execute():
    result = redactor().decide("Execute", {"command": "echo $KALSHI_API_KEY"})
    assert decision(result) == "deny"


def test_redactor_blocks_raw_secret_in_new_file():
    result = redactor().decide(
        "Create", {"content": "KEY = 'sk_live_" + "a" * 24 + "'"}
    )
    assert decision(result) == "deny"


def test_redactor_allows_env_template_reference():
    result = redactor().decide(
        "Create", {"content": "key = process.env.ADJACENT_API_KEY"}
    )
    assert decision(result) == "allow"


def test_chart_style_denies_generic_palette_on_write():
    result = chart_style().decide(
        "Create", {"content": "import seaborn as sns\nsns.set_palette('viridis')"}
    )
    assert decision(result) == "deny"


def test_chart_style_never_denies_on_execute():
    result = chart_style().decide(
        "Execute", {"command": "python3 plot.py  # import matplotlib"}
    )
    assert decision(result) == "allow"
    assert "additionalContext" in result["hookSpecificOutput"]


def test_chart_style_allows_adjacent_aware_code():
    result = chart_style().decide(
        "Create",
        {"content": "import matplotlib\nimport adjacent_chart_style as adj\nadj.figure()"},
    )
    assert decision(result) == "allow"


def test_mover_logger_accepts_mcp_tool_name(tmp_path):
    hook = load_hook(f"{PACKAGE}/hooks/post-tool-use/mover-logger.py")
    hook.LOG_PATH = str(tmp_path / "movers.log")
    result = hook.emit_extra_context(
        {
            "tool_name": "mcp__adjacent-markets-dev__price",
            "tool_response": {"slug": "demo", "moves": {"1d": 0.02}},
        }
    )
    assert result is not None
    assert "demo 1d" in Path(hook.LOG_PATH).read_text(encoding="utf-8")


def test_pre_tool_hooks_fail_open_on_invalid_json():
    for name in ("conventions.py", "secret-redactor.py", "chart-style.py"):
        proc = subprocess.run(
            [sys.executable, str(ROOT / PACKAGE / "hooks/pre-tool-use" / name)],
            input="not json",
            capture_output=True,
            text=True,
            check=True,
        )
        payload = json.loads(proc.stdout)
        assert payload["hookSpecificOutput"]["permissionDecision"] == "allow"
