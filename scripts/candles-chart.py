#!/usr/bin/env python3
"""Build a chart CSV from Adjacent market candles.

The `markets/{id}/candles` surface is live. Fetch candles via the MCP
`price` tool (raw timeseries) or supply a candle JSON file, then this
script emits a mid-based `ts,close` CSV for the Adjacent chart pipeline.

Never substitutes last trade for mid. Each candle contributes a close
derived from, in priority order:

1. explicit `mid`
2. midpoint of `bid` / `ask`
3. midpoint of the Kalshi yes-side dollar pair (`yes_bid_dollars` /
   `yes_ask_dollars`)
4. midpoint of the no-side dollar pair, inverted to the yes side
5. explicit mid-derived `close`, `close_dollars`, `yes_close_dollars`,
   or `price`

Timestamps accept `ts`, `timestamp`, `end_period_ts`, `end_ts`,
`start_ts`, or `start_period_ts`, in that order.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path


def _num(value) -> float | None:
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return None
    return None


def candle_close(candle: dict) -> float | None:
    """Return the mid-based close for a candle, or None when absent."""
    mid = _num(candle.get("mid"))
    if mid is not None:
        return mid

    bid = _num(candle.get("bid"))
    ask = _num(candle.get("ask"))
    if bid is not None and ask is not None:
        return (bid + ask) / 2

    # Kalshi candlestick shape: dollar fields on yes/no sides.
    yes_bid = _num(candle.get("yes_bid_dollars"))
    yes_ask = _num(candle.get("yes_ask_dollars"))
    if yes_bid is not None and yes_ask is not None:
        return (yes_bid + yes_ask) / 2

    no_bid = _num(candle.get("no_bid_dollars"))
    no_ask = _num(candle.get("no_ask_dollars"))
    if no_bid is not None and no_ask is not None:
        # NO mid of 0.40 is YES mid of 0.60.
        return 1.0 - ((no_bid + no_ask) / 2)

    for key in ("close", "close_dollars", "yes_close_dollars", "price"):
        close = _num(candle.get(key))
        if close is not None:
            return close
    return None


def candle_ts(candle: dict) -> str | None:
    for key in ("ts", "timestamp", "end_period_ts", "end_ts", "start_ts", "start_period_ts"):
        value = candle.get(key)
        if value is None:
            continue
        return str(value)
    return None


def to_series(candles: list[dict]) -> list[tuple[str, float]]:
    series: list[tuple[str, float]] = []
    for candle in candles:
        ts = candle_ts(candle)
        close = candle_close(candle)
        if ts is None or close is None:
            continue
        series.append((ts, close))
    series.sort()
    return series


def rebase(series: list[tuple[str, float]]) -> list[tuple[str, float]]:
    if not series:
        return []
    base = series[0][1]
    if base == 0:
        return series
    return [(ts, 100.0 * value / base) for ts, value in series]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, help="path to candle JSON")
    parser.add_argument("--output", help="write CSV to this path instead of stdout")
    parser.add_argument(
        "--rebase",
        action="store_true",
        help="rebase closes to 100 at the first candle",
    )
    args = parser.parse_args()
    candles = json.loads(Path(args.input).read_text(encoding="utf-8"))
    if isinstance(candles, dict):
        candles = candles.get("candles", candles.get("series", candles.get("data", [])))
    series = to_series(candles)
    if args.rebase:
        series = rebase(series)
    target = open(args.output, "w", encoding="utf-8", newline="") if args.output else sys.stdout
    try:
        writer = csv.writer(target)
        writer.writerow(["ts", "close"])
        for ts, close in series:
            writer.writerow([ts, f"{close:.4f}"])
    finally:
        if args.output:
            target.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
