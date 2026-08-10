"""Shared loaders for hook and script modules under test.

Hook scripts and workflow scripts have hyphenated filenames, so they
cannot be imported normally. Load them by path and exercise their
functions directly.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def load_hook(relative_path: str):
    path = ROOT / relative_path
    spec = importlib.util.spec_from_file_location(path.stem.replace("-", "_"), path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_script(name: str):
    """Load a script from scripts/ by filename, inserting scripts/ on sys.path."""
    path = ROOT / "scripts" / name
    scripts_path = str(path.parent)
    if scripts_path not in sys.path:
        sys.path.insert(0, scripts_path)
    spec = importlib.util.spec_from_file_location(path.stem.replace("-", "_"), path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
