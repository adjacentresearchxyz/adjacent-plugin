"""Shared runtime paths for command-line workflows.

Resolution order lets a plugin install live outside the monorepo while
still defaulting cleanly when scripts ship next to ``data/``:

- ``ADJACENT_PLUGIN_ROOT``: install root that contains ``scripts/`` and
  ``data/``.
- ``ADJACENT_PLUGIN_SCRIPTS``: explicit scripts directory override.
- ``ADJACENT_DATA_DIR``: explicit shared data directory override.
- ``ADJACENT_STATE_DIR``: logs and chart-output directory override.
"""

from __future__ import annotations

import os
from pathlib import Path


# scripts/_paths.py -> scripts/ -> plugin root
_FILE_ROOT = Path(__file__).resolve().parent.parent


def plugin_root() -> Path:
    """Return the Adjacent plugin install root."""
    override = os.environ.get("ADJACENT_PLUGIN_ROOT")
    if override:
        return Path(override).expanduser().resolve()
    return _FILE_ROOT


def scripts_dir() -> Path:
    """Return the directory that holds the Python workflow scripts."""
    override = os.environ.get("ADJACENT_PLUGIN_SCRIPTS")
    if override:
        return Path(override).expanduser().resolve()
    return plugin_root() / "scripts"


def data_dir() -> Path:
    """Return the shared data directory, allowing an explicit override."""
    override = os.environ.get("ADJACENT_DATA_DIR")
    if override:
        return Path(override).expanduser().resolve()
    return plugin_root() / "data"


def state_dir() -> Path:
    """Return logs / chart-output directory."""
    override = os.environ.get("ADJACENT_STATE_DIR")
    if override:
        return Path(override).expanduser().resolve()
    return plugin_root() / "state"
