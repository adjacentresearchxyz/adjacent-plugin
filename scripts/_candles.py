"""Shared candle / timeseries normalization for chart producers.

Adjacent price payloads are not uniform. Index raw series often look like
``{timestamp, price}`` under a ``points`` key; market candles may carry
``mid``, bid/ask pairs, or Kalshi dollar fields. Chart producers should
import from here instead of re-deriving field priority.
"""

from __future__ import annotations


def as_number(value) -> float | None:
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return None
    return None


def candle_close(candle: dict) -> float | None:
    """Return the mid-based close for a candle, or None when absent.

    Priority:
    1. explicit ``mid``
    2. midpoint of ``bid`` / ``ask``
    3. midpoint of Kalshi yes-side dollar pair
    4. midpoint of no-side dollar pair, inverted to the yes side
    5. explicit ``close`` / ``close_dollars`` / ``yes_close_dollars`` / ``price`` / ``value``
    """
    mid = as_number(candle.get("mid"))
    if mid is not None:
        return mid

    bid = as_number(candle.get("bid"))
    ask = as_number(candle.get("ask"))
    if bid is not None and ask is not None:
        return (bid + ask) / 2

    yes_bid = as_number(candle.get("yes_bid_dollars"))
    yes_ask = as_number(candle.get("yes_ask_dollars"))
    if yes_bid is not None and yes_ask is not None:
        return (yes_bid + yes_ask) / 2

    no_bid = as_number(candle.get("no_bid_dollars"))
    no_ask = as_number(candle.get("no_ask_dollars"))
    if no_bid is not None and no_ask is not None:
        # NO mid of 0.40 is YES mid of 0.60.
        return 1.0 - ((no_bid + no_ask) / 2)

    for key in ("close", "close_dollars", "yes_close_dollars", "price", "value"):
        close = as_number(candle.get(key))
        if close is not None:
            return close
    return None


def candle_ts(candle: dict) -> str | None:
    for key in (
        "ts",
        "timestamp",
        "time",
        "end_period_ts",
        "end_ts",
        "start_ts",
        "start_period_ts",
    ):
        value = candle.get(key)
        if value is None:
            continue
        return str(value)
    return None


def series_rows(payload) -> list:
    """Find timeseries rows in a raw price payload."""
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        for key in ("candles", "series", "timeseries", "points", "data", "items"):
            rows = payload.get(key)
            if isinstance(rows, list):
                return rows
    return []


def to_series(candles: list) -> list[tuple[str, float]]:
    series: list[tuple[str, float]] = []
    for candle in candles:
        if not isinstance(candle, dict):
            continue
        ts = candle_ts(candle)
        close = candle_close(candle)
        if ts is None or close is None:
            continue
        series.append((ts, close))
    series.sort()
    return series


def rebase(series: list[tuple[str, float]]) -> list[tuple[str, float]]:
    if not series:
        return []
    base = series[0][1]
    if base == 0:
        return series
    return [(ts, 100.0 * value / base) for ts, value in series]
