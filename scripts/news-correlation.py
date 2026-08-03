#!/usr/bin/env python3
"""Rank supplied news events by the following minute-aligned mid move."""

from __future__ import annotations

import argparse
import bisect
import json
from datetime import datetime, timedelta
from pathlib import Path


def parse_ts(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def correlate(
    articles: list[dict],
    prices: list[dict],
    window_minutes: int,
) -> list[dict]:
    rows_by_market: dict[str, list[tuple[datetime, float]]] = {}
    for row in prices:
        rows_by_market.setdefault(row["market_id"], []).append(
            (parse_ts(row["ts"]).replace(second=0, microsecond=0), float(row["mid"]))
        )
    series: dict[str, tuple[list[datetime], list[tuple[datetime, float]]]] = {}
    for market_id, rows in rows_by_market.items():
        rows.sort()
        series[market_id] = ([ts for ts, _mid in rows], rows)

    results: list[dict] = []
    for article in articles:
        market_id = article["market_id"]
        timestamps, rows = series.get(market_id, ([], []))
        if len(rows) < 2:
            continue
        published = parse_ts(article["published_at"]).replace(second=0, microsecond=0)
        before_index = bisect.bisect_right(timestamps, published) - 1
        after_index = bisect.bisect_right(
            timestamps, published + timedelta(minutes=window_minutes)
        ) - 1
        if before_index < 0 or after_index <= before_index:
            continue
        before = rows[before_index][1]
        after = rows[after_index][1]
        move_pct = (after - before) / before * 100
        results.append(
            {
                "market_id": market_id,
                "published_at": article["published_at"],
                "headline": article["headline"],
                "move_pct": round(move_pct, 4),
            }
        )
    return sorted(results, key=lambda row: abs(row["move_pct"]), reverse=True)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--news", required=True)
    parser.add_argument("--prices", required=True)
    parser.add_argument("--window-minutes", type=int, default=30)
    args = parser.parse_args()
    articles = json.loads(Path(args.news).read_text(encoding="utf-8"))
    prices = json.loads(Path(args.prices).read_text(encoding="utf-8"))
    print(json.dumps(correlate(articles, prices, args.window_minutes), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
