#!/usr/bin/env python3
"""topic-brief.py -- topic update: news + markets + mid quotes (+ charts).

The common interactive loop: user names a topic ("washington football"),
this script returns structured news hits, related markets with mid quotes,
and optional branded chart CSVs/PNGs so the host agent can format a brief.

Discovery rules:
- News: prefer the prod MCP tier when available (dev news find is often
  empty). Fall back to the selected tier.
- Markets: over-fetch candidates (3x the display limit, at least 15),
  carry volume / open-interest hints, price them, then rank:
  real traded series first, then liquid books, then find-quote fallbacks.
- Charts: only for chartable series (non-empty mid history). Never chart
  empty-history find-quote fallbacks.
- Prices: mid-quote only. Never last trade.
- Never invent hits. Empty news or markets is a valid response.
- Use full market and news ids from MCP; never truncate UUIDs.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from _mcp import McpError, fetch
from _paths import state_dir

# Over-fetch multiplier so ranking can prefer liquid / chartable books
# over the first N thin find hits.
MARKET_CANDIDATE_MULTIPLIER = 3
MARKET_CANDIDATE_FLOOR = 15


def _hits(payload: Any) -> list[dict]:
    if isinstance(payload, dict):
        rows = payload.get("hits")
        if isinstance(rows, list):
            return [row for row in rows if isinstance(row, dict)]
    if isinstance(payload, list):
        return [row for row in payload if isinstance(row, dict)]
    return []


def _as_float(value: Any) -> float | None:
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return None
    return None


def _first_number(record: dict, keys: tuple[str, ...]) -> float | None:
    for key in keys:
        if key not in record:
            continue
        number = _as_float(record.get(key))
        if number is not None:
            return number
    return None


def _news_row(row: dict) -> dict | None:
    news_id = row.get("id")
    title = row.get("name") or row.get("title") or row.get("headline")
    if not news_id or not title:
        return None
    return {
        "id": str(news_id),
        "title": str(title),
        "source": row.get("source"),
        "published_date": row.get("published_date") or row.get("published_at"),
        "url": row.get("url"),
        "type": "news",
    }


def _market_stub(row: dict) -> dict | None:
    market_id = row.get("id")
    name = row.get("name") or row.get("title")
    if not market_id or not name:
        return None
    volume = _first_number(
        row,
        (
            "volume_24h",
            "volume24h",
            "volume",
            "vol_24h",
            "yes_volume_24h",
            "dollar_volume_24h",
        ),
    )
    open_interest = _first_number(
        row,
        (
            "open_interest",
            "openInterest",
            "oi",
            "open_interest_contracts",
        ),
    )
    liquidity = 0.0
    if volume is not None:
        liquidity += abs(volume)
    if open_interest is not None:
        liquidity += abs(open_interest)
    return {
        "id": str(market_id),
        "name": str(name),
        "type": "market",
        "probability": row.get("probability"),
        "volume_24h": volume,
        "open_interest": open_interest,
        "liquidity": liquidity,
    }


def candidate_market_limit(display_limit: int) -> int:
    """How many find hits to pull before ranking down to display_limit."""
    display = max(1, int(display_limit))
    return max(MARKET_CANDIDATE_FLOOR, display * MARKET_CANDIDATE_MULTIPLIER)


def _mid_from_price(payload: Any) -> dict:
    """Extract mid/bid/ask from compact or raw price payloads."""
    if not isinstance(payload, dict):
        return {}
    # Nested compact summary shapes.
    for key in ("summary", "latest", "quote", "price"):
        nested = payload.get(key)
        if isinstance(nested, dict):
            mid = nested.get("mid")
            if mid is not None:
                return {
                    "mid": float(mid),
                    "bid": nested.get("bid"),
                    "ask": nested.get("ask"),
                    "as_of": nested.get("as_of") or nested.get("ts") or nested.get("timestamp"),
                    "point_count": 1,
                }
    mid = payload.get("mid")
    if mid is not None:
        return {
            "mid": float(mid),
            "bid": payload.get("bid"),
            "ask": payload.get("ask"),
            "as_of": payload.get("as_of") or payload.get("ts") or payload.get("timestamp"),
            "point_count": 1,
        }
    # Raw timeseries: take the last mid/price point.
    for key in ("points", "series", "candles", "timeseries", "data"):
        rows = payload.get(key)
        if isinstance(rows, list) and rows:
            last = rows[-1]
            if isinstance(last, dict):
                value = last.get("mid", last.get("price", last.get("close", last.get("value"))))
                if value is not None:
                    return {
                        "mid": float(value),
                        "bid": last.get("bid"),
                        "ask": last.get("ask"),
                        "as_of": last.get("ts") or last.get("timestamp") or last.get("time"),
                        "point_count": len(rows),
                    }
    return {}


def find_news(topic: str, tier: str, api_key: str | None, limit: int) -> tuple[list[dict], list[str]]:
    """Prefer prod for news discovery; fall back to the selected tier."""
    warnings: list[str] = []
    tiers: list[str] = []
    if tier != "prod":
        tiers.append("prod")
    tiers.append(tier)
    seen: set[str] = set()
    ordered_tiers = list(dict.fromkeys(tiers))

    for try_tier in ordered_tiers:
        try:
            payload = fetch(
                "find",
                {"query": topic, "type": "news"},
                tier=try_tier,
                api_key=api_key,
            )
        except McpError as exc:
            warnings.append(f"news find on {try_tier} failed: {exc}")
            continue
        rows = []
        for raw in _hits(payload):
            row = _news_row(raw)
            if row is None or row["id"] in seen:
                continue
            seen.add(row["id"])
            rows.append(row)
            if len(rows) >= limit:
                break
        if rows:
            if try_tier != tier:
                warnings.append(
                    f"news hits came from {try_tier} (selected tier {tier} had none or failed)"
                )
            return rows, warnings
    return [], warnings


def find_markets(topic: str, tier: str, api_key: str | None, limit: int) -> tuple[list[dict], list[str]]:
    """Pull market candidates (over-fetched for later ranking)."""
    warnings: list[str] = []
    try:
        payload = fetch(
            "find",
            {"query": topic, "type": "market"},
            tier=tier,
            api_key=api_key,
        )
    except McpError as exc:
        return [], [f"market find failed: {exc}"]
    rows: list[dict] = []
    for raw in _hits(payload):
        row = _market_stub(raw)
        if row is None:
            continue
        rows.append(row)
        if len(rows) >= limit:
            break
    return rows, warnings


def _probability_as_mid(probability) -> float | None:
    """Map find-hit probability (0-100 or 0-1) to a 0-1 mid."""
    if not isinstance(probability, (int, float)):
        return None
    value = float(probability)
    if value > 1.0:
        value = value / 100.0
    if value < 0.0 or value > 1.0:
        return None
    return value


def price_market(
    market_id: str,
    timeframe: str,
    tier: str,
    api_key: str | None,
    *,
    probability=None,
) -> dict:
    errors: list[str] = []
    # Prefer raw so we know whether a series is chartable.
    for raw_flag in (True, False):
        try:
            payload = fetch(
                "price",
                {
                    "id": market_id,
                    "type": "market",
                    "timeframe": timeframe,
                    "raw": raw_flag,
                },
                tier=tier,
                api_key=api_key,
            )
        except McpError as exc:
            errors.append(str(exc))
            continue
        quote = _mid_from_price(payload)
        if "mid" not in quote:
            continue
        point_count = int(quote.pop("point_count", 0) or 0)
        # Raw series with multiple points is chartable; a lone compact mid
        # is quotable but not a history chart.
        chartable = bool(raw_flag and point_count >= 2)
        if not raw_flag and point_count >= 1:
            # Compact mid only - try to confirm history via a second raw call
            # already attempted first. Mark non-chartable.
            chartable = False
        return {
            "id": market_id,
            "ok": True,
            "quote_source": "price",
            "chartable": chartable,
            "point_count": point_count,
            **quote,
        }

    # Some markets have a live probability on find but empty candle history.
    mid = _probability_as_mid(probability)
    if mid is not None:
        return {
            "id": market_id,
            "ok": True,
            "mid": mid,
            "quote_source": "find_probability",
            "chartable": False,
            "point_count": 0,
            "note": "no candle history in window; mid from find probability",
        }

    try:
        detail = fetch(
            "get",
            {"id": market_id, "type": "market"},
            tier=tier,
            api_key=api_key,
        )
    except McpError as exc:
        errors.append(str(exc))
        detail = None
    if isinstance(detail, dict):
        quote = _mid_from_price(detail)
        if "mid" not in quote:
            for key in ("probability", "yes_mid", "last_price", "price"):
                mid = _probability_as_mid(detail.get(key))
                if mid is not None:
                    quote = {"mid": mid}
                    break
        if "mid" in quote:
            quote.pop("point_count", None)
            return {
                "id": market_id,
                "ok": True,
                "quote_source": "get",
                "chartable": False,
                "point_count": 0,
                **quote,
            }

    return {
        "id": market_id,
        "ok": False,
        "chartable": False,
        "point_count": 0,
        "error": errors[-1] if errors else "no mid quote in price payload",
    }


def rank_markets(markets: list[dict]) -> list[dict]:
    """Order: chartable traded series, then liquid books, then find-quote fallbacks."""

    def sort_key(row: dict) -> tuple:
        if not row.get("ok"):
            tier = 9
        elif row.get("chartable"):
            tier = 0
        elif float(row.get("liquidity") or 0) > 0:
            tier = 1
        elif row.get("quote_source") == "price":
            tier = 2
        elif row.get("quote_source") == "find_probability":
            tier = 3
        else:
            tier = 4
        liquidity = float(row.get("liquidity") or 0)
        return (tier, -liquidity, str(row.get("name") or ""))

    return sorted(markets, key=sort_key)


def _load_chart_build():
    """Load hyphenated chart-build.py as a module."""
    import importlib.util

    script = Path(__file__).resolve().parent / "chart-build.py"
    spec = importlib.util.spec_from_file_location("adjacent_chart_build", script)
    if spec is None or spec.loader is None:
        raise RuntimeError("could not load chart-build.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def build_charts(
    market_ids: list[str],
    timeframe: str,
    tier: str,
    api_key: str | None,
    output_dir: Path,
    png: bool,
) -> list[dict]:
    try:
        module = _load_chart_build()
    except Exception as exc:  # noqa: BLE001
        return [{"ok": False, "error": str(exc)}]

    charts: list[dict] = []
    for market_id in market_ids:
        stem = market_id.replace(":", "-").replace("/", "-")
        csv_path = output_dir / f"{stem}.csv"
        try:
            built = module.candles_csv(
                [market_id],
                "market",
                timeframe,
                tier,
                api_key,
                csv_path,
                False,
            )
        except Exception as exc:  # noqa: BLE001 - surface per-market failure
            charts.append({"id": market_id, "ok": False, "error": str(exc)})
            continue
        if not built.get("ok"):
            charts.append({"id": market_id, "ok": False, "error": built.get("error")})
            continue
        points = int(built.get("points") or 0)
        if points < 2:
            charts.append(
                {
                    "id": market_id,
                    "ok": False,
                    "error": "not chartable: fewer than 2 history points",
                    "points": points,
                }
            )
            continue
        entry: dict[str, Any] = {
            "id": market_id,
            "ok": True,
            "csv": str(csv_path),
            "points": points,
        }
        if png:
            png_path = output_dir / f"{stem}.png"
            rendered = module.render_png(
                csv_path,
                png_path,
                headline=market_id,
                deck=f"{timeframe} mid",
            )
            entry["png"] = str(png_path) if rendered.get("ok") else None
            if not rendered.get("ok"):
                entry["png_error"] = rendered.get("error")
                if rendered.get("remedy"):
                    entry["png_remedy"] = rendered["remedy"]
        charts.append(entry)
    return charts


def run_brief(
    topic: str,
    *,
    tier: str,
    api_key: str | None,
    news_limit: int,
    market_limit: int,
    timeframe: str,
    chart: bool,
    png: bool,
    output_dir: Path | None,
) -> dict:
    warnings: list[str] = []

    fetch_limit = candidate_market_limit(market_limit)

    # Run news and market discovery in parallel - each find is a separate
    # MCP round trip (~5-45s), so overlapping them cuts wall time roughly
    # in half for the discovery phase.
    with ThreadPoolExecutor(max_workers=2) as discover_pool:
        news_future = discover_pool.submit(find_news, topic, tier, api_key, news_limit)
        market_future = discover_pool.submit(find_markets, topic, tier, api_key, fetch_limit)
        news, news_warnings = news_future.result()
        candidates, market_warnings = market_future.result()

    warnings.extend(news_warnings)
    warnings.extend(market_warnings)
    if len(candidates) > market_limit:
        warnings.append(
            f"ranked {len(candidates)} market candidates down to {market_limit} "
            "(chartable and liquid first)"
        )

    priced: list[dict] = []
    if candidates:

        def attach_price(market: dict) -> dict:
            quote = price_market(
                market["id"],
                timeframe,
                tier,
                api_key,
                probability=market.get("probability"),
            )
            row = {**market, **{k: v for k, v in quote.items() if k != "id"}}
            row["id"] = market["id"]
            return row

        # 8-worker pricing pool: each price call is an independent MCP round
        # trip (~11s), so parallel pricing is the biggest win for multi-market
        # briefs.
        with ThreadPoolExecutor(max_workers=min(8, max(1, len(candidates)))) as pool:
            priced = list(pool.map(attach_price, candidates))
        priced = rank_markets(priced)[: max(1, market_limit)]

    charts: list[dict] = []
    if chart and priced:
        out = output_dir or (state_dir() / "charts" / "topic-brief")
        out.mkdir(parents=True, exist_ok=True)
        # Only chart markets with real history - never empty find-quote shells.
        chartable_ids = [row["id"] for row in priced if row.get("ok") and row.get("chartable")]
        if not chartable_ids:
            warnings.append(
                "no chartable markets in the ranked set (empty mid history); "
                "agent must pick a substantive market and chart it manually"
            )
        else:
            charts = build_charts(chartable_ids, timeframe, tier, api_key, out, png)

    return {
        "format_version": 1,
        "ok": True,
        "workflow": "topic_brief",
        "topic": topic,
        "as_of": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "tier": tier,
        "basis": "mid-quote",
        "news": news,
        "markets": priced,
        "charts": charts,
        "warnings": warnings,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="Topic update: news, markets, mids, charts.")
    ap.add_argument("topic", help="topic query, e.g. 'washington football'")
    ap.add_argument("--news-limit", type=int, default=5, help="max news hits (default 5)")
    ap.add_argument("--market-limit", type=int, default=5, help="max markets after ranking (default 5)")
    ap.add_argument("--timeframe", default="7d", help="price/chart timeframe (default 7d)")
    ap.add_argument("--chart", action="store_true", help="build candle CSVs for chartable markets")
    ap.add_argument("--png", action="store_true", help="also render branded PNGs (needs matplotlib)")
    ap.add_argument("--output-dir", help="chart artifact directory")
    ap.add_argument("--prod", action="store_true", help="prefer realtime tier when keyed")
    args = ap.parse_args()

    api_key = os.environ.get("ADJACENT_API_KEY")
    tier = "prod" if (args.prod and api_key) else "dev"
    if args.png and not args.chart:
        args.chart = True

    output_dir = Path(args.output_dir).expanduser() if args.output_dir else None
    try:
        result = run_brief(
            args.topic.strip(),
            tier=tier,
            api_key=api_key,
            news_limit=max(1, args.news_limit),
            market_limit=max(1, args.market_limit),
            timeframe=args.timeframe,
            chart=args.chart,
            png=args.png,
            output_dir=output_dir,
        )
    except Exception as exc:  # noqa: BLE001 - top-level JSON error for agents
        json.dump({"ok": False, "error": str(exc), "workflow": "topic_brief"}, sys.stdout, indent=2)
        sys.stdout.write("\n")
        return 1

    json.dump(result, sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
