#!/usr/bin/env python3
"""SessionStart hook: inject the using-adjacent skill into context.

Hosts invoke this with no required stdin. On success it prints a JSON
envelope whose additionalContext is the full using-adjacent skill. If
the skill file cannot be read, it fail-opens so a missing file never
wedges the session.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path


def plugin_root() -> Path:
    return Path(__file__).resolve().parent.parent


def skill_path() -> Path:
    return plugin_root() / "skills" / "using-adjacent" / "SKILL.md"


def skill_text() -> str:
    return skill_path().read_text(encoding="utf-8")


def additional_context(skill: str) -> str:
    return (
        "<EXTREMELY_IMPORTANT>\n"
        "You have Adjacent.\n\n"
        "**Below is the full content of your using-adjacent skill. "
        "For all other Adjacent skills, load the matching SKILL.md.**\n\n"
        f"{skill}\n"
        "</EXTREMELY_IMPORTANT>"
    )


def envelope(context: str) -> dict:
    return {
        "hookSpecificOutput": {
            "hookEventName": "SessionStart",
            "additionalContext": context,
        }
    }


def build_payload() -> dict:
    try:
        return envelope(additional_context(skill_text()))
    except OSError:
        return {"continue": True}


def main() -> int:
    json.dump(build_payload(), sys.stdout)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
