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
import os
import re
import sys
from datetime import datetime, timezone
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

BLOCKED_ENV = (
    "ADJACENT_API_KEY",
    "KALSHI_API_KEY",
    "KALSHI_PASSPHRASE",
    "KALSHI_RSA_KEY_PATH",
    "DATAWRAPPER_API_KEY",
    "MCP_DUNE_API_KEY",
)
ENV_NAME = "(" + "|".join(BLOCKED_ENV) + ")"
PRINT_PATTERNS = (
    re.compile(r"\becho\b[^\n]*\${?" + ENV_NAME + r"}?"),
    re.compile(r"\bcat\b[^\n]*\${?(?:" + ENV_NAME + r")\}?"),
    re.compile(r"\bprintenv\b[^\n]*(?:" + ENV_NAME + r")"),
    re.compile(r"\benv\b\s*\|"),
    re.compile(r"\bhead\b[^\n]*\${?(?:" + ENV_NAME + r")\}?"),
    re.compile(r"\${?" + ENV_NAME + r"}?"),
    re.compile(ENV_NAME),
    re.compile(r"\bprintenv\b\s*$"),
    re.compile(r"\benv\b\s*$"),
)
FILE_PATH_PATTERNS = (
    re.compile(r"~/?\.kalshi/.*\.key\b"),
    re.compile(r"~/?\.kalshi/kalshi_rsa"),
)
RAW_VALUE_PATTERNS = (
    re.compile(r"\bsk_live_[A-Za-z0-9]{20,}\b"),
    re.compile(r"\bdwk_[A-Za-z0-9]{20,}\b"),
    re.compile(r"\bbearer\s+[A-Za-z0-9_\-\.=]{32,}\b", re.IGNORECASE),
    re.compile(r"\b-----BEGIN [A-Z ]*PRIVATE KEY-----"),
)
CHART_LIB_RE = re.compile(
    r"\b(import\s+seaborn|from\s+seaborn|import\s+matplotlib|from\s+matplotlib|"
    r"matplotlib\.pyplot|matplotlib\.use|\bplt\.|\bsns\.|import\s+plotly|"
    r"from\s+plotly|plotly\.graph_objects|plotly\.express|go\.Figure|"
    r"px\.line|px\.bar|datawrapper)\b",
    re.IGNORECASE,
)
ADJACENT_AWARE_RE = re.compile(
    r"adjacent_chart_style|\badj\.(?:PALETTE|SERIES|UP|DOWN|apply_adjacent_theme|"
    r"apply_adjacent_style|plotly_template|percent_formatter|save|source_line|"
    r"figure|frame|y_axis|area_series|last_value|series_label|swatch_legend)\b",
    re.IGNORECASE,
)
HEX_RE = re.compile(r"#[0-9a-fA-F]{3}(?:[0-9a-fA-F]{3})?\b")
GENERIC_PALETTE_RE = re.compile(
    r"\b(viridis|plasma|inferno|magma|cividis|tab10|tab20|tab20b|tab20c|"
    r"Set1|Set2|Set3|Paired|Pastel1|Pastel2|muted|bright|colorblind|deep|"
    r"pastel|dark|RdBu|RdYlGn|coolwarm|jet)\b",
    re.IGNORECASE,
)
ADJACENT_HEX = {
    "#" + h
    for h in (
        "ece9e2", "ffffff", "0e2a1f", "0a0f0d", "5c5a53", "7f7d7a",
        "3fae5a", "22c55e", "e66b55", "6fb7e0", "d89a3f", "a8c49a",
        "f0a8c8", "d6d2c8", "f6f5f1", "ecebea", "2a6a3a", "9b3a2e",
        "0e6b3a", "c0392b", "3498db", "4a90d9", "e87d2a", "b85cce",
    )
}
THRESHOLDS = {"1d": 0.015, "7d": 0.040}
STATE_DIR = os.environ.get("ADJACENT_STATE_DIR", ".")
LOG_PATH = os.path.join(STATE_DIR, "logs", "movers.log")


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
    """Pull text out of a write-capable or shell tool input.

    For Bash commands, returns the command string so chart-style can
    nudge when a shell command runs a chart library. For write tools,
    returns the content/new_string/edits text. Returns empty string
    for anything else."""
    if tool_name == "Bash":
        cmd = tool_input.get("command", "")
        return cmd if isinstance(cmd, str) else ""
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


def _conventions_check(payload: dict[str, Any]) -> dict[str, Any]:
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


