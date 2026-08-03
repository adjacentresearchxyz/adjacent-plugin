#!/usr/bin/env python3
"""Post-tool-use hook on Adjacent `price` MCP calls.

When the model calls `adjacent-markets/price` (or dev variant), the response
contains a `mid`-keyed 24h and 7d series. If `|move_1d| >= 1.5%` OR
`|move_7d| >= 4%`, append a single line to
`<plugin-data-dir>/logs/movers.log` so the morning briefing can pick it up
later.

The user does not see this hook's output by default; it persists to a file.
Hooks emit JSON; the host prints stdout only on request.
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone

STATE_DIR = os.environ.get("ADJACENT_STATE_DIR", ".")
LOG_PATH = os.path.join(STATE_DIR, "logs", "movers.log")
THRESHOLDS = {"1d": 0.015, "7d": 0.040}


def find_threshold(moves: dict[str, float]) -> str | None:
    for k, limit in THRESHOLDS.items():
        m = moves.get(k)
        if m is None:
            continue
        try:
            if abs(float(m)) >= limit:
                return k
        except (TypeError, ValueError):
            continue
    return None


def emit_extra_context(payload: dict) -> dict | None:
    tool = payload.get("tool_name", "")
    if not (tool.endswith("/price") or tool.endswith("__price")):
        return None
    tool_response = payload.get("tool_response")
    if not isinstance(tool_response, dict):
        return None
    moves = tool_response.get("moves") or {}
    hit = find_threshold(moves)
    if hit is None:
        return None
    slug = (
        tool_response.get("slug")
        or (tool_response.get("args") or {}).get("slug")
        or tool_response.get("id")
        or "<unknown>"
    )
    line = f"{datetime.now(timezone.utc).isoformat(timespec='seconds')} {slug} {hit} {moves.get(hit):+.4f}\n"
    os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write(line)
    return {
        "hookSpecificOutput": {
            "hookEventName": "PostToolUse",
            "additionalContext": f"mover-logger: appended {slug} {hit} {moves.get(hit):+.4f}",
        }
    }


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except json.JSONDecodeError:
        json.dump({"continue": True}, sys.stdout)
        return 0
    result = emit_extra_context(payload)
    if result is None:
        json.dump({"continue": True}, sys.stdout)
    else:
        json.dump(result, sys.stdout)
    return 0


if __name__ == "__main__":
    sys.exit(main())
