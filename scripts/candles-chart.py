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
   `price`, or `value`

Timestamps accept `ts`, `timestamp`, `time`, `end_period_ts`, `end_ts`,
`start_ts`, or `start_period_ts`, in that order. Normalization lives in
`_candles.py` so chart-build and this script stay aligned.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

from _candles import candle_close, candle_ts, rebase, series_rows, to_series

# Re-export for tests and callers that import this script module.
__all__ = ["candle_close", "candle_ts", "rebase", "to_series"]


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
    candles = series_rows(json.loads(Path(args.input).read_text(encoding="utf-8")))
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
