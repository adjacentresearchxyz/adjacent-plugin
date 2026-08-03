"""conftest.py - shared fixtures and path setup for the Hermes plugin
tests.

The tests run with NO Hermes installation. This file puts the bundled
plugin package on sys.path so `import adjacent` resolves to
.hermes/plugins/adjacent, and provides a fake host context for
registration tests.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Repo root = tests/hermes/ -> tests -> adjacent-plugin
_REPO_ROOT = Path(__file__).resolve().parents[2]
_PLUGIN_PARENT = _REPO_ROOT / ".hermes" / "plugins"

# Make `import adjacent` resolve to the Hermes-native plugin package.
if str(_PLUGIN_PARENT) not in sys.path:
    sys.path.insert(0, str(_PLUGIN_PARENT))


class FakeContext:
    """Record Hermes plugin registrations for assertions."""

    def __init__(self) -> None:
        self.tools: dict[str, dict] = {}
        self.skills: dict[str, object] = {}
        self.hooks: list[tuple] = []
        self.commands: dict[str, dict] = {}
        self.calls: dict[str, int] = {}

    def _cap(self, name):
        self.calls[name] = self.calls.get(name, 0) + 1

    def register_tool(self, *, name, toolset, schema, handler, description="", **kwargs):
        self._cap("register_tool")
        self.tools[name] = {
            "toolset": toolset,
            "schema": schema,
            "handler": handler,
            "description": description,
        }

    def register_skill(self, name, path, *args, **kwargs):
        self._cap("register_skill")
        self.skills[name] = path

    def register_hook(self, event, handler, *args, **kwargs):
        self._cap("register_hook")
        self.hooks.append((event, handler))

    def register_command(self, name, *, handler, description="", **kwargs):
        self._cap("register_command")
        self.commands[name] = {"handler": handler, "description": description}


@pytest.fixture
def fake_ctx():
    return FakeContext()


@pytest.fixture
def tmp_data_root(tmp_path, monkeypatch):
    """Point shared workflows at an isolated data directory."""
    root = tmp_path / "data"
    positions = root / "positions"
    positions.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("ADJACENT_DATA_DIR", str(root))
    return root
