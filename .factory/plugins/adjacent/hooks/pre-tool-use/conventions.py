#!/usr/bin/env python3
"""Pre-tool-use conventions hook for the adjacent plugin.

Reads a PreToolUse payload from stdin (the host invokes hooks with a JSON
envelope containing tool_name and tool_input) and emits a JSON decision on
stdout.

Enforces the AGENTS.md writing rules on the *content* the model is about
to persist via Create / Edit / ApplyPatch:

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
import os
import re
import sys
from typing import Any

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _shared import WRITE_TOOLS, allow, collect_new_text, deny  # noqa: E402

EM_DASH = chr(0x2014)
BULLET_GLYPH = chr(0x2022)
PP_TOKEN_RE = re.compile(r"\b\d+(?:\.\d+)?\s*pp\b", re.IGNORECASE)
# Regional indicators, enclosed ideographic supplement, the main emoji
# block, misc symbols, dingbats, and the variation selector that composes
# emojis. Written as escapes so this file stays byte-clean.
EMOJI_RE = re.compile(
    "[\U0001F100-\U0001F1FF\U0001F200-\U0001F2FF\U0001F300-\U0001FAFF"
    "\u2600-\u26FF\u2700-\u27BF\uFE0F]"
)


def scan_text(text: str) -> list[str]:
    findings: list[str] = []
    if EM_DASH in text:
        findings.append("contains em-dash; use ASCII hyphen or colon instead")
    if BULLET_GLYPH in text:
        findings.append("contains unicode bullet (codepoint 0x2022); use ASCII hyphen-minus instead")
    if PP_TOKEN_RE.search(text):
        findings.append("contains `pp`; use `%` (percent) instead")
    if EMOJI_RE.search(text):
        findings.append("contains an emoji; strip it")
    return findings


def decide(tool_name: str, tool_input: dict[str, Any]) -> dict[str, Any]:
    text = collect_new_text(tool_input) if tool_name in WRITE_TOOLS else ""
    findings = scan_text(text)
    if not findings:
        return allow("conventions ok")
    return deny("blocked by adjacent/conventions: " + "; ".join(findings))


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, TypeError):
        json.dump(
            {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "allow",
                    "permissionDecisionReason": "conventions skipped unreadable payload",
                }
            },
            sys.stdout,
        )
        return 0
    if not isinstance(payload, dict):
        payload = {}
    result = decide(payload.get("tool_name", ""), payload.get("tool_input") or {})
    json.dump(result, sys.stdout)
    return 0


if __name__ == "__main__":
    sys.exit(main())
