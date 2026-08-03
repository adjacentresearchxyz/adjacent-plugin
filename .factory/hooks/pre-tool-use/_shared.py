"""Shared PreToolUse plumbing for the adjacent plugin hooks.

The host invokes a hook with a JSON envelope on stdin carrying
``tool_name`` and ``tool_input``, and reads a decision envelope back on
stdout. Field names inside ``tool_input`` vary per tool, so the readers
here look for the known keys first and fall back to a generic scan rather
than hard-coding one tool's schema.

Two rules keep the hooks from blocking legitimate work:

- Keys holding pre-edit text (``old_string`` and friends) are never
  scanned. Removing an em-dash requires naming it in the old text.
- A unified diff is reduced to its added lines, so a patch that only
  touches neighboring context is judged on what it actually adds.
"""

from __future__ import annotations

from typing import Any

# Tool names, per host tool ids.
SHELL_TOOLS = {"Execute"}
WRITE_TOOLS = {"Create", "Edit", "ApplyPatch"}

# Keys whose value is text about to be persisted.
NEW_TEXT_KEYS = (
    "content",
    "new_string",
    "new_str",
    "new_text",
    "file_text",
    "patch",
    "replacement",
    "text",
)

# Keys whose value is pre-edit text; scanning them causes false denials.
OLD_TEXT_KEYS = (
    "old_string",
    "old_str",
    "old_text",
    "original",
    "before",
)

# Keys that carry a shell command.
COMMAND_KEYS = ("command", "cmd", "script", "shell_command")


def looks_like_diff(text: str) -> bool:
    for line in text.splitlines():
        if line.startswith("@@ ") or line.startswith("+++ ") or line.startswith("*** "):
            return True
    return False


def added_lines(text: str) -> str:
    """Reduce a unified diff to the text it adds."""
    kept: list[str] = []
    for line in text.splitlines():
        if line.startswith("+++"):
            continue
        if line.startswith("+"):
            kept.append(line[1:])
    return "\n".join(kept)


def _walk(value: Any, keys: tuple[str, ...] | None, out: list[str]) -> None:
    """Collect strings under ``keys``, or under every key when ``keys`` is None."""
    if isinstance(value, dict):
        for key, item in value.items():
            lowered = str(key).lower()
            if lowered in OLD_TEXT_KEYS:
                continue
            if isinstance(item, str):
                if keys is None or lowered in keys:
                    out.append(item)
            else:
                _walk(item, keys, out)
    elif isinstance(value, list):
        for item in value:
            _walk(item, keys, out)


def _collect(tool_input: dict[str, Any], keys: tuple[str, ...]) -> list[str]:
    parts: list[str] = []
    _walk(tool_input, keys, parts)
    if not parts:
        _walk(tool_input, None, parts)
    return parts


def collect_new_text(tool_input: dict[str, Any]) -> str:
    """Return the text a write-capable tool is about to persist."""
    parts = [
        added_lines(part) if looks_like_diff(part) else part
        for part in _collect(tool_input, NEW_TEXT_KEYS)
    ]
    return "\n".join(part for part in parts if part)


def collect_command(tool_input: dict[str, Any]) -> str:
    """Return the shell command a shell tool is about to run."""
    return "\n".join(_collect(tool_input, COMMAND_KEYS))


def collect_text(tool_name: str, tool_input: dict[str, Any]) -> str:
    """Dispatch to the right reader for this tool."""
    if tool_name in SHELL_TOOLS:
        return collect_command(tool_input)
    return collect_new_text(tool_input)


def allow(reason: str) -> dict[str, Any]:
    return {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "allow",
            "permissionDecisionReason": reason,
        }
    }


def allow_with_context(reason: str, context: str) -> dict[str, Any]:
    result = allow(reason)
    result["hookSpecificOutput"]["additionalContext"] = context
    return result


def deny(reason: str) -> dict[str, Any]:
    return {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
        }
    }
