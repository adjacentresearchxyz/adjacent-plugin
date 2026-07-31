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
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib import request as urlrequest
from urllib.error import HTTPError
from zoneinfo import ZoneInfo

DATAWRAPPER_API_KEY = os.environ.get("DATAWRAPPER_API_KEY", "")
BASE = "https://api.datawrapper.de"
ET = ZoneInfo("America/New_York")


def post(path: str, raw: bytes, ctype: str = "text/csv") -> dict[str, Any]:
    req = urlrequest.Request(
        BASE + path,
        method="POST",
        data=raw,
        headers={
            "Authorization": f"Bearer {DATAWRAPPER_API_KEY}",
            "Content-Type": ctype,
            "User-Agent": "adjacent-plugin/0.1 datawrapper-publish",
        },
    )
    try:
        with urlrequest.urlopen(req, timeout=20) as resp:
            text = resp.read().decode("utf-8")
            return json.loads(text) if text and text.startswith("{") else {"raw": text}
    except HTTPError as e:
        return {"error": e.code, "body": e.read().decode("utf-8", errors="replace")}


def main() -> int:
    if not DATAWRAPPER_API_KEY:
        print("error: DATAWRAPPER_API_KEY unset", file=sys.stderr)
        return 1
    ap = argparse.ArgumentParser()
    ap.add_argument("chart_id")
    ap.add_argument("--csv", help="path to a CSV file; default reads stdin")
    ap.add_argument("--no-publish", action="store_true")
    args = ap.parse_args()
    if args.csv:
        csv_bytes = Path(args.csv).read_bytes()
    elif not sys.stdin.isatty():
        csv_bytes = sys.stdin.buffer.read()
    else:
        print("error: no CSV input", file=sys.stderr)
        return 2
    r1 = post(f"/v3/charts/{args.chart_id}/data", raw=csv_bytes)
    if "error" in r1:
        json.dump({"stage": "data", **r1}, sys.stdout, indent=2)
        sys.stdout.write("\n")
        return 3
    if not args.no_publish:
        r2 = post(f"/v3/charts/{args.chart_id}/publish", raw=b"")
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
