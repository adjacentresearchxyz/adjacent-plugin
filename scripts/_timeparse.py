"""Shared timestamp parsing for the analysis workflows.

Adjacent surfaces are not uniform about timestamp encoding: index and
snapshot payloads use ISO 8601 (often with a trailing ``Z``), while
several market and news rows carry a numeric epoch under keys such as
``ts``. news-latest.py maps whichever key it finds into
``published_at``, so a downstream consumer that assumed ISO would raise
on a perfectly valid row.

``parse_timestamp`` accepts either encoding and always returns a
timezone-aware UTC datetime. Callers that grade rather than crash
should catch ValueError and record the message.
"""

from __future__ import annotations

from datetime import datetime, timezone


# Epoch values above this are treated as milliseconds. 10^11 seconds is
# year 5138, far past any real timestamp, while 10^11 ms is 1973 - so
# any millisecond timestamp from the last few decades lands above it.
_MILLISECOND_CUTOFF = 10**11


def parse_timestamp(value: object) -> datetime:
    """Parse an ISO 8601 string or a numeric epoch into aware UTC.

    Raises ValueError with a descriptive message for anything else.
    """
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)

    if isinstance(value, bool):
        raise ValueError(f"not a timestamp: {value!r}")

    if isinstance(value, (int, float)):
        return _from_epoch(float(value))

    if not isinstance(value, str):
        raise ValueError(f"not a timestamp: {value!r}")

    text = value.strip()
    if not text:
        raise ValueError("empty timestamp")

    # A bare number in a string is an epoch, not an ISO date.
    try:
        return _from_epoch(float(text))
    except ValueError:
        pass

    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        raise ValueError(f"unrecognized timestamp: {text!r}") from None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _from_epoch(raw: float) -> datetime:
    seconds = raw / 1000.0 if abs(raw) >= _MILLISECOND_CUTOFF else raw
    try:
        return datetime.fromtimestamp(seconds, tz=timezone.utc)
    except (OverflowError, OSError, ValueError):
        raise ValueError(f"epoch out of range: {raw!r}") from None
