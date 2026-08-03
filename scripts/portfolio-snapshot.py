#!/usr/bin/env python3
"""portfolio-snapshot.py - portfolio status for any index.

Reads cached position documents from data/positions/*.json. Emits a
human-readable status or, with --json, structured output for downstream
consumers. All timestamps use America/New_York (ET).
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from zoneinfo import ZoneInfo

from _paths import data_dir


ET = ZoneInfo("America/New_York")


def positions_dir():
    """Resolved per call so ADJACENT_DATA_DIR applies after import."""
    return data_dir() / "positions"


def load_all() -> dict[str, dict]:
    out: dict[str, dict] = {}
    root = positions_dir()
    if not root.exists():
        return out
    for p in sorted(root.glob("*.json")):
        if p.stem.endswith(".series"):
            continue
        try:
            doc = json.loads(p.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        out[p.stem] = doc
    return out


def load_index(index: str) -> dict[str, dict]:
    path = positions_dir() / f"{index}.json"
    try:
        return {index: json.loads(path.read_text(encoding="utf-8"))}
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def now_et_str() -> str:
    return datetime.now(ET).strftime("%Y-%m-%d %H:%M:%S ET")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--index", help="report only this index slug")
    ap.add_argument("--include-pnl", action="store_true")
    args = ap.parse_args()
    docs = load_index(args.index) if args.index else load_all()
    if not docs:
        print("no portfolio snapshots found", file=sys.stderr)
        return 1
    if args.json:
        json.dump(
            {"as_of": datetime.now(ET).isoformat(timespec="seconds"), "snapshots": docs},
            sys.stdout,
            indent=2,
        )
        sys.stdout.write("\n")
        return 0
    print(f"as-of: {now_et_str()}")
    for idx, doc in docs.items():
        positions = doc.get("positions", []) or []
        n = len(positions)
        exposure = sum(abs(p.get("notional", 0)) for p in positions)
        print(f"- {idx}: {n} positions, exposure ${exposure:,.2f}")
        if args.include_pnl:
            for p in positions:
                mid = p.get("mid")
                cost = p.get("cost_basis")
                if mid is not None and cost:
                    pnl_pct = (mid - cost) / cost
                    print(
                        f"  - {p.get('market_id', 'unknown')}: "
                        f"size {p.get('size', 0)} mid {mid:.4f} "
                        f"pnl {pnl_pct*100:+.2f}% mid-quote"
                    )
    print(f"last sync: {now_et_str()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
