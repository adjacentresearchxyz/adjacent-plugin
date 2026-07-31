#!/usr/bin/env python3
"""table-tracking.py - build a per-index tracking-error table CSV.

Reads tracking/<slug>.json (produced by scripts/tracking-index.py) and
emits a CSV suitable for Datawrapper publish:

  market_id,size,notional,weight_pct,pnl_pct_mid,fill_queue_pct

Pipe into scripts/datawrapper-publish.py <chart-id> to publish.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

DATA_DIR = Path(os.environ.get("ADJACENT_PLUGIN_DATA", "."))
TRACKING_DIR = DATA_DIR / "plugins" / "adjacent" / "data" / "tracking"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--index", required=True)
    ap.add_argument("--output", help="write CSV to this path instead of stdout")
    args = ap.parse_args()
    src = TRACKING_DIR / f"{args.index}.json"
    if not src.exists():
        raise SystemExit(f"error: missing tracking source {src}; run scripts/tracking-index.py first")
    doc = json.loads(src.read_text(encoding="utf-8"))
    target = open(args.output, "w", encoding="utf-8", newline="") if args.output else sys.stdout
    try:
        w = csv.DictWriter(
            target,
            fieldnames=["market_id", "size", "notional", "weight_pct", "pnl_pct_mid", "fill_queue_pct"],
        )
        w.writeheader()
        for row in doc.get("rows", []):
            w.writerow({k: row.get(k, "") for k in w.fieldnames})
    finally:
        if args.output:
            target.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
