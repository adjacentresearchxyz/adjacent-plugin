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

from _datawrapper import post, read_csv


def main() -> int:
    api_key = os.environ.get("DATAWRAPPER_API_KEY")
    if not api_key:
        print("error: DATAWRAPPER_API_KEY unset", file=sys.stderr)
        return 1
    ap = argparse.ArgumentParser()
    ap.add_argument("--title", required=True)
    ap.add_argument("--csv", help="path to a CSV file; default reads stdin")
    args = ap.parse_args()
    try:
        csv_bytes = read_csv(args.csv)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    created = post(
        api_key,
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
    upload = post(
        api_key,
        f"/v3/charts/{chart_id}/data",
        raw=csv_bytes,
        content_type="text/csv",
    )
    if "error" in upload:
        json.dump(upload, sys.stdout, indent=2)
        sys.stdout.write("\n")
        return 4
    json.dump({"chart_id": chart_id, "public_url": f"https://datawrapper.de/chart/{chart_id}"}, sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
