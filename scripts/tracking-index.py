#!/usr/bin/env python3
"""tracking-index.py - produce a per-position mid-based table for any index.

Reads data/positions/<slug>.json and emits data/tracking/<slug>.json.
Each row reports position size, mid, cost basis, current notional,
%-weight in the portfolio, mid-based return against cost basis, and the
queued fill deviation.

Scope: this is the per-position leg of the tracking report, not the
tracking error itself. Tracking error is
(mid_portfolio_return - mid_index_return) in %, which needs an index
reference series; position documents carry no index series, so it is
computed downstream from these rows plus a chart series (see
scripts/chart-index.py). Do not read `pnl_pct_mid` as tracking error.
"""

from __future__ import annotations

import argparse
import json
import sys

from _paths import data_dir


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--index", required=True, help="position file slug")
    ap.add_argument("--json", action="store_true", help="also print to stdout")
    args = ap.parse_args()
    root = data_dir()
    pos_path = root / "positions" / f"{args.index}.json"
    if not pos_path.exists():
        raise SystemExit(f"error: missing positions file {pos_path}")
    try:
        doc = json.loads(pos_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SystemExit(f"error: {pos_path} is not valid JSON: {exc}")
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
    out_dir = root / "tracking"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{args.index}.json"
    out_path.write_text(json.dumps({"index": args.index, "rows": rows}, indent=2), encoding="utf-8")
    if args.json:
        json.dump({"index": args.index, "rows": rows}, sys.stdout, indent=2)
        sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
