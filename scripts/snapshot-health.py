#!/usr/bin/env python3
"""Zero-key health checks for Adjacent public snapshots.

The public surfaces (for example ``/api/v1/public/indices``) are live and
need no API key. Many of them return a bare list or object with no
``as_of`` field; when ``--live`` is set this script falls back to the HTTP
``Last-Modified`` or ``Date`` header so a healthy feed is not graded
``error`` solely for missing body metadata.

Descriptor JSON:

    [{"name": "indices",
      "url": "https://api.adjacent.markets/api/v1/public/indices",
      "max_age_minutes": 30}, ...]

Each row is graded fresh, stale, or error against ``max_age_minutes``
(default 60).
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path

from _http import get_with_headers
from _timeparse import parse_timestamp


DEFAULT_MAX_AGE_MINUTES = 60


def parse_ts(value: object) -> datetime:
    return parse_timestamp(value)


def _as_of_from_headers(headers: dict[str, str]) -> str | None:
    for key in ("last-modified", "date"):
        raw = headers.get(key)
        if not raw:
            continue
        try:
            dt = parsedate_to_datetime(raw)
        except (TypeError, ValueError, IndexError):
            continue
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc).isoformat()
    return None


def _as_of_from_payload(payload: object) -> str | None:
    if isinstance(payload, dict):
        for key in ("as_of", "updated_at", "timestamp", "ts"):
            value = payload.get(key)
            if value:
                return str(value)
        # Some index payloads expose updated_at on the first row of a nested list.
        for key in ("data", "indices", "items", "results"):
            nested = payload.get(key)
            if isinstance(nested, list) and nested:
                return _as_of_from_payload(nested[0])
    if isinstance(payload, list) and payload:
        return _as_of_from_payload(payload[0])
    return None


def evaluate(snapshots: list[dict], now: datetime) -> dict:
    rows: list[dict] = []
    for snapshot in snapshots:
        name = str(snapshot.get("name", "unknown"))
        row: dict = {"name": name}
        if snapshot.get("error"):
            row["status"] = "error"
            row["detail"] = str(snapshot["error"])
            rows.append(row)
            continue
        as_of = snapshot.get("as_of")
        if not as_of:
            row["status"] = "error"
            row["detail"] = "missing as_of"
            rows.append(row)
            continue
        # A feed is graded, never fatal: an unparseable timestamp or max
        # age is reported as an error row like any other bad snapshot.
        try:
            max_age = float(snapshot.get("max_age_minutes", DEFAULT_MAX_AGE_MINUTES))
        except (TypeError, ValueError):
            row["status"] = "error"
            row["detail"] = f"invalid max_age_minutes: {snapshot.get('max_age_minutes')!r}"
            rows.append(row)
            continue
        try:
            parsed_as_of = parse_ts(as_of)
        except ValueError as exc:
            row["status"] = "error"
            row["detail"] = str(exc)
            row["as_of"] = str(as_of)
            rows.append(row)
            continue
        age_minutes = (now - parsed_as_of).total_seconds() / 60
        row["age_minutes"] = round(age_minutes, 2)
        row["as_of"] = str(as_of)
        row["status"] = "fresh" if age_minutes <= max_age else "stale"
        rows.append(row)
    healthy = all(row["status"] == "fresh" for row in rows) if rows else False
    return {"healthy": healthy, "checked": len(rows), "snapshots": rows}


def _fetch_live(snapshots: list[dict], api_key: str | None) -> list[dict]:
    resolved: list[dict] = []
    for snapshot in snapshots:
        url = snapshot.get("url")
        if not url:
            resolved.append(snapshot)
            continue
        merged = dict(snapshot)
        try:
            status, body, headers = get_with_headers(str(url), api_key)
        except ValueError as exc:
            merged["error"] = str(exc)
            resolved.append(merged)
            continue
        if status >= 400:
            merged["error"] = f"HTTP {status}"
            resolved.append(merged)
            continue
        try:
            payload = json.loads(body.decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            payload = None
        as_of = None
        if "as_of" not in merged:
            as_of = _as_of_from_payload(payload) if payload is not None else None
            if not as_of:
                as_of = _as_of_from_headers(headers)
            if as_of:
                merged["as_of"] = as_of
        # Empty list with a successful HTTP response is still an error for
        # surfaces that should always have rows.
        if isinstance(payload, list) and len(payload) == 0:
            merged["error"] = "empty list"
        resolved.append(merged)
    return resolved


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, help="path to snapshot descriptor JSON")
    parser.add_argument("--live", action="store_true", help="fetch each url before grading")
    args = parser.parse_args()
    snapshots = json.loads(Path(args.input).read_text(encoding="utf-8"))
    if isinstance(snapshots, dict):
        snapshots = snapshots.get("snapshots", [])
    if args.live:
        snapshots = _fetch_live(snapshots, os.environ.get("ADJACENT_API_KEY"))
    report = evaluate(snapshots, datetime.now(timezone.utc))
    print(json.dumps(report, indent=2))
    return 0 if report["healthy"] else 1


if __name__ == "__main__":
    sys.exit(main())
