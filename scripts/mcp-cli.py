#!/usr/bin/env python3
"""mcp-cli.py -- ad-hoc command-line MCP client for the Adjacent MCP.

Subcommands match the live tool schemas:

    find  <query> [--type TYPE]
    get   <id> --type TYPE
    list  [--type TYPE]
    price <id> <timeframe> --type TYPE [--raw]

Auth via ``ADJACENT_API_KEY`` (optional). With a key, calls the realtime
tier; without, the public 15-min-delayed tier.

Used by cron jobs and tests where an agent host is unavailable.
"""

from __future__ import annotations

import argparse
import json
import os
import sys

from _mcp import DEFAULT_HOST, call
from _venue import fetch_quote


ENTITY_TYPES = ["index", "rate", "event", "market", "news"]
PRICE_TYPES = ["index", "rate", "event", "market"]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default=DEFAULT_HOST)
    ap.add_argument("--endpoint", default="/mcp")
    sub = ap.add_subparsers(dest="tool", required=True)

    list_p = sub.add_parser("list")
    list_p.add_argument(
        "--type",
        default="event",
        choices=ENTITY_TYPES + ["events", "markets", "indices"],
        help="entity kind to list (default: event)",
    )

    find_p = sub.add_parser("find")
    find_p.add_argument("query", help="free-text topic / name / ticker")
    find_p.add_argument("--type", choices=ENTITY_TYPES, default=None)

    get_p = sub.add_parser("get")
    get_p.add_argument("id")
    get_p.add_argument(
        "--type",
        required=True,
        choices=ENTITY_TYPES,
        help="required entity type (index/rate/event/market/news)",
    )

    price_p = sub.add_parser("price")
    price_p.add_argument("id", help="prefixed market id or index/rate slug")
    price_p.add_argument("timeframe", help='human timeframe, e.g. "24h", "7d"')
    price_p.add_argument(
        "--type",
        required=True,
        choices=PRICE_TYPES,
        help="required entity type (index/rate/event/market)",
    )
    price_p.add_argument("--raw", action="store_true")
    price_p.add_argument(
        "--fallback-venue",
        choices=["kalshi", "polymarket"],
        help="on Adjacent failure, read a public venue orderbook for a prefixed market id",
    )
    price_p.add_argument("--side", choices=["yes", "no"], default="yes")
    # Accept legacy --slug flag as an alias for positional id clarity in docs.
    price_p.add_argument(
        "--slug",
        dest="legacy_slug",
        default=None,
        help=argparse.SUPPRESS,
    )

    args = ap.parse_args()
    api_key = os.environ.get("ADJACENT_API_KEY")
    tool_args: dict = {}

    if args.tool == "list":
        kind = args.type
        # Normalize plural aliases used in older scripts.
        kind = {
            "events": "event",
            "markets": "market",
            "indices": "index",
        }.get(kind, kind)
        tool_args = {"type": kind}
    elif args.tool == "find":
        tool_args = {"query": args.query}
        if args.type:
            tool_args["type"] = args.type
    elif args.tool == "get":
        tool_args = {"id": args.id, "type": args.type}
    elif args.tool == "price":
        entity_id = args.legacy_slug or args.id
        tool_args = {
            "id": entity_id,
            "type": args.type,
            "timeframe": args.timeframe,
            "raw": bool(args.raw),
        }

    res = call(args.host, api_key, args.endpoint, args.tool, tool_args)
    if (
        args.tool == "price"
        and args.fallback_venue
        and args.type == "market"
        and isinstance(res, dict)
        and "error" in res
    ):
        try:
            quote = fetch_quote(entity_id, side=args.side)
            if quote["venue"] != args.fallback_venue:
                raise ValueError(
                    f"market id venue is {quote['venue']}, not {args.fallback_venue}"
                )
            json.dump({"fallback": True, **quote}, sys.stdout, indent=2)
            sys.stdout.write("\n")
            return 0
        except Exception as exc:  # noqa: BLE001 - report fallback failure
            res = {
                "error": {
                    "message": f"Adjacent price failed and {args.fallback_venue} fallback failed: {exc}"
                }
            }
    json.dump(res, sys.stdout, indent=2)
    sys.stdout.write("\n")
    if "error" in res:
        return 1
    result = res.get("result") if isinstance(res, dict) else None
    if isinstance(result, dict) and result.get("isError"):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