def _secret_redactor_check(payload: dict[str, Any]) -> dict[str, Any]:
    tool_name = payload.get("tool_name", "") or ""
    tool_input = payload.get("tool_input") or {}
    if not isinstance(tool_input, dict):
        tool_input = {}
    if tool_name == "Bash":
        command = tool_input.get("command", "")
        command = command if isinstance(command, str) else ""
        for pattern in PRINT_PATTERNS:
            if pattern.search(command):
                return _deny(
                    f"Bash command matches secret-print pattern: {pattern.pattern[:60]}"
                )
        for pattern in FILE_PATH_PATTERNS:
            if pattern.search(command):
                return _deny(f"Bash command touches a key file: {pattern.pattern}")
        if re.search(r"\b(open|less|more|awk|sed|tee|cp)\b[^\n]*(?:\.kalshi|kalshi_rsa)", command):
            return _deny("Bash command attempts to read a Kalshi key file")
        return _allow("adjacent/secret-redactor: no secret-print pattern")
    if tool_name not in WRITE_TOOLS:
        return _allow("adjacent/secret-redactor: skipped non-target tool")
    text = collect_text(tool_name, tool_input)
    for pattern in RAW_VALUE_PATTERNS:
        if pattern.search(text):
            return _deny(
                f"raw secret token detected (pattern prefix: {pattern.pattern[:40]})"
            )
    return _allow("adjacent/secret-redactor: no raw secret in text")


def _chart_style_check(payload: dict[str, Any]) -> dict[str, Any]:
    tool_name = payload.get("tool_name", "") or ""
    tool_input = payload.get("tool_input") or {}
    if not isinstance(tool_input, dict):
        tool_input = {}
    text = collect_text(tool_name, tool_input)
    if not text or not CHART_LIB_RE.search(text):
        return _allow("adjacent/chart-style: no chart library detected")
    aware = bool(ADJACENT_AWARE_RE.search(text))
    if tool_name == "Bash":
        if aware:
            return _allow("adjacent/chart-style: bash run uses adjacent_chart_style")
        return _allow_with_context(
            "chart-style: chart library detected. Import adjacent_chart_style as adj "
            "and use the Adjacent chart helper. See the adjacent-chart-style skill."
        )
    generics = GENERIC_PALETTE_RE.search(text)
    bad_colors = []
    for match in HEX_RE.finditer(text):
        value = match.group(0).lower()
        if len(value) == 4:
            value = "#" + "".join(c * 2 for c in value[1:])
        if value not in ADJACENT_HEX:
            bad_colors.append(match.group(0))
    if aware and not generics:
        return _allow("adjacent/chart-style: adjacent_chart_style in use")
    if generics or (bad_colors and not aware):
        reasons = []
        if generics:
            reasons.append(f"uses generic palette ({generics.group(0)})")
        if bad_colors and not aware:
            reasons.append("hardcoded color(s) not in the Adjacent palette")
        return _deny(
            "blocked by adjacent/chart-style: chart code is not on-brand. "
            + "; ".join(reasons)
            + ". Import adjacent_chart_style and use Adjacent palette tokens."
        )
    return _allow_with_context(
        "chart-style: chart library detected without adjacent_chart_style. "
        "Import adjacent_chart_style as adj and use the Adjacent chart helper."
    )


def _allow_with_context(context: str) -> dict[str, Any]:
    result = _allow("adjacent/chart-style: allowed with guidance")
    result["hookSpecificOutput"]["additionalContext"] = context
    return result


def pre_tool_call(payload: dict[str, Any]) -> dict[str, Any]:
    """Run all Hermes PreToolUse checks, stopping at the first denial."""
    for check in (_conventions_check, _secret_redactor_check, _chart_style_check):
        result = check(payload)
        if result["hookSpecificOutput"]["permissionDecision"] == "deny":
            return result
    return _allow("adjacent: all pre-tool-use checks passed")


def post_tool_call(payload: dict[str, Any]) -> dict[str, Any]:
    tool_name = payload.get("tool_name", "") or ""
    if not (tool_name.endswith("/price") or tool_name.endswith("__price")):
        return {"continue": True}
    response = payload.get("tool_response")
    if not isinstance(response, dict):
        return {"continue": True}
    moves = response.get("moves") or {}
    if not isinstance(moves, dict):
        return {"continue": True}
    hit = None
    for key, limit in THRESHOLDS.items():
        try:
            if key in moves and abs(float(moves[key])) >= limit:
                hit = key
                break
        except (TypeError, ValueError):
            continue
    if hit is None:
        return {"continue": True}
    slug = (
        response.get("slug")
        or (response.get("args") or {}).get("slug")
        or response.get("id")
        or "<unknown>"
    )
    value = float(moves[hit])
    line = f"{datetime.now(timezone.utc).isoformat(timespec='seconds')} {slug} {hit} {value:+.4f}\n"
    os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
    with open(LOG_PATH, "a", encoding="utf-8") as handle:
        handle.write(line)
    return {
        "hookSpecificOutput": {
            "hookEventName": "PostToolUse",
            "additionalContext": f"mover-logger: appended {slug} {hit} {value:+.4f}",
        }
    }


def main() -> int:
    """CLI entry for hosts that invoke hooks as subprocesses. Reads a
    JSON payload from stdin, writes a JSON decision to stdout."""
    raw = sys.stdin.read()
    try:
        payload = json.loads(raw) if raw.strip() else {}
    except json.JSONDecodeError:
        json.dump(_allow("adjacent/conventions: unreadable payload"), sys.stdout)
        return 0
    try:
        result = pre_tool_call(payload)
    except Exception:
        result = _allow("adjacent/conventions: unexpected error")
    json.dump(result, sys.stdout)
    return 0


if __name__ == "__main__":
    sys.exit(main())
