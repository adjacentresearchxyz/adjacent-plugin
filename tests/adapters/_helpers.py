"""Shared helpers for adapter tests.

No third-party dependencies. Uses only the Python standard library.
"""

import json
import os
import re
import tomllib
from typing import Any, Dict, List, Optional

# Resolve the plugin root from this file's location:
#   tests/adapters/_helpers.py -> plugin root is two parents up.
PLUGIN_ROOT = os.path.normpath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")
)

CODEX_DIR = os.path.join(PLUGIN_ROOT, ".codex")
CURSOR_DIR = os.path.join(PLUGIN_ROOT, ".cursor")

# Expected agent names translated from plugins/adjacent/agents/*.md.
EXPECTED_AGENTS = [
    "coordinator",
    "index-monitor",
    "data-monitor",
    "briefing-writer",
    "ask-assistant",
]

# Expected .mdc rule files under .cursor/rules.
EXPECTED_MDC_RULES = [
    "adjacent-tokens.mdc",
    "adjacent-pricing.mdc",
    "adjacent-conventions.mdc",
    "adjacent-json.mdc",
    "adjacent-data-surfaces.mdc",
]

# Canonical MCP endpoint URLs (must match plugins/adjacent/mcp.json).
MCP_PROD_URL = "https://mcp.adjacent.markets/mcp?apiKey=${ADJACENT_API_KEY}"
MCP_DEV_URL = "https://mcp.dev.adjacent.markets/mcp?apiKey=${ADJACENT_API_KEY}"

# Read-only MCP tools shared across agents.
READONLY_TOOL_PREFIXES = ("adjacent-markets/", "adjacent-markets-dev/")


def read_file(rel_path: str) -> str:
    """Read a text file relative to the plugin root."""
    full = os.path.join(PLUGIN_ROOT, rel_path)
    with open(full, "r", encoding="utf-8") as fh:
        return fh.read()


def file_exists(rel_path: str) -> bool:
    return os.path.isfile(os.path.join(PLUGIN_ROOT, rel_path))


# ---------------------------------------------------------------------------
# TOML parser
# ---------------------------------------------------------------------------

def parse_toml(text: str) -> Dict[str, Any]:
    """Parse TOML with Python 3.11+'s standard-library parser."""
    return tomllib.loads(text)


# ---------------------------------------------------------------------------
# YAML-ish frontmatter parser (no third-party deps)
# ---------------------------------------------------------------------------

def parse_frontmatter(text: str) -> Dict[str, Any]:
    """Parse a YAML-ish frontmatter block delimited by ``---`` lines.

    Supports:
      - Simple key: value pairs.
      - YAML lists (lines starting with ``  -``).
      - Booleans (true/false) and integers.
      - Nested keys are NOT supported (none are needed).

    Returns a dict with the parsed keys plus a ``_body`` key holding the
    markdown body after the frontmatter.
    """
    if not text.startswith("---"):
        return {"_body": text}
    lines = text.splitlines()
    # First line is the opening ---
    end_idx: Optional[int] = None
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            end_idx = i
            break
    if end_idx is None:
        return {"_body": text}
    fm_lines = lines[1:end_idx]
    body = "\n".join(lines[end_idx + 1:])

    data: Dict[str, Any] = {}
    current_list_key: Optional[str] = None
    for line in fm_lines:
        if not line.strip():
            continue
        # List item: starts with whitespace then -
        if re.match(r"^\s+-\s+", line):
            item = re.sub(r"^\s+-\s+", "", line).strip()
            if current_list_key is not None:
                data[current_list_key].append(item)
            continue
        # key: value
        m = re.match(r"^([A-Za-z0-9_-]+)\s*:\s*(.*)$", line)
        if m:
            key = m.group(1)
            val = m.group(2).strip()
            current_list_key = key
            if val == "":
                data[key] = []
            elif val.startswith("[") and val.endswith("]"):
                # Inline JSON-style array: ["a", "b", "c"]
                inner = val[1:-1].strip()
                items: List[str] = []
                if inner:
                    for part in inner.split(","):
                        part = part.strip().strip('"').strip("'")
                        if part:
                            items.append(part)
                data[key] = items
            elif val.lower() in ("true", "false"):
                data[key] = val.lower() == "true"
            else:
                try:
                    data[key] = int(val)
                except ValueError:
                    data[key] = val
    data["_body"] = body
    return data


def assert_no_em_dash(text: str) -> List[str]:
    """Return a list of lines containing an em-dash (U+2014)."""
    offenders = []
    for i, line in enumerate(text.splitlines(), 1):
        if "\u2014" in line:
            offenders.append("line %d" % i)
    return offenders


def assert_no_emoji(text: str) -> List[str]:
    """Return a list of lines containing common emoji ranges."""
    offenders = []
    for i, line in enumerate(text.splitlines(), 1):
        # Check for non-ASCII characters that are not part of allowed
        # ranges (we allow basic Latin + common punctuation). This is a
        # rough check for emoji and unicode bullets.
        for ch in line:
            code = ord(ch)
            if code == 0x2022:  # unicode bullet
                offenders.append("line %d (unicode bullet)" % i)
                break
            # Emoji ranges (rough)
            if 0x1F000 <= code <= 0x1FFFF or 0x2600 <= code <= 0x27BF:
                offenders.append("line %d (emoji-like char U+%04X)" % (i, code))
                break
    return offenders
