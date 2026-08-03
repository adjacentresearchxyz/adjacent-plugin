#!/usr/bin/env python3
"""Fetch the latest Adjacent news via the live news surface.

The `news/latest` surface is live. This script pulls it through the
Adjacent MCP `list` tool (type=news) and can normalize the response into
the article shape that news-correlation.py consumes:

    [{"market_id": ..., "published_at": ..., "headline": ...}, ...]

Auth via `ADJACENT_API_KEY` (optional). Without a key the public
15-min-delayed tier is used.
"""

from __future__ import annotations

import argparse
import json
import os
import sys

from _mcp import DEFAULT_HOST, call


_HEADLINE_KEYS = ("headline", "title", "name")
_PUBLISHED_KEYS = ("published_at", "publishedAt", "published", "timestamp", "ts")
_MARKET_KEYS = ("market_id", "marketId", "market", "slug", "id")


def _first(record: dict, keys: tuple[str, ...]) -> str | None:
    for key in keys:
        value = record.get(key)
        if isinstance(value, (str, int, float)) and str(value):
            return str(value)
    return None


def iter_records(response: dict):
    """Yield candidate article dicts from an MCP tool response.

    Handles both structured `result.content` shapes (a list whose text
    fields carry JSON) and a plain list result. Never raises; unknown
    shapes simply yield nothing.
    """
    result = response.get("result", response)
    payloads: list = []
    if isinstance(result, dict):
        content = result.get("content")
        if isinstance(content, list):
            for item in content:
                text = item.get("text") if isinstance(item, dict) else None
                if isinstance(text, str):
                    try:
                        payloads.append(json.loads(text))
                    except json.JSONDecodeError:
                        continue
                elif isinstance(item, dict):
                    payloads.append(item)
        else:
            payloads.append(result)
    elif isinstance(result, list):
        payloads.append(result)
    for payload in payloads:
        rows = payload
        if isinstance(payload, dict):
            for key in ("news", "articles", "items", "data", "results"):
                if isinstance(payload.get(key), list):
                    rows = payload[key]
                    break
        if isinstance(rows, list):
            for row in rows:
                if isinstance(row, dict):
                    yield row


def normalize_articles(response: dict) -> list[dict]:
    """Best-effort mapping of an MCP news response into article rows.

    Rows missing a market id or headline are skipped. This does not
    invent fields; it only maps known aliases.
    """
    articles: list[dict] = []
    for record in iter_records(response):
        market_id = _first(record, _MARKET_KEYS)
        headline = _first(record, _HEADLINE_KEYS)
        published_at = _first(record, _PUBLISHED_KEYS)
        if not market_id or not headline or not published_at:
            continue
        articles.append(
            {
                "market_id": market_id,
                "published_at": published_at,
                "headline": headline,
            }
        )
    return articles


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--endpoint", default="/mcp")
    parser.add_argument(
        "--normalize",
        action="store_true",
        help="emit article rows shaped for news-correlation.py",
    )
    args = parser.parse_args()
    api_key = os.environ.get("ADJACENT_API_KEY")
    response = call(args.host, api_key, args.endpoint, "list", {"type": "news"})
    if "error" in response:
        json.dump(response, sys.stdout, indent=2)
        sys.stdout.write("\n")
        return 1
    payload = normalize_articles(response) if args.normalize else response
    json.dump(payload, sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
