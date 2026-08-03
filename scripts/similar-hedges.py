#!/usr/bin/env python3
"""Rank similar markets as hedges or proxies for a target market.

The `markets/{id}/similar` surface is live. Fetch related markets via the
MCP, attach a signed mid-return correlation to the target for each one,
and supply the rows as JSON:

    [{"market_id": ..., "correlation": -0.72}, ...]

A hedge is a negatively correlated market (moves opposite the target); a
proxy is a positively correlated market (moves with it). Correlations are
mid-based by convention; never use last-trade prints.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def classify(rows: list[dict], min_abs: float) -> dict:
    hedges: list[dict] = []
    proxies: list[dict] = []
    for row in rows:
        market_id = row.get("market_id")
        corr = row.get("correlation")
        if market_id is None or not isinstance(corr, (int, float)):
            continue
        corr = float(corr)
        if abs(corr) < min_abs:
            continue
        entry = {"market_id": str(market_id), "correlation": round(corr, 4)}
        (hedges if corr < 0 else proxies).append(entry)
    hedges.sort(key=lambda r: r["correlation"])
    proxies.sort(key=lambda r: r["correlation"], reverse=True)
    return {"hedges": hedges, "proxies": proxies}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, help="path to similar-markets JSON")
    parser.add_argument(
        "--min-abs-correlation",
        type=float,
        default=0.3,
        help="ignore markets whose absolute correlation is below this",
    )
    args = parser.parse_args()
    rows = json.loads(Path(args.input).read_text(encoding="utf-8"))
    if isinstance(rows, dict):
        rows = rows.get("similar", rows.get("markets", []))
    print(json.dumps(classify(rows, args.min_abs_correlation), indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
