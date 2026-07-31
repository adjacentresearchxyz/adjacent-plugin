#!/usr/bin/env python3
"""chart-index.py - build a per-index 24h %-return chart CSV.

Two series: index value and portfolio value, both rebased to 100 at
the most recent fill timestamp for the named index. Reads from
<plugin-data>/plugins/adjacent/data/positions/<slug>.series.json
(in production these are populated from MCP price calls via
scripts/mcp-cli.py price ... --raw).

Output is CSV on stdout: ts,index,portfolio. Pipe into
scripts/datawrapper-publish.py <chart-id> to publish.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from pathlib import Path

DATA_DIR = Path(os.environ.get("ADJACENT_PLUGIN_DATA", "."))
POSITIONS_DIR = DATA_DIR / "plugins" / "adjacent" / "data" / "positions"


def load_series(name: str) -> list[tuple[str, float]]:
    cache = POSITIONS_DIR / f"{name}.series.json"
    if not cache.exists():
        return []
    doc = json.loads(cache.read_text(encoding="utf-8"))
    return [(row["ts"], row["value"]) for row in doc.get("series", [])]


def rebase(series: list[tuple[str, float]], anchor: str) -> list[tuple[str, float]]:
    base = None
    out: list[tuple[str, float]] = []
    for ts, v in series:
        if ts == anchor:
            base = v
            out.append((ts, 100.0))
        elif base is not None:
            out.append((ts, 100.0 * v / base))
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--index", required=True)
    ap.add_argument("--output", help="write CSV to this path instead of stdout")
    args = ap.parse_args()
    fill_ts_path = POSITIONS_DIR / f"{args.index}.last_fill_ts"
    if not fill_ts_path.exists():
        raise SystemExit(
            f"error: missing {fill_ts_path}; run scripts/rebalance-index.py "
            "first so the anchor timestamp is populated"
        )
    anchor = fill_ts_path.read_text(encoding="utf-8").strip()
    index = rebase(load_series(f"{args.index}.index"), anchor)
    portfolio = rebase(load_series(f"{args.index}.portfolio"), anchor)
    series = {}
    for ts, v in index:
        series[ts] = {"index": v}
    for ts, v in portfolio:
        series.setdefault(ts, {})["portfolio"] = v
    target = open(args.output, "w", encoding="utf-8", newline="") if args.output else sys.stdout
    try:
        w = csv.DictWriter(target, fieldnames=["ts", "index", "portfolio"])
        w.writeheader()
        for ts in sorted(series):
            row = series[ts]
            w.writerow(
                {
                    "ts": ts,
                    "index": f"{row.get('index', ''):.4f}",
                    "portfolio": f"{row.get('portfolio', ''):.4f}",
                }
            )
    finally:
        if args.output:
            target.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
