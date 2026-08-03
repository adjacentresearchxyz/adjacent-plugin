from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def load_hook(relative_path: str):
    path = ROOT / relative_path
    spec = importlib.util.spec_from_file_location(path.stem.replace("-", "_"), path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_mover_logger_accepts_claude_mcp_tool_name(tmp_path):
    hook = load_hook("plugins/adjacent/hooks/post-tool-use/mover-logger.py")
    hook.LOG_PATH = str(tmp_path / "movers.log")
    result = hook.emit_extra_context(
        {
            "tool_name": "mcp__adjacent_markets_dev__price",
            "tool_response": {"slug": "demo", "moves": {"1d": 0.02}},
        }
    )
    assert result is not None
    assert "demo 1d" in Path(hook.LOG_PATH).read_text(encoding="utf-8")


def test_conventions_ignore_bash_input():
    hook = load_hook("plugins/adjacent/hooks/pre-tool-use/conventions.py")
    result = hook.decide("Bash", {"command": f"printf '{chr(0x2014)}'"})
    assert result["hookSpecificOutput"]["permissionDecision"] == "allow"


def test_conventions_hook_only_launches_for_write_tools():
    manifest = json.loads(
        (
            ROOT / "plugins" / "adjacent" / ".claude-plugin" / "plugin.json"
        ).read_text(encoding="utf-8")
    )
    hook = next(
        item
        for item in manifest["hooks"]
        if item["script"].endswith("conventions.py")
    )
    assert hook["match"]["tool_name"] == ["Write", "Edit", "MultiEdit"]


def test_pre_tool_hooks_fail_open_on_invalid_json():
    for relative_path in (
        "plugins/adjacent/hooks/pre-tool-use/conventions.py",
        "plugins/adjacent/hooks/pre-tool-use/secret-redactor.py",
    ):
        proc = subprocess.run(
            [sys.executable, str(ROOT / relative_path)],
            input="{",
            capture_output=True,
            text=True,
            check=False,
        )
        assert proc.returncode == 0
        result = json.loads(proc.stdout)
        assert result["hookSpecificOutput"]["permissionDecision"] == "allow"
