#!/usr/bin/env python3
"""mcp-cli.py -- ad-hoc command-line MCP client for the Adjacent MCP.

Subcommands:

    find  <topic>       -- run find tool
    get   <id>          -- run get tool
    list  [type]        -- run list tool (defaults to events)
    price <slug> <tf>   -- run price tool

Auth via `ADJACENT_API_KEY` (optional). With a key, calls the realtime tier
endpoint; without, the public 15-min-delayed tier.

Used by cron jobs and tests where the full Claude Code runtime is
overkill or unavailable.
"""

from __future__ import annotations

import argparse
import http.client
import json
import os
import ssl
import sys
from urllib.parse import urlparse, urlencode

DEFAULT_HOST = "mcp.adjacent.markets"
DEFAULT_PORT_TLS = 443


def build_url(host: str, api_key: str | None, endpoint: str = "/mcp") -> str:
    base = f"https://{host}{endpoint}"
    if api_key:
        sep = "&" if "?" in base else "?"
        base = f"{base}{sep}apiKey={api_key}"
    return base


def call(host: str, api_key: str | None, tool: str, args: dict) -> dict:
    url = build_url(host, api_key)
    parsed = urlparse(url)
    is_tls = parsed.scheme == "https"
    conn: http.client.HTTPConnection | http.client.HTTPSConnection
    if is_tls:
        ctx = ssl.create_default_context()
        conn = http.client.HTTPSConnection(parsed.hostname, parsed.port or DEFAULT_PORT_TLS, context=ctx, timeout=15)
    else:
        conn = http.client.HTTPConnection(parsed.hostname, parsed.port or 80, timeout=15)
    body = json.dumps(
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {"name": tool, "arguments": args},
        }
    ).encode("utf-8")
    path = parsed.path + ("?" + parsed.query if parsed.query else "")
    headers = {"Content-Type": "application/json", "Accept": "application/json"}
    # Adjacent accepts the apiKey as a URL query param only; do not also send
    # an Authorization header (that combination is rejected by the server).
    conn.request("POST", path, body=body, headers=headers)
    resp = conn.getresponse()
    return json.loads(resp.read().decode("utf-8"))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default=DEFAULT_HOST)
    ap.add_argument("--endpoint", default="/mcp")
    sub = ap.add_subparsers(dest="tool", required=True)
    list_p = sub.add_parser("list")
    list_p.add_argument(
        "--type",
        default="events",
        choices=["events", "event", "market", "markets", "index", "indices", "rate", "rates", "news"],
        help="entity kind to list (default: events)",
    )
    sub.add_parser("find").add_argument("topic")
    sub.add_parser("get").add_argument("id")
    p = sub.add_parser("price")
    p.add_argument("slug")
    p.add_argument("timeframe")
    p.add_argument("--raw", action="store_true")
    args = ap.parse_args()
    api_key = os.environ.get("ADJACENT_API_KEY")
    tool_args = {}
    if args.tool == "list":
        tool_args = {"type": args.type}
    elif args.tool == "find":
        tool_args = {"topic": args.topic}
    elif args.tool == "get":
        tool_args = {"id": args.id}
    elif args.tool == "price":
        tool_args = {"slug": args.slug, "timeframe": args.timeframe, "raw": args.raw}
    res = call(args.host, api_key, args.tool, tool_args)
    json.dump(res, sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0 if "error" not in res else 1


if __name__ == "__main__":
    sys.exit(main())
