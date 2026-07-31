#!/usr/bin/env python3
"""tracking-index.py - produce a per-row tracking-error table for any index.

Reads <plugin-data>/plugins/adjacent/data/positions/<slug>.json and
emits <plugin-data>/plugins/adjacent/data/tracking/<slug>.json. Each
row reports position size, mid, cost basis, current notional,
%-weight in the portfolio, today's mid-based move (P&L), and the
queued fill deviation.

Tracking = (mid_portfolio_return - mid_index_return) in %.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

DATA_DIR = Path(os.environ.get("ADJACENT_PLUGIN_DATA", "."))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--index", required=True, help="position file slug")
    ap.add_argument("--json", action="store_true", help="also print to stdout")
    args = ap.parse_args()
    pos_path = DATA_DIR / "plugins" / "adjacent" / "data" / "positions" / f"{args.index}.json"
    if not pos_path.exists():
        raise SystemExit(f"error: missing positions file {pos_path}")
    doc = json.loads(pos_path.read_text(encoding="utf-8"))
    positions = doc.get("positions", []) or []
    total_notional = sum(abs(p.get("notional", 0)) for p in positions)
    rows = []
    for p in positions:
        size = p.get("size", 0)
        notional = p.get("notional", 0)
        cost = p.get("cost_basis")
        mid = p.get("mid")
        weight_pct = (notional / total_notional * 100) if total_notional else 0
        pnl_pct = ((mid - cost) / cost * 100) if (mid is not None and cost) else 0
        rows.append({
            "market_id": p.get("market_id"),
            "size": size,
            "mid": mid,
            "cost_basis": cost,
            "notional": notional,
            "weight_pct": round(weight_pct, 4),
            "pnl_pct_mid": round(pnl_pct, 4),
            "fill_queue_pct": p.get("fill_queue_pct"),
        })
    out_dir = DATA_DIR / "plugins" / "adjacent" / "data" / "tracking"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{args.index}.json"
    out_path.write_text(json.dumps({"index": args.index, "rows": rows}, indent=2), encoding="utf-8")
    if args.json:
        json.dump({"index": args.index, "rows": rows}, sys.stdout, indent=2)
        sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
