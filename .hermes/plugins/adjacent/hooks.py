"""hooks.py - Hermes pre_tool_call hook for the Adjacent plugin.

The hook enforces the hard AGENTS.md output rules on the *content* a
tool is about to persist via write-capable tools (Write, Edit,
MultiEdit). It blocks:

- the em-dash codepoint (U+2014): use ASCII hyphen or colon instead
- the unicode bullet codepoint (U+2022): use ASCII hyphen-minus
- the `pp` abbreviation (percentage points) when it follows a number:
  use `%` instead
- emoji codepoints

Scope and false-positive avoidance:

- Only write-capable tools are scanned on the *content to be written*.
  Bash commands and arbitrary read-only tool input are NOT scanned for
  em-dash / bullet / pp, because those characters appear legitimately in
  shell pipelines, URLs, and existing file contents that a tool might
  reference. This keeps the hook from false-blocking arbitrary input.
- The `pp` check is anchored to a number (`\\d+pp`) so common English
  words (e.g. "approach", "happen") never trip it.
- A violation DENIES the call with a remediation hint. A clean payload
  ALLOWS it. An unreadable payload ALLOWS it (fail-open for the host so
  a malformed envelope never wedges the agent).

The hook is importable and callable as pre_tool_call(payload) so unit
tests can exercise it with no Hermes installation. A main() CLI entry
is provided for hosts that invoke hooks as subprocesses.

Conventions: this file is byte-clean of the four forbidden codepoints
so it does not self-block.
"""

from __future__ import annotations

import json
import re
import sys
from typing import Any

EM_DASH = chr(0x2014)
BULLET_GLYPH = chr(0x2022)
# Anchored to a number so English words like "approach" / "happen" do
# not trip the check.
PP_TOKEN_RE = re.compile(r"\b\d+(?:\.\d+)?\s*pp\b", re.IGNORECASE)
EMOJI_RANGES = (
    (0x1F100, 0x1F1FF),
    (0x1F200, 0x1F2FF),
    (0x1F300, 0x1FAFF),
    (0x2600, 0x26FF),
    (0x2700, 0x27BF),
    (0xFE0F, 0xFE0F),
)

# Only these tools have a "content to be written" surface. Scoping here
# is the primary false-positive guard: we never scan arbitrary tool
# input (e.g. Bash commands, Read paths) for the forbidden codepoints.
WRITE_TOOLS = {"Write", "Edit", "MultiEdit"}


def _is_emoji(ch: str) -> bool:
    cp = ord(ch)
    return any(lo <= cp <= hi for lo, hi in EMOJI_RANGES)


def scan_text(text: str) -> list[str]:
    """Return a list of violation descriptions for the given text."""
    findings: list[str] = []
    if EM_DASH in text:
        findings.append("contains em-dash (U+2014); use ASCII hyphen or colon instead")
    if BULLET_GLYPH in text:
        findings.append("contains unicode bullet (U+2022); use ASCII hyphen-minus instead")
    if PP_TOKEN_RE.search(text):
        findings.append("contains `pp` (percentage points); use `%` instead")
    if any(_is_emoji(ch) for ch in text):
        findings.append("contains an emoji; strip it")
    return findings


def collect_text(tool_name: str, tool_input: dict[str, Any]) -> str:
    """Pull the to-be-written text out of a write-capable tool input.

    Returns an empty string for any tool that is not write-capable, so
    the hook never inspects arbitrary tool input."""
    if tool_name not in WRITE_TOOLS:
        return ""
    parts: list[str] = []
    content = tool_input.get("content")
    if isinstance(content, str):
        parts.append(content)
    new_string = tool_input.get("new_string")
    if isinstance(new_string, str):
        parts.append(new_string)
    edits = tool_input.get("edits")
    if isinstance(edits, list):
        for e in edits:
            if isinstance(e, dict) and isinstance(e.get("new_string"), str):
                parts.append(e["new_string"])
    return "\n".join(parts)


def _allow(reason: str) -> dict[str, Any]:
    return {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "allow",
            "permissionDecisionReason": reason,
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


def pre_tool_call(payload: dict[str, Any]) -> dict[str, Any]:
    """Decide allow/deny for a PreToolUse event.

    payload shape: {"tool_name": str, "tool_input": dict, ...}
    """
    tool_name = payload.get("tool_name", "") or ""
    tool_input = payload.get("tool_input") or {}
    if not isinstance(tool_input, dict):
        tool_input = {}
    if tool_name not in WRITE_TOOLS:
        return _allow("adjacent/conventions: not a write-capable tool; skip")
    text = collect_text(tool_name, tool_input)
    if not text:
        return _allow("adjacent/conventions: no write content to scan")
    findings = scan_text(text)
    if not findings:
        return _allow("adjacent/conventions: content ok")
    reason = "blocked by adjacent/conventions: " + "; ".join(findings)
    return _deny(reason)


def main() -> int:
    """CLI entry for hosts that invoke hooks as subprocesses. Reads a
    JSON payload from stdin, writes a JSON decision to stdout."""
    raw = sys.stdin.read()
    try:
        payload = json.loads(raw) if raw.strip() else {}
    except json.JSONDecodeError:
        json.dump(_allow("adjacent/conventions: unreadable payload"), sys.stdout)
        return 0
    result = pre_tool_call(payload)
    json.dump(result, sys.stdout)
    return 0


if __name__ == "__main__":
    sys.exit(main())
