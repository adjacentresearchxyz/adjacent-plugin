#!/usr/bin/env python3
"""brief-daily.py -- end-to-end daily / index brief.

Resolves a watchlist, fetches mid-quote moves for every slug, applies the
index-mover thresholds, and emits both structured movers and the formatted
brief text. One call replaces the fetch-then-format loop a host agent would
otherwise drive by hand.

Watchlist resolution, most specific first:

1. ``--slugs a,b,c``
2. ``data/watchlist.json`` when it holds entries
3. a live ``list(type=index)``, capped by ``--limit``

Thresholds (mid-based, from AGENTS.md): 1D at 1.5%, 7D at 4%. Fewer than
three flagged movers is a quiet day and the brief says so rather than
padding. All percentages are mid-quote; `pp` is never emitted.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from _mcp import McpError, fetch
from _paths import data_dir, scripts_dir

THRESHOLD_1D = 1.5
THRESHOLD_7D = 4.0
QUIET_BELOW = 3

# Keys the price surface may use for a period move, most explicit first.
MOVE_KEYS = ("move", "move_pct", "change_pct", "pct_change", "change")
# Identifier keys the price surface accepts, most specific first. The
# display name is never an id.
ID_KEYS = ("index_id", "slug", "id", "ticker")


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


def extract_move_pct(payload) -> float | None:
    """Pull a percent move out of a price payload, or derive it from open/close.

    Values already expressed as a fraction (abs <= 1) are scaled to percent
    so a 0.021 move and a 2.1 move mean the same thing downstream.
    """
    if not isinstance(payload, dict):
        return None

    body = payload
    for nested in ("summary", "data", "price"):
        inner = body.get(nested)
        if isinstance(inner, dict):
            body = {**inner, **{k: v for k, v in body.items() if k != nested}}
            break

    for key in MOVE_KEYS:
        move = _as_float(body.get(key))
        if move is not None:
            return move * 100.0 if abs(move) <= 1.0 else move

    open_px = _as_float(body.get("open"))
    close_px = _as_float(body.get("close") or body.get("mid") or body.get("last"))
    if open_px and close_px is not None:
        return ((close_px - open_px) / open_px) * 100.0
    return None


def load_watchlist() -> list[str]:
    path = data_dir() / "watchlist.json"
    if not path.is_file():
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    entries = payload.get("indices") or payload.get("slugs") or payload.get("watchlist")
    if isinstance(entries, list):
        return [str(item) for item in entries if isinstance(item, (str, int))]
    return []


def index_rows(tier: str, api_key: str | None) -> list[dict]:
    """Fetch the index list once. Rows already carry prices and closes."""
    payload = fetch("list", {"type": "index"}, tier=tier, api_key=api_key)
    rows = payload
    if isinstance(payload, dict):
        rows = payload.get("data") or payload.get("items") or payload.get("results") or []
    return [row for row in rows if isinstance(row, dict)] if isinstance(rows, list) else []


def row_id(row: dict) -> str | None:
    """The identifier the price surface accepts. Never the display name."""
    for key in ID_KEYS:
        value = row.get(key)
        if value not in (None, ""):
            return str(value)
    return None


def moves_from_row(row: dict) -> tuple[float | None, float | None]:
    """Derive 1D and 7D percent moves from a list row.

    The list already reports every close we need, so a scan costs one
    request rather than two per index. 1D has no packaged change field and
    is derived from the latest price against the prior close.
    """
    latest = _as_float(row.get("latest_price"))
    prev_1d = _as_float(row.get("previous_close_1d"))
    move_1d = None
    if latest is not None and prev_1d:
        move_1d = ((latest - prev_1d) / prev_1d) * 100.0

    move_7d = _as_float(row.get("change_7d"))
    if move_7d is None:
        prev_7d = _as_float(row.get("previous_close_7d"))
        if latest is not None and prev_7d:
            move_7d = ((latest - prev_7d) / prev_7d) * 100.0
    return move_1d, move_7d


def latest_news(tier: str) -> list[dict]:
    """Pull the live news surface through the existing normalizer."""
    script = scripts_dir() / "news-latest.py"
    if not script.is_file():
        return []
    host = "mcp.adjacent.markets" if tier == "prod" else "mcp.dev.adjacent.markets"
    proc = subprocess.run(
        [sys.executable, str(script), "--normalize", "--host", host],
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        return []
    try:
        payload = json.loads(proc.stdout)
    except json.JSONDecodeError:
        return []
    rows = payload.get("articles") if isinstance(payload, dict) else payload
    return rows if isinstance(rows, list) else []


def price_moves(slug: str, tier: str, api_key: str | None) -> tuple[float | None, float | None]:
    """Fall back to the price surface for a slug the index list did not carry."""
    day = fetch(
        "price",
        {"id": slug, "type": "index", "timeframe": "24h", "raw": False},
        tier=tier,
        api_key=api_key,
    )
    move_1d = extract_move_pct(day)
    try:
        week = fetch(
            "price",
            {"id": slug, "type": "index", "timeframe": "7d", "raw": False},
            tier=tier,
            api_key=api_key,
        )
        move_7d = extract_move_pct(week)
    except McpError:
        move_7d = None
    return move_1d, move_7d


def flag(move_1d: float, move_7d: float | None) -> list[str]:
    horizons = []
    if abs(move_1d) >= THRESHOLD_1D:
        horizons.append("1D")
    if move_7d is not None and abs(move_7d) >= THRESHOLD_7D:
        horizons.append("7D")
    return horizons


def scan(
    slugs: list[str] | None,
    rows: list[dict],
    tier: str,
    api_key: str | None,
) -> tuple[list[dict], list[dict]]:
    """Score the requested slugs, preferring the already-fetched list rows."""
    by_id = {row_id(row): row for row in rows if row_id(row)}
    targets = slugs if slugs is not None else list(by_id)

    movers: list[dict] = []
    skipped: list[dict] = []
    for slug in targets:
        row = by_id.get(slug)
        if row is not None and row.get("halted"):
            skipped.append({"slug": slug, "reason": "index is halted"})
            continue

        if row is not None:
            move_1d, move_7d = moves_from_row(row)
            name = row.get("name")
        else:
            try:
                move_1d, move_7d = price_moves(slug, tier, api_key)
            except McpError as exc:
                skipped.append({"slug": slug, "reason": str(exc)[:200]})
                continue
            name = None

        if move_1d is None:
            skipped.append({"slug": slug, "reason": "no mid-quote move available"})
            continue

        horizons = flag(move_1d, move_7d)
        movers.append(
            {
                "slug": slug,
                "name": name,
                "move_1d": round(move_1d, 4),
                "move_7d": round(move_7d, 4) if move_7d is not None else None,
                "flagged": bool(horizons),
                "horizons": horizons,
            }
        )

    movers.sort(key=lambda row: abs(row["move_1d"]), reverse=True)
    return movers, skipped


def render(movers: list[dict], news: list[dict], as_of: str, quiet: bool) -> str:
    lines = [f"{as_of} adjacent"]
    if quiet:
        lines.append("briefing-too-quiet")
        return "\n".join(lines)

    headline_by_slug: dict[str, str] = {}
    for article in news:
        slug = article.get("slug") or article.get("index") or article.get("id")
        title = article.get("title") or article.get("headline")
        if slug and title and str(slug) not in headline_by_slug:
            headline_by_slug[str(slug)] = str(title)

    for row in movers:
        if not row["flagged"]:
            continue
        week = f", 7d {row['move_7d']:+.2f}%" if row["move_7d"] is not None else ""
        reason = headline_by_slug.get(row["slug"], "")
        suffix = f" {reason}" if reason else ""
        lines.append(f"- {row['slug']}: 1d {row['move_1d']:+.2f}%{week}{suffix}")
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser(description="Run the Adjacent daily brief end to end.")
    ap.add_argument("--slugs", help="comma-separated index slugs; overrides the watchlist")
    ap.add_argument("--prod", action="store_true", help="use the realtime tier (needs a key)")
    ap.add_argument("--with-news", action="store_true", help="attach live news headlines")
    ap.add_argument("--limit", type=int, default=10, help="max slugs when discovering live")
    ap.add_argument("--output", help="write the JSON result to this path as well as stdout")
    args = ap.parse_args()

    api_key = os.environ.get("ADJACENT_API_KEY")
    tier = "prod" if (args.prod and api_key) else "dev"

    slugs: list[str] | None
    if args.slugs:
        slugs, source = [s.strip() for s in args.slugs.split(",") if s.strip()], "args"
    else:
        watchlist = load_watchlist()
        slugs, source = (watchlist, "watchlist") if watchlist else (None, "live-list")

    try:
        rows = index_rows(tier, api_key)
    except McpError as exc:
        if slugs is None:
            json.dump({"ok": False, "error": str(exc)}, sys.stdout, indent=2)
            sys.stdout.write("\n")
            return 1
        rows = []

    movers, skipped = scan(
        slugs[: args.limit] if slugs is not None else None, rows[: args.limit], tier, api_key
    )
    news = latest_news(tier) if args.with_news else []
    flagged = [row for row in movers if row["flagged"]]
    quiet = len(flagged) < QUIET_BELOW
    as_of = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    result = {
        "format_version": 1,
        "ok": True,
        "as_of": as_of,
        "tier": tier,
        "source": source,
        "thresholds": {"1d_pct": THRESHOLD_1D, "7d_pct": THRESHOLD_7D},
        "basis": "mid-quote",
        "unit": "%",
        "movers": movers,
        "flagged_count": len(flagged),
        "skipped": skipped,
        "quiet": quiet,
        "news_attached": len(news),
        "text": render(movers, news, as_of, quiet),
    }

    if args.output:
        out = Path(args.output).expanduser()
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
        result["artifact"] = str(out)

    json.dump(result, sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
