#!/usr/bin/env python3
"""datawrapper-publish.py -- push a new CSV to an existing Datawrapper chart id.

The chart id is positional so the script works for any chart the caller
manages. Pair with `datawrapper-create.py` for the first publish, then
re-run with this script to refresh.

Usage:
  cat data.csv | datawrapper-publish.py <chart-id>
  datawrapper-publish.py <chart-id> --csv /path/to/data.csv
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime
from zoneinfo import ZoneInfo

from _datawrapper import post, read_csv


ET = ZoneInfo("America/New_York")


def main() -> int:
    api_key = os.environ.get("DATAWRAPPER_API_KEY")
    if not api_key:
        print("error: DATAWRAPPER_API_KEY unset", file=sys.stderr)
        return 1
    ap = argparse.ArgumentParser()
    ap.add_argument("chart_id")
    ap.add_argument("--csv", help="path to a CSV file; default reads stdin")
    ap.add_argument("--no-publish", action="store_true")
    args = ap.parse_args()
    try:
        csv_bytes = read_csv(args.csv)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    r1 = post(
        api_key,
        f"/v3/charts/{args.chart_id}/data",
        raw=csv_bytes,
        content_type="text/csv",
    )
    if "error" in r1:
        json.dump({"stage": "data", **r1}, sys.stdout, indent=2)
        sys.stdout.write("\n")
        return 3
    if not args.no_publish:
        r2 = post(
            api_key,
            f"/v3/charts/{args.chart_id}/publish",
            raw=b"",
            content_type="text/csv",
        )
        if "error" in r2:
            json.dump({"stage": "publish", **r2}, sys.stdout, indent=2)
            sys.stdout.write("\n")
            return 4
    payload = {
        "chart": f"https://datawrapper.de/chart/{args.chart_id}",
        "csv_length": len(csv_bytes.splitlines()),
    }
    if not args.no_publish:
        published_et = datetime.now(ET).strftime("%Y-%m-%d %H:%M")
        payload["published_at"] = f"{published_et} ET"
    else:
        payload["published_at"] = "skipped (--no-publish)"
    json.dump(payload, sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
