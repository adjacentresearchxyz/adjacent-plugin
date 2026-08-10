#!/usr/bin/env python3
"""Post-tool-use secret-scrubber hook for the adjacent plugin.

Defense-in-depth: the pre-tool-use `secret-redactor` blocks commands that
would print secrets, but any secret that slips past the pre-tool-use check
ends up in stdout/stderr and is persisted verbatim. This hook scans tool
output for raw secret patterns and reports redaction via `additionalContext`.

The hook cannot reliably rewrite output on every host, so it signals the
agent and operator that scrubbing was needed rather than silently mutating
the captured stream.

Reads PostToolUse JSON on stdin, writes JSON response on stdout.
"""

from __future__ import annotations

import json
import re
import sys
from typing import Any

# Combined raw secret-value pattern. Single regex pass is more efficient
# than iterating 4 separate patterns. Must stay in sync with the pre-tool-use
# `secret-redactor.py` RAW_VALUE_PATTERNS.
_COMBINED_PATTERN = re.compile(
    r"\bsk_live_[A-Za-z0-9]{20,}\b"
    r"|\bdwk_[A-Za-z0-9]{20,}\b"
    r"|\bbearer\s+[A-Za-z0-9_\-\.=]{32,}\b"
    r"|\b-----BEGIN [A-Z ]*PRIVATE KEY-----",
    re.IGNORECASE,
)

REDACTED = "[REDACTED]"


def _redact(text: str) -> tuple[str, int]:
    """Replace every raw secret match with [REDACTED]. Return (text, count)."""
    return _COMBINED_PATTERN.subn(REDACTED, text)


def scrub_output(payload: dict[str, Any]) -> dict[str, Any] | None:
    """Scan tool_response stdout/stderr for raw secrets.

    Returns a hook response dict when redaction occurred, else None.
    """
    tool_response = payload.get("tool_response")
    if not isinstance(tool_response, dict):
        return None
    total = 0
    for field in ("stdout", "stderr", "output", "content", "result"):
        value = tool_response.get(field)
        if not isinstance(value, str):
            continue
        _, n = _redact(value)
        total += n
    if total == 0:
        return None
    return {
        "hookSpecificOutput": {
            "hookEventName": "PostToolUse",
            "additionalContext": (
                f"secret-scrubber: redacted {total} secret value(s) "
                f"from tool output; replaced with {REDACTED}"
            ),
        }
    }


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, TypeError):
        json.dump({"continue": True}, sys.stdout)
        return 0
    if not isinstance(payload, dict):
        payload = {}
    try:
        result = scrub_output(payload)
    except Exception:
        result = None
    if result is None:
        json.dump({"continue": True}, sys.stdout)
    else:
        json.dump(result, sys.stdout)
    return 0


if __name__ == "__main__":
    sys.exit(main())
