"""Skill discovery contract: Use-when descriptions and session bootstrap.

Agents decide whether to load a skill from the YAML description alone.
A description that summarizes the workflow becomes a shortcut they
follow instead of reading the body. These tests keep every shared
skill on triggering conditions, and keep the session-start hook
injecting using-adjacent.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

from tests._hookutil import ROOT, load_hook


CANONICAL_SKILLS = ROOT / "plugins" / "adjacent" / "skills"
FACTORY_SKILLS = ROOT / ".factory" / "skills"
HERMES_SKILLS = ROOT / ".hermes" / "plugins" / "adjacent" / "skills"

WORKFLOW_SUMMARY_MARKERS = (
    "drives the",
    "includes the",
    "mirrors the",
    "pulls news",
    "scripts and commands depend",
    "apply before any chart",
)

SESSION_START_SCRIPTS = (
    ROOT / "plugins" / "adjacent" / "hooks" / "session-start.py",
    ROOT / ".factory" / "hooks" / "session-start.py",
)


def _skill_dirs() -> list[Path]:
    return [
        path
        for path in CANONICAL_SKILLS.iterdir()
        if path.is_dir() and (path / "SKILL.md").is_file()
    ]


def skill_description(text: str) -> str:
    """Return the YAML description, including folded `>` / `|` scalars."""
    if not text.startswith("---"):
        return ""
    lines = text.splitlines()
    end = next(
        (i for i, line in enumerate(lines[1:], 1) if line.strip() == "---"),
        None,
    )
    if end is None:
        return ""
    collected: list[str] = []
    in_desc = False
    for line in lines[1:end]:
        if line.startswith("description:"):
            rest = line.split(":", 1)[1].strip()
            if rest in {">", "|", ""}:
                in_desc = True
                continue
            return rest.strip('"').strip("'")
        if in_desc:
            if re.match(r"^[A-Za-z0-9_-]+:", line):
                break
            collected.append(line.strip())
    return " ".join(part for part in collected if part)


def test_using_adjacent_skill_exists():
    path = CANONICAL_SKILLS / "using-adjacent" / "SKILL.md"
    assert path.is_file(), "missing using-adjacent skill"


def test_every_shared_skill_description_starts_with_use_when():
    missing = []
    for directory in _skill_dirs():
        text = (directory / "SKILL.md").read_text(encoding="utf-8")
        description = skill_description(text)
        if not description.lower().startswith("use when"):
            missing.append(f"{directory.name}: {description[:80]!r}")
    assert missing == [], "skill descriptions must start with Use when:\n" + "\n".join(
        missing
    )


def test_descriptions_are_triggers_not_workflow_summaries():
    offenders = []
    for directory in _skill_dirs():
        text = (directory / "SKILL.md").read_text(encoding="utf-8")
        description = skill_description(text).lower()
        for marker in WORKFLOW_SUMMARY_MARKERS:
            if marker in description:
                offenders.append(f"{directory.name}: {marker!r}")
    assert offenders == [], "descriptions summarize workflow:\n" + "\n".join(offenders)


def test_using_adjacent_requires_fresh_evidence_and_skill_load():
    text = (CANONICAL_SKILLS / "using-adjacent" / "SKILL.md").read_text(
        encoding="utf-8"
    )
    lowered = text.lower()
    assert "adjacent-workflows" in lowered
    assert "never invent" in lowered
    assert "fresh" in lowered
    assert "price" in lowered
    assert "before" in lowered


def test_session_start_scripts_exist_and_match():
    texts = []
    for path in SESSION_START_SCRIPTS:
        assert path.is_file(), f"missing session-start hook: {path}"
        texts.append(path.read_bytes())
    assert texts[0] == texts[1], "Claude and Factory session-start.py drifted"


def test_session_start_injects_using_adjacent(monkeypatch):
    hook = load_hook("plugins/adjacent/hooks/session-start.py")
    payload = hook.envelope(hook.additional_context(hook.skill_text()))
    context = payload["hookSpecificOutput"]["additionalContext"]
    assert payload["hookSpecificOutput"]["hookEventName"] == "SessionStart"
    assert "using-adjacent" in context.lower()
    assert "Use when" in context


def test_session_start_cli_emits_json():
    script = SESSION_START_SCRIPTS[0]
    proc = subprocess.run(
        [sys.executable, str(script)],
        capture_output=True,
        text=True,
        check=True,
        cwd=str(ROOT),
        env={**os.environ},
    )
    payload = json.loads(proc.stdout)
    context = payload["hookSpecificOutput"]["additionalContext"]
    assert "using-adjacent" in context.lower()


def test_session_start_fail_open_when_skill_missing(tmp_path, monkeypatch):
    hook = load_hook("plugins/adjacent/hooks/session-start.py")
    monkeypatch.setattr(hook, "plugin_root", lambda: tmp_path)
    payload = hook.build_payload()
    assert payload.get("continue") is True


def test_claude_manifest_registers_session_start():
    manifest = json.loads(
        (ROOT / "plugins" / "adjacent" / ".claude-plugin" / "plugin.json").read_text(
            encoding="utf-8"
        )
    )
    events = [item.get("event") for item in manifest["hooks"]]
    assert "SessionStart" in events
    session = next(item for item in manifest["hooks"] if item["event"] == "SessionStart")
    assert session["script"].endswith("session-start.py")


def test_factory_hooks_register_session_start():
    hooks = json.loads(
        (ROOT / ".factory" / "hooks" / "hooks.json").read_text(encoding="utf-8")
    )["hooks"]
    assert "SessionStart" in hooks
    commands = [
        entry["command"]
        for group in hooks["SessionStart"]
        for entry in group["hooks"]
    ]
    assert any("session-start.py" in command for command in commands)


def test_cursor_using_adjacent_rule_always_applies():
    path = ROOT / ".cursor" / "rules" / "using-adjacent.mdc"
    assert path.is_file()
    text = path.read_text(encoding="utf-8")
    assert "alwaysApply: true" in text
    assert "using-adjacent" in text.lower() or "load the matching" in text.lower()
    assert "never invent" in text.lower()


def test_using_adjacent_is_mirrored_to_host_packages():
    source = (CANONICAL_SKILLS / "using-adjacent" / "SKILL.md").read_bytes()
    for path in (
        FACTORY_SKILLS / "using-adjacent" / "SKILL.md",
        HERMES_SKILLS / "using-adjacent" / "SKILL.md",
    ):
        assert path.is_file(), f"missing host copy: {path}"
        assert path.read_bytes() == source
