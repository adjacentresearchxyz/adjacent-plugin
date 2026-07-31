#!/usr/bin/env python3
"""Pre-tool-use conventions hook for the adjacent plugin.

Reads a PreToolUse payload from stdin (the Claude Code host invokes hooks
with a JSON envelope containing tool_name and tool_input) and emits a JSON
decision on stdout.

Enforces the AGENTS.md writing rules on the *content* the model is about
to persist via Write / Edit / MultiEdit / Bash:

- no em-dash character (codepoint 0x2014); replace with ASCII hyphen or colon
- bullets must be ASCII hyphen-minus, never the unicode bullet codepoint 0x2022
- percent sign `%` only, never `pp` (percentage points) inside numeric contexts
- no emojis

A violation blocks the call with a remediation hint. The source file is
intentionally byte-clean of the four forbidden codepoints so the validation
script's self-blocker check passes.
"""

from __future__ import annotations

import json
import re
import sys
from typing import Any

EM_DASH = chr(0x2014)
BULLET_GLYPH = chr(0x2022)
PP_TOKEN_RE = re.compile(r"\b\d+(?:\.\d+)?\s*pp\b", re.IGNORECASE)
EMOJI_RANGES = (
    (0x1F100, 0x1F1FF),  # regional indicator symbols (flag emojis)
    (0x1F200, 0x1F2FF),  # enclosed ideographic supplement
    (0x1F300, 0x1FAFF),  # main emoji block
    (0x2600, 0x26FF),    # misc symbols
    (0x2700, 0x27BF),    # dingbats
    (0xFE0F, 0xFE0F),    # variation selector that composes emojis
)

WRITE_TOOLS = {"Write", "Edit", "MultiEdit"}


def is_emoji(ch: str) -> bool:
    cp = ord(ch)
    return any(lo <= cp <= hi for lo, hi in EMOJI_RANGES)


def scan_text(text: str) -> list[str]:
    findings: list[str] = []
    if EM_DASH in text:
        findings.append("contains em-dash; use ASCII hyphen or colon instead")
    if BULLET_GLYPH in text:
        findings.append("contains unicode bullet (codepoint 0x2022); use ASCII hyphen-minus instead")
    if PP_TOKEN_RE.search(text):
        findings.append("contains `pp`; use `%` (percent) instead")
    if any(is_emoji(ch) for ch in text):
        findings.append("contains an emoji; strip it")
    for line in text.splitlines():
        stripped = line.lstrip()
        if stripped.startswith(BULLET_GLYPH):
            findings.append(
                f"line starts with unicode bullet: {line[:60]!r}; replace with `-`"
            )
    return findings


def collect_text(tool_name: str, tool_input: dict[str, Any]) -> str:
    """Pull the to-be-written text out of a tool input, or the command for Bash."""
    if tool_name in WRITE_TOOLS:
        parts: list[str] = []
        if "content" in tool_input and isinstance(tool_input["content"], str):
            parts.append(tool_input["content"])
        if "new_string" in tool_input and isinstance(tool_input["new_string"], str):
            parts.append(tool_input["new_string"])
        if "edits" in tool_input and isinstance(tool_input["edits"], list):
            for e in tool_input["edits"]:
                if isinstance(e, dict) and isinstance(e.get("new_string"), str):
                    parts.append(e["new_string"])
        return "\n".join(parts)
    if tool_name == "Bash":
        cmd = tool_input.get("command", "")
        return cmd if isinstance(cmd, str) else ""
    return ""


def decide(tool_name: str, tool_input: dict[str, Any]) -> dict[str, Any]:
    text = collect_text(tool_name, tool_input)
    findings = scan_text(text)
    if not findings:
        return {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "allow",
                "permissionDecisionReason": "conventions ok",
            }
        }
    reason = "blocked by adjacent/conventions: " + "; ".join(findings)
    return {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
        }
    }


def main() -> int:
    payload = json.load(sys.stdin)
    result = decide(payload.get("tool_name", ""), payload.get("tool_input") or {})
    json.dump(result, sys.stdout)
    return 0


if __name__ == "__main__":
    sys.exit(main())
