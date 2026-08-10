#!/usr/bin/env python3
"""Pre-tool-use secret-redactor hook for the adjacent plugin.

Two responsibilities, per AGENTS.md:

1. Block Bash commands that would print any Adjacent/Kalshi/Datawrapper/Dune
   secret to stdout (e.g. `echo $KALSHI_API_KEY`, `cat ~/.kalshi/kalshi_rsa.key`,
   `curl -H "Authorization: Bearer $DATAWRAPPER_API_KEY" ... | head`).

2. Block Write/Edit commands whose `content` matches a *literal* secret value.
   `process.env.ADJACENT_API_KEY` template references are allowed (the host
   substitutes at runtime); raw sk_live_*/dwk_*/Bearer strings are not.

Reads PreToolUse JSON on stdin, writes JSON decision on stdout.
"""

from __future__ import annotations

import json
import re
import sys
from typing import Any

BLOCKED_ENV = (
    "ADJACENT_API_KEY",
    "KALSHI_API_KEY",
    "KALSHI_PASSPHRASE",
    "KALSHI_RSA_KEY_PATH",
    "DATAWRAPPER_API_KEY",
    "MCP_DUNE_API_KEY",
)
ENV_NAME = "(" + "|".join(BLOCKED_ENV) + ")"

# Bash commands that would print a secret value if the runner expanded the env var.
PRINT_PATTERNS = (
    re.compile(r"\becho\b[^\n]*\${?" + ENV_NAME + r"}?"),
    re.compile(r"\bcat\b[^\n]*\${?(?:" + ENV_NAME + r")\}?"),
    re.compile(r"\bprintenv\b[^\n]*(?:" + ENV_NAME + r")"),
    re.compile(r"\benv\b\s*\|"),
    re.compile(r"\bhead\b[^\n]*\${?(?:" + ENV_NAME + r")\}?"),
    # Catch-all: block any command that references a blocked env var,
    # regardless of the command verb. This catches printf, python, curl,
    # base64, strings, xxd, tail, and any other exfiltration vector.
    re.compile(r"\${?" + ENV_NAME + r"}?"),
    # Block bare env var names too - covers programmatic reads such as
    # python "os.environ['KALSHI_API_KEY']" that do not use $ expansion.
    re.compile(ENV_NAME),
    # printenv with no arguments prints ALL env vars including secrets.
    re.compile(r"\bprintenv\b\s*$"),
    # env with no pipe also prints all env vars.
    re.compile(r"\benv\b\s*$"),
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


def is_bash_secret_leak(command: str) -> str | None:
    for pat in PRINT_PATTERNS:
        if pat.search(command):
            return f"Bash command matches secret-print pattern: {pat.pattern[:60]}"
    for pat in FILE_PATH_PATTERNS:
        if pat.search(command):
            return f"Bash command touches a key file: {pat.pattern}"
    if re.search(r"\b(open|less|more|awk|sed|tee|cp)\b[^\n]*(?:\.kalshi|kalshi_rsa)", command):
        return "Bash command attempts to read a Kalshi key file"
    return None


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


def is_raw_secret_in_text(text: str) -> str | None:
    for pat in RAW_VALUE_PATTERNS:
        m = pat.search(text)
        if m:
            return f"raw secret token detected (pattern prefix: {pat.pattern[:40]})"
    return None


def decide(tool_name: str, tool_input: dict[str, Any]) -> dict[str, Any]:
    if tool_name == "Bash":
        reason = is_bash_secret_leak(tool_input.get("command", "") or "")
        if reason:
            return {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "deny",
                    "permissionDecisionReason": reason,
                }
            }
        return {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "allow",
                "permissionDecisionReason": "no secret-print pattern",
            }
        }
    if tool_name in {"Write", "Edit", "MultiEdit"}:
        text = collect_text(tool_name, tool_input)
        reason = is_raw_secret_in_text(text)
        if reason:
            return {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "deny",
                    "permissionDecisionReason": reason,
                }
            }
        return {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "allow",
                "permissionDecisionReason": "no raw secret in text",
            }
        }
    return {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "allow",
            "permissionDecisionReason": "redactor skipped non-target tool",
        }
    }


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, TypeError):
        json.dump(
            {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "allow",
                    "permissionDecisionReason": "redactor skipped unreadable payload",
                }
            },
            sys.stdout,
        )
        return 0
    if not isinstance(payload, dict):
        payload = {}
    try:
        result = decide(payload.get("tool_name", ""), payload.get("tool_input") or {})
    except Exception:
        result = {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "allow",
                "permissionDecisionReason": "redactor skipped unexpected error",
            }
        }
    json.dump(result, sys.stdout)
    return 0


if __name__ == "__main__":
    sys.exit(main())
