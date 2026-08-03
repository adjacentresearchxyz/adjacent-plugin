#!/usr/bin/env python3
"""chart-index.py - build a per-index 24h %-return chart CSV.

Two series: index value and portfolio value, both rebased to 100 at
the most recent fill timestamp for the named index. Reads from
data/positions/<slug>.series.json (in production these are populated from MCP price calls via
scripts/mcp-cli.py price ... --raw).

Output is CSV on stdout: ts,index,portfolio. Pipe into
scripts/datawrapper-publish.py <chart-id> to publish.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys

from _paths import data_dir


def positions_dir():
    """Resolved per call so ADJACENT_DATA_DIR applies after import."""
    return data_dir() / "positions"


def load_series(name: str) -> list[tuple[str, float]]:
    cache = positions_dir() / f"{name}.series.json"
    if not cache.exists():
        return []
    doc = json.loads(cache.read_text(encoding="utf-8"))
    return [(row["ts"], row["value"]) for row in doc.get("series", [])]


def fmt_value(value: float | None) -> str:
    """Format a series value, leaving the cell blank when a series has no
    point at this timestamp. The two series are rebased independently and
    rarely share an identical timestamp set, so gaps are the norm."""
    return "" if value is None else f"{value:.4f}"


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
    fill_ts_path = positions_dir() / f"{args.index}.last_fill_ts"
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
                    "index": fmt_value(row.get("index")),
                    "portfolio": fmt_value(row.get("portfolio")),
                }
            )
    finally:
        if args.output:
            target.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
