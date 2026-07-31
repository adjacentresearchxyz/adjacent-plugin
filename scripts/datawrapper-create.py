#!/usr/bin/env python3
"""datawrapper-create.py -- create a new Datawrapper chart from a CSV on stdin or file.

Auth via `DATAWRAPPER_API_KEY`. Returns the new chart id on stdout so the
caller can pipe it into `datawrapper-publish.py <chart-id>` for future
updates.

Usage:
  cat data.csv | datawrapper-create.py --title "<chart title>"
  datawrapper-create.py --title "<chart title>" --csv path/to/data.csv
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any
from urllib import request as urlrequest
from urllib.error import HTTPError

DATAWRAPPER_API_KEY = os.environ.get("DATAWRAPPER_API_KEY", "")
BASE = "https://api.datawrapper.de"


def post(path: str, body: dict[str, Any] | None = None, raw: bytes | None = None, ctype: str = "application/json") -> dict[str, Any]:
    data = raw if raw is not None else (json.dumps(body).encode("utf-8") if body else None)
    req = urlrequest.Request(
        BASE + path,
        method="POST",
        data=data,
        headers={
            "Authorization": f"Bearer {DATAWRAPPER_API_KEY}",
            "Content-Type": ctype,
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
    ap.add_argument("--title", required=True)
    ap.add_argument("--csv", help="path to a CSV file; default reads stdin")
    args = ap.parse_args()
    if args.csv:
        csv_bytes = Path(args.csv).read_bytes()
    elif not sys.stdin.isatty():
        csv_bytes = sys.stdin.buffer.read()
    else:
        print("error: no CSV input", file=sys.stderr)
        return 2
    created = post(
        "/v3/charts",
        body={"title": args.title, "type": "d3-lines" if b"," in csv_bytes[:300] else "tables"},
    )
    if "error" in created:
        json.dump(created, sys.stdout, indent=2)
        sys.stdout.write("\n")
        return 3
    chart_id = created.get("id") or created.get("data", {}).get("id")
    if not chart_id:
        json.dump(created, sys.stdout, indent=2)
        sys.stdout.write("\n")
        return 3
    upload = post(f"/v3/charts/{chart_id}/data", raw=csv_bytes, ctype="text/csv")
    if "error" in upload:
        json.dump(upload, sys.stdout, indent=2)
        sys.stdout.write("\n")
        return 4
    json.dump({"chart_id": chart_id, "public_url": f"https://datawrapper.de/chart/{chart_id}"}, sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
