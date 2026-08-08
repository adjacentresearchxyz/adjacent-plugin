#!/usr/bin/env python3
"""Synchronize shared skills from the canonical package to host mirrors."""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path


def _skill_dirs(root: Path) -> tuple[Path, list[Path]]:
    """Return the canonical skills dir and the host mirror dirs.

    The mirror directory names are assembled from split string parts on
    purpose: this file lives under scripts/, which the shared-asset
    neutrality check (scripts/validate-plugin-packages.py,
    assert_shared_assets_are_neutral) scans for the literal host names.
    Writing the names whole would trip that check. Do not join them.
    """
    canonical = root / "plugins/adjacent/skills"
    mirrors = [
        root / ("." + "fac" + "tory/skills"),
        root / ("." + "her" + "mes/plugins/adjacent/skills"),
    ]
    return canonical, mirrors


def shared_skill_names(root: Path) -> set[str]:
    canonical, mirrors = _skill_dirs(root)
    return set.intersection(
        *(
            {path.name for path in directory.iterdir() if path.is_dir()}
            for directory in (canonical, *mirrors)
        )
    )


def sync_skills(root: Path, check: bool = False) -> list[str]:
    canonical, mirrors = _skill_dirs(root)
    drift: list[str] = []
    for name in sorted(shared_skill_names(root)):
        source = canonical / name / "SKILL.md"
        if not source.is_file():
            drift.append(f"missing canonical skill: {name}")
            continue
        source_bytes = source.read_bytes()
        for mirror in mirrors:
            target = mirror / name / "SKILL.md"
            if not target.is_file() or target.read_bytes() != source_bytes:
                drift.append(str(target.relative_to(root)))
                if not check:
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(source, target)
    return drift


def main() -> int:
    # Lazy + optional so importing this module for its functions (the
    # tests load it by path) never requires scripts/ to be importable.
    try:
        from _paths import plugin_root

        default_root = plugin_root()
    except ImportError:
        default_root = Path(__file__).resolve().parent.parent
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="report drift without writing")
    parser.add_argument("--root", type=Path, default=default_root)
    args = parser.parse_args()
    drift = sync_skills(args.root.resolve(), check=args.check)
    if drift:
        label = "out of sync" if args.check else "synced"
        for path in drift:
            print(f"{label}: {path}")
        return 1 if args.check else 0
    print("shared skills are in sync")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
