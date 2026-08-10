#!/usr/bin/env python3
"""market-snapshot.py -- standardized tradable snapshot.

Turns a topic, an index, or an explicit id list into one normalized table a
trader can act on: every row carries the same fields in the same units, with
mid quotes and an explicit spread rather than a last-trade print.

Resolution, most specific first:

1. ``--ids kalshi:abc,kalshi:def``
2. ``--index <slug>`` (the index constituents)
3. ``--query <topic>`` (a live find)

Emits JSON on stdout and, with ``--csv``, the same rows as a CSV artifact.
Prices are mid: ``mid = (bid + ask) / 2``. Percentages use `%`, never `pp`.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

from _mcp import McpError, fetch

COLUMNS = [
    "id",
    "name",
    "platform",
    "kind",
    "mid",
    "bid",
    "ask",
    "spread",
    "volume_24h",
    "move_1d_pct",
    "expires",
    "weight",
    "mid_source",
    "tradable",
]


def _as_float(value) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value.strip().rstrip("%"))
        except ValueError:
            return None
    return None


def _first(payload: dict, *keys):
    for key in keys:
        if key in payload and payload[key] not in (None, ""):
            return payload[key]
    return None


def _rows_of(payload):
    """Find the row list, unwrapping the one-level {"data": [...]} envelope."""
    if isinstance(payload, list):
        return payload
    if not isinstance(payload, dict):
        return []
    for key in ("constituents", "items", "results", "data", "markets"):
        value = payload.get(key)
        if isinstance(value, list):
            return value
        if isinstance(value, dict):
            for inner in ("data", "items", "results"):
                rows = value.get(inner)
                if isinstance(rows, list):
                    return rows
    return []


def _id_of(row) -> str | None:
    if isinstance(row, str):
        return row
    if isinstance(row, dict):
        value = _first(row, "market_id", "id", "ticker", "slug", "index_id")
        return str(value) if value else None
    return None


def base_row(raw: dict) -> dict:
    """Build a snapshot row from what the resolution payload already carried.

    Constituent rows ship a price, volume, and expiry, so the common case
    costs no extra request. There is no bid/ask at this level, so mid is
    taken from the reported price and mid_source records that: downstream
    tracking math needs to know whether a spread was available.
    """
    market_id = _id_of(raw) or ""
    price = _as_float(_first(raw, "price", "mid", "latest_price"))
    kind = _first(raw, "kind", "type") or "market"
    return {
        "id": market_id,
        "name": _first(raw, "name", "title", "question") or market_id,
        "platform": _first(raw, "platform", "exchange") or market_id.split(":")[0],
        "kind": kind,
        "mid": round(price, 6) if price is not None else None,
        "mid_source": "reported_price" if price is not None else None,
        "bid": None,
        "ask": None,
        "spread": None,
        "volume_24h": _as_float(_first(raw, "volume", "volume_24h", "open_interest")),
        "move_1d_pct": None,
        "expires": _first(raw, "end_date", "expires", "expiration", "close_time"),
        "weight": _as_float(raw.get("weight")),
        "tradable": kind == "market" and price is not None,
    }


def resolve_rows(args, tier: str, api_key: str | None) -> tuple[list[dict], str]:
    """Resolve the request into raw rows, preferring payloads that carry data."""
    if args.ids:
        return [{"market_id": i.strip()} for i in args.ids.split(",") if i.strip()], "ids"
    if args.index:
        payload = fetch("get", {"id": args.index, "type": "index"}, tier=tier, api_key=api_key)
        return [r for r in _rows_of(payload) if isinstance(r, dict)], "index"
    payload = fetch("find", {"query": args.query, "type": "market"}, tier=tier, api_key=api_key)
    return [r for r in _rows_of(payload) if isinstance(r, dict)], "query"


def enrich(row: dict, tier: str, api_key: str | None, timeframe: str) -> dict:
    """Add the quote leg: bid, ask, a true mid, and the period move."""
    market_id = row["id"]
    entity = "index" if row.get("kind") == "index" else "market"
    quote = fetch(
        "price",
        {"id": market_id, "type": entity, "timeframe": timeframe, "raw": False},
        tier=tier,
        api_key=api_key,
    )
    quote = quote if isinstance(quote, dict) else {}

    bid = _as_float(_first(quote, "bid", "yes_bid", "bid_price"))
    ask = _as_float(_first(quote, "ask", "yes_ask", "ask_price"))
    mid = _as_float(_first(quote, "mid", "mid_price"))
    if mid is None and bid is not None and ask is not None:
        mid = (bid + ask) / 2.0

    move = _as_float(_first(quote, "move", "move_pct", "change_pct"))
    if move is not None and abs(move) <= 1.0:
        move *= 100.0

    if mid is not None:
        row["mid"] = round(mid, 6)
        row["mid_source"] = "bid_ask" if (bid is not None and ask is not None) else "reported_mid"
    row["bid"] = round(bid, 6) if bid is not None else None
    row["ask"] = round(ask, 6) if ask is not None else None
    row["spread"] = round(ask - bid, 6) if (bid is not None and ask is not None) else None
    if move is not None:
        row["move_1d_pct"] = round(move, 4)
    volume = _as_float(_first(quote, "volume_24h", "volume", "volume24h"))
    if volume is not None:
        row["volume_24h"] = volume
    row["tradable"] = bool(row.get("kind") == "market" and row.get("mid") is not None)
    return row


def write_csv(rows: list[dict], path: Path) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=COLUMNS)
        writer.writeheader()
        for row in rows:
            writer.writerow({column: row.get(column) for column in COLUMNS})
    return str(path)


def main() -> int:
    ap = argparse.ArgumentParser(description="Build a normalized tradable market snapshot.")
    source = ap.add_mutually_exclusive_group(required=True)
    source.add_argument("--ids", help="comma-separated market ids in platform:raw form")
    source.add_argument("--index", help="index slug; snapshots its constituents")
    source.add_argument("--query", help="free-text topic to resolve into markets")
    ap.add_argument("--limit", type=int, default=25, help="max rows (default 25)")
    ap.add_argument("--timeframe", default="24h", help="quote timeframe (default 24h)")
    ap.add_argument("--quotes", action="store_true", help="add the bid/ask quote leg per row")
    ap.add_argument("--csv", help="also write the rows to this CSV path")
    ap.add_argument("--prod", action="store_true", help="use the realtime tier (needs a key)")
    args = ap.parse_args()

    api_key = os.environ.get("ADJACENT_API_KEY")
    tier = "prod" if (args.prod and api_key) else "dev"

    try:
        raw_rows, resolved_by = resolve_rows(args, tier, api_key)
    except McpError as exc:
        json.dump({"ok": False, "error": str(exc)}, sys.stdout, indent=2)
        sys.stdout.write("\n")
        return 1

    rows: list[dict] = []
    skipped: list[dict] = []
    # An id list carries no data of its own, so it always needs the quote leg.
    want_quotes = args.quotes or resolved_by == "ids"

    # Build base rows first so enrichment can run in parallel.
    base_rows = []
    for raw in raw_rows[: args.limit]:
        row = base_row(raw)
        if row["id"]:
            base_rows.append(row)

    if want_quotes and base_rows:
        def _enrich_safe(row: dict) -> tuple[dict, dict | None]:
            try:
                return enrich(row, tier, api_key, args.timeframe), None
            except McpError as exc:
                return row, {"id": row["id"], "reason": str(exc)[:200]}

        # Each enrich() call is an independent MCP price round trip, so
        # parallel pricing is the biggest win for multi-row snapshots.
        with ThreadPoolExecutor(max_workers=min(8, len(base_rows))) as pool:
            results = list(pool.map(_enrich_safe, base_rows))
        for row, skip in results:
            if skip is not None:
                skipped.append(skip)
            rows.append(row)
    else:
        rows = base_rows

    result = {
        "format_version": 1,
        "ok": True,
        "as_of": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "tier": tier,
        "resolved_by": resolved_by,
        "basis": "mid-quote",
        "unit": "%",
        "columns": COLUMNS,
        "rows": rows,
        "row_count": len(rows),
        "skipped": skipped,
    }
    if args.csv:
        result["artifact"] = write_csv(rows, Path(args.csv).expanduser())

    json.dump(result, sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
