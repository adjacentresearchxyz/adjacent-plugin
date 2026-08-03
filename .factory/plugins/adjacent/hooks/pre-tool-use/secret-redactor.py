#!/usr/bin/env python3
"""Pre-tool-use secret-redactor hook for the adjacent plugin.

Two responsibilities, per AGENTS.md:

1. Block Execute commands that would print any Adjacent/Kalshi/Datawrapper/Dune
   secret to stdout (e.g. `echo $KALSHI_API_KEY`, `cat ~/.kalshi/kalshi_rsa.key`,
   `curl -H "Authorization: Bearer $DATAWRAPPER_API_KEY" ... | head`).

2. Block Create/Edit/ApplyPatch calls whose new text matches a *literal* secret
   value. `process.env.ADJACENT_API_KEY` template references are allowed (the
   host substitutes at runtime); raw sk_live_*/dwk_*/Bearer strings are not.

Reads PreToolUse JSON on stdin, writes JSON decision on stdout.
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
    WRITE_TOOLS,
    allow,
    collect_command,
    collect_new_text,
    deny,
)

BLOCKED_ENV = (
    "ADJACENT_API_KEY",
    "KALSHI_API_KEY",
    "KALSHI_PASSPHRASE",
    "KALSHI_RSA_KEY_PATH",
    "DATAWRAPPER_API_KEY",
    "MCP_DUNE_API_KEY",
)
ENV_NAME = "(" + "|".join(BLOCKED_ENV) + ")"

# Shell commands that would print a secret value if the runner expanded the env var.
PRINT_PATTERNS = (
    re.compile(r"\becho\b[^\n]*\${?" + ENV_NAME + r"}?"),
    re.compile(r"\bcat\b[^\n]*\${?(?:" + ENV_NAME + r")\}?"),
    re.compile(r"\bprintenv\b[^\n]*(?:" + ENV_NAME + r")"),
    re.compile(r"\benv\b\s*\|"),
    re.compile(r"\bhead\b[^\n]*\${?(?:" + ENV_NAME + r")\}?"),
)

# Files that hold secrets; reading them is suspicious regardless of the verb.
FILE_PATH_PATTERNS = (
    re.compile(r"~/?\.kalshi/.*\.key\b"),
    re.compile(r"~/?\.kalshi/kalshi_rsa"),
)

# Token shapes that strongly suggest a *raw* value being pasted in (not a template)
RAW_VALUE_PATTERNS = (
    re.compile(r"\bsk_live_[A-Za-z0-9]{20,}\b"),                   # Kalshi-API style
    re.compile(r"\bdwk_[A-Za-z0-9]{20,}\b"),                       # Datawrapper
    re.compile(r"\bbearer\s+[A-Za-z0-9_\-\.=]{32,}\b", re.IGNORECASE),
    re.compile(r"\b-----BEGIN [A-Z ]*PRIVATE KEY-----"),          # PEM key body
)


def is_shell_secret_leak(command: str) -> str | None:
    for pat in PRINT_PATTERNS:
        if pat.search(command):
            return f"Execute command matches secret-print pattern: {pat.pattern[:60]}"
    for pat in FILE_PATH_PATTERNS:
        if pat.search(command):
            return f"Execute command touches a key file: {pat.pattern}"
    if re.search(r"\b(open|less|more|awk|sed|tee|cp)\b[^\n]*(?:\.kalshi|kalshi_rsa)", command):
        return "Execute command attempts to read a Kalshi key file"
    return None


def is_raw_secret_in_text(text: str) -> str | None:
    for pat in RAW_VALUE_PATTERNS:
        m = pat.search(text)
        if m:
            return f"raw secret token detected (pattern prefix: {pat.pattern[:40]})"
    return None


def decide(tool_name: str, tool_input: dict[str, Any]) -> dict[str, Any]:
    if tool_name in SHELL_TOOLS:
        reason = is_shell_secret_leak(collect_command(tool_input))
        if reason:
            return deny(reason)
        return allow("no secret-print pattern")
    if tool_name in WRITE_TOOLS:
        reason = is_raw_secret_in_text(collect_new_text(tool_input))
        if reason:
            return deny(reason)
        return allow("no raw secret in text")
    return allow("redactor skipped non-target tool")


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, TypeError):
        json.dump(allow("redactor skipped unreadable payload"), sys.stdout)
        return 0
    if not isinstance(payload, dict):
        payload = {}
    result = decide(payload.get("tool_name", ""), payload.get("tool_input") or {})
    json.dump(result, sys.stdout)
    return 0


if __name__ == "__main__":
    sys.exit(main())
