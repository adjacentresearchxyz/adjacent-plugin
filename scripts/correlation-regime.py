#!/usr/bin/env python3
"""Flag supplied correlation observations whose latest value moves by 2 sigma."""

from __future__ import annotations

import argparse
import json
import statistics
from pathlib import Path


def find_regime_shifts(rows: list[dict], threshold: float) -> list[dict]:
    grouped: dict[tuple[str, str], list[dict]] = {}
    for row in rows:
        key = (row["index"], row["benchmark"])
        grouped.setdefault(key, []).append(row)

    results: list[dict] = []
    for (index, benchmark), observations in grouped.items():
        observations.sort(key=lambda row: row["ts"])
        if len(observations) < 3:
            continue
        history = [float(row["correlation"]) for row in observations[:-1]]
        deviation = statistics.pstdev(history)
        if deviation == 0:
            continue
        latest = float(observations[-1]["correlation"])
        z_score = (latest - statistics.mean(history)) / deviation
        if abs(z_score) >= threshold:
            results.append(
                {
                    "index": index,
                    "benchmark": benchmark,
                    "correlation": latest,
                    "z_score": round(z_score, 4),
                    "ts": observations[-1]["ts"],
                }
            )
    return sorted(results, key=lambda row: abs(row["z_score"]), reverse=True)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--sigma", type=float, default=2.0)
    args = parser.parse_args()
    rows = json.loads(Path(args.input).read_text(encoding="utf-8"))
    print(json.dumps(find_regime_shifts(rows, args.sigma), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
