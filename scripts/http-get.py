#!/usr/bin/env python3
"""GET a read-only Adjacent surface (exports, docs archive, public data).

Backs the export cookbook and docs Q&A workflows: fetch `/export/*`,
`/docs.zip`, or `/public/*` from an Adjacent host and write the bytes to
a file or stdout. Restricted to HTTPS Adjacent hosts. Auth via
`ADJACENT_API_KEY` when set (optional for public surfaces).
"""

from __future__ import annotations

import argparse
import os
import sys

from _http import get


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", required=True, help="HTTPS Adjacent URL to fetch")
    parser.add_argument("--output", help="write body to this path instead of stdout")
    args = parser.parse_args()
    api_key = os.environ.get("ADJACENT_API_KEY")
    try:
        status, body = get(args.url, api_key)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    if status >= 400:
        sys.stderr.write(f"error: HTTP {status}\n")
        sys.stderr.buffer.write(body)
        return 1
    if args.output:
        with open(args.output, "wb") as handle:
            handle.write(body)
    else:
        sys.stdout.buffer.write(body)
    return 0


if __name__ == "__main__":
    sys.exit(main())
