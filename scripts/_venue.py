"""Read-only live quote fallbacks for supported prediction-market venues."""

from __future__ import annotations

import json
from typing import Any
from urllib.parse import quote as url_quote
from urllib.request import Request, urlopen


KALSHI_BASE = "https://external-api.kalshi.com/trade-api/v2"
POLYMARKET_BASE = "https://clob.polymarket.com"


def parse_market_id(market_id: str) -> tuple[str, str] | None:
    """Require an explicit supported venue prefix."""
    if ":" not in market_id:
        return None
    venue, raw = market_id.split(":", 1)
    if venue not in {"kalshi", "polymarket"} or not raw:
        return None
    return venue, raw


def _best(levels: Any, *, maximum: bool) -> float | None:
    values = []
    for level in levels or []:
        if isinstance(level, dict):
            value = level.get("price")
        elif isinstance(level, (list, tuple)) and level:
            value = level[0]
        else:
            value = None
        if value is not None:
            values.append(float(value))
    return (max(values) if maximum else min(values)) if values else None


def _quote(bid: float, ask: float, venue: str) -> dict[str, Any]:
    bid = round(bid, 8)
    ask = round(ask, 8)
    if not (0.0 <= bid <= ask <= 1.0):
        raise ValueError(f"{venue} returned invalid quote bid={bid} ask={ask}")
    return {
        "bid": bid,
        "ask": ask,
        "mid": round((bid + ask) / 2.0, 8),
        "venue": venue,
        "basis": "mid-quote",
    }


def kalshi_quote(payload: dict[str, Any], *, side: str = "yes") -> dict[str, Any]:
    """Normalize Kalshi yes/no bid-only books to a bid/ask/mid quote."""
    book = payload.get("orderbook_fp") or payload.get("orderbook") or {}
    yes_bid = _best(book.get("yes_dollars"), maximum=True)
    no_bid = _best(book.get("no_dollars"), maximum=True)
    if yes_bid is None or no_bid is None:
        raise ValueError("Kalshi orderbook has no two-sided quote")
    if side == "yes":
        return _quote(yes_bid, 1.0 - no_bid, "kalshi")
    if side == "no":
        return _quote(no_bid, 1.0 - yes_bid, "kalshi")
    raise ValueError("side must be yes or no")


def polymarket_quote(payload: dict[str, Any]) -> dict[str, Any]:
    """Normalize a Polymarket CLOB book to a bid/ask/mid quote."""
    bid = _best(payload.get("bids"), maximum=True)
    ask = _best(payload.get("asks"), maximum=False)
    if bid is None or ask is None:
        raise ValueError("Polymarket orderbook has no two-sided quote")
    return _quote(bid, ask, "polymarket")


def fetch_quote(market_id: str, *, side: str = "yes") -> dict[str, Any]:
    parsed = parse_market_id(market_id)
    if parsed is None:
        raise ValueError(
            "fallback requires an explicit market id prefix: "
            "kalshi:<ticker> or polymarket:<token_id>"
        )
    venue, raw = parsed
    if venue == "kalshi":
        url = f"{KALSHI_BASE}/markets/{url_quote(raw, safe='')}/orderbook"
    else:
        url = f"{POLYMARKET_BASE}/book?token_id={url_quote(raw, safe='')}"
    req = Request(url, headers={"Accept": "application/json", "User-Agent": "adjacent-plugin/0.2"})
    with urlopen(req, timeout=20) as response:
        payload = json.loads(response.read().decode("utf-8"))
    if venue == "kalshi":
        quote = kalshi_quote(payload, side=side)
    elif venue == "polymarket":
        quote = polymarket_quote(payload)
    else:
        raise ValueError(f"unsupported venue: {venue}")
    quote["market_id"] = market_id
    return quote
