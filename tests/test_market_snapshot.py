from __future__ import annotations

import sys
import time
from concurrent.futures import ThreadPoolExecutor

from tests._hookutil import load_script


def _make_enrich_safe(module):
    """Return a closure that wraps enrich() with McpError -> skip-dict handling."""
    def _enrich_safe(row):
        try:
            return module.enrich(row, "dev", None, "24h"), None
        except module.McpError as exc:
            return row, {"id": row["id"], "reason": str(exc)[:200]}
    return _enrich_safe


# --------------------------------------------------------------------------
# Step 1: import sanity
# --------------------------------------------------------------------------


def test_load_script_exposes_base_row_and_enrich():
    module = load_script("market-snapshot.py")
    assert callable(module.base_row)
    assert callable(module.enrich)
    assert callable(module.fetch)
    assert module.McpError is not None


# --------------------------------------------------------------------------
# Step 2: base_row tests
# --------------------------------------------------------------------------


def test_base_row_extracts_id_and_name():
    module = load_script("market-snapshot.py")
    raw = {
        "market_id": "kalshi:abc",
        "name": "Will ABC close above 50?",
        "price": "0.55",
        "kind": "market",
    }
    row = module.base_row(raw)
    assert row["id"] == "kalshi:abc"
    assert row["name"] == "Will ABC close above 50?"
    assert row["mid"] == 0.55
    assert row["mid_source"] == "reported_price"
    assert row["platform"] == "kalshi"
    assert row["kind"] == "market"
    assert row["tradable"] is True


def test_base_row_handles_missing_price():
    module = load_script("market-snapshot.py")
    raw = {"market_id": "kalshi:abc", "name": "No price here"}
    row = module.base_row(raw)
    assert row["mid"] is None
    assert row["mid_source"] is None
    assert row["tradable"] is False


def test_base_row_extracts_weight():
    module = load_script("market-snapshot.py")
    raw = {"market_id": "kalshi:abc", "name": "Weighted", "weight": "0.25"}
    row = module.base_row(raw)
    assert row["weight"] == 0.25


# --------------------------------------------------------------------------
# Step 3: enrich tests with mocked fetch
# --------------------------------------------------------------------------


def test_enrich_adds_bid_ask_mid(monkeypatch):
    module = load_script("market-snapshot.py")

    def fake_fetch(tool, args, **kw):
        assert tool == "price"
        return {"bid": 0.40, "ask": 0.60, "mid": 0.50}

    monkeypatch.setattr(module, "fetch", fake_fetch)
    row = module.base_row({"market_id": "kalshi:abc", "name": "A", "price": "0.50"})
    out = module.enrich(row, "dev", None, "24h")
    assert out["mid"] == 0.5
    assert out["bid"] == 0.4
    assert out["ask"] == 0.6
    assert out["spread"] == 0.2
    assert out["mid_source"] == "bid_ask"


def test_enrich_derives_mid_from_bid_ask(monkeypatch):
    module = load_script("market-snapshot.py")

    def fake_fetch(tool, args, **kw):
        # No explicit mid; enrich must derive it.
        return {"bid": 0.30, "ask": 0.70}

    monkeypatch.setattr(module, "fetch", fake_fetch)
    row = module.base_row({"market_id": "kalshi:abc", "name": "A", "price": "0.50"})
    out = module.enrich(row, "dev", None, "24h")
    assert out["mid"] == 0.5
    assert out["mid_source"] == "bid_ask"
    assert out["spread"] == 0.4


def test_enrich_extracts_move_pct(monkeypatch):
    module = load_script("market-snapshot.py")

    def fake_fetch(tool, args, **kw):
        # move is a fraction (0.025) and must be scaled to 2.5%.
        return {"bid": 0.40, "ask": 0.60, "mid": 0.50, "move": 0.025}

    monkeypatch.setattr(module, "fetch", fake_fetch)
    row = module.base_row({"market_id": "kalshi:abc", "name": "A", "price": "0.50"})
    out = module.enrich(row, "dev", None, "24h")
    assert out["move_1d_pct"] == 2.5


def test_enrich_safe_returns_skip_on_mcp_error(monkeypatch):
    module = load_script("market-snapshot.py")

    def fake_fetch(tool, args, **kw):
        raise module.McpError("boom")

    monkeypatch.setattr(module, "fetch", fake_fetch)
    row = module.base_row({"market_id": "kalshi:abc", "name": "A", "price": "0.50"})

    _enrich_safe = _make_enrich_safe(module)

    out_row, skip = _enrich_safe(row)
    assert skip is not None
    assert skip["id"] == "kalshi:abc"
    assert skip["reason"] == "boom"
    # The original row is returned unenriched.
    assert out_row["id"] == "kalshi:abc"
    assert out_row["bid"] is None


# --------------------------------------------------------------------------
# Step 4: parallel enrich ordering and skipped-row tests
# --------------------------------------------------------------------------


def _make_base_row(market_id: str, name: str) -> dict:
    return {
        "id": market_id,
        "name": name,
        "platform": market_id.split(":")[0],
        "kind": "market",
        "mid": None,
        "mid_source": None,
        "bid": None,
        "ask": None,
        "spread": None,
        "volume_24h": None,
        "move_1d_pct": None,
        "expires": None,
        "weight": None,
        "tradable": False,
    }


def test_parallel_enrich_preserves_order(monkeypatch):
    module = load_script("market-snapshot.py")

    # Vary the response time per id so threads finish out of order.
    delays = {"kalshi:A": 0.05, "kalshi:B": 0.01, "kalshi:C": 0.03}

    def fake_fetch(tool, args, **kw):
        mid = delays.get(args.get("id"), 0.01)
        time.sleep(mid)
        return {"bid": 0.40, "ask": 0.60, "mid": 0.50}

    monkeypatch.setattr(module, "fetch", fake_fetch)

    base_rows = [
        _make_base_row("kalshi:A", "A"),
        _make_base_row("kalshi:B", "B"),
        _make_base_row("kalshi:C", "C"),
    ]

    _enrich_safe = _make_enrich_safe(module)

    with ThreadPoolExecutor(max_workers=3) as pool:
        results = list(pool.map(_enrich_safe, base_rows))

    rows = [r for r, _ in results]
    skipped = [s for _, s in results if s is not None]

    assert [r["id"] for r in rows] == ["kalshi:A", "kalshi:B", "kalshi:C"]
    assert all(r["mid"] == 0.5 for r in rows)
    assert skipped == []


def test_parallel_enrich_isolates_failure(monkeypatch):
    module = load_script("market-snapshot.py")

    def fake_fetch(tool, args, **kw):
        if args.get("id") == "kalshi:BAD":
            raise module.McpError("price unavailable")
        return {"bid": 0.40, "ask": 0.60, "mid": 0.50}

    monkeypatch.setattr(module, "fetch", fake_fetch)

    base_rows = [
        _make_base_row("kalshi:GOOD1", "G1"),
        _make_base_row("kalshi:BAD", "B"),
        _make_base_row("kalshi:GOOD2", "G2"),
    ]

    _enrich_safe = _make_enrich_safe(module)

    with ThreadPoolExecutor(max_workers=3) as pool:
        results = list(pool.map(_enrich_safe, base_rows))

    rows = [r for r, _ in results]
    skipped = [s for _, s in results if s is not None]

    assert [r["id"] for r in rows] == ["kalshi:GOOD1", "kalshi:BAD", "kalshi:GOOD2"]
    # The failed row is unenriched.
    bad_row = next(r for r in rows if r["id"] == "kalshi:BAD")
    assert bad_row["bid"] is None
    assert bad_row["mid"] is None
    # The good rows are enriched.
    good_rows = [r for r in rows if r["id"] != "kalshi:BAD"]
    assert all(r["mid"] == 0.5 for r in good_rows)
    # The failure is recorded in skipped.
    assert len(skipped) == 1
    assert skipped[0]["id"] == "kalshi:BAD"
    assert "price unavailable" in skipped[0]["reason"]


def test_parallel_enrich_empty_input():
    module = load_script("market-snapshot.py")

    base_rows: list[dict] = []

    _enrich_safe = _make_enrich_safe(module)

    if base_rows:
        with ThreadPoolExecutor(max_workers=min(8, len(base_rows))) as pool:
            results = list(pool.map(_enrich_safe, base_rows))
    else:
        results = []

    rows = [r for r, _ in results]
    skipped = [s for _, s in results if s is not None]

    assert rows == []
    assert skipped == []


def test_no_quotes_returns_base_rows():
    module = load_script("market-snapshot.py")

    # When want_quotes is False the loop is skipped entirely; rows equals
    # base_rows with no enrichment. Simulate that branch directly.
    raw_rows = [
        {"market_id": "kalshi:A", "name": "A", "price": "0.50"},
        {"market_id": "kalshi:B", "name": "B", "price": "0.60"},
    ]
    base_rows = [module.base_row(raw) for raw in raw_rows if module.base_row(raw)["id"]]

    want_quotes = False
    if want_quotes and base_rows:
        rows = []
    else:
        rows = base_rows

    assert [r["id"] for r in rows] == ["kalshi:A", "kalshi:B"]
    # No enrichment happened: bid/ask remain None, mid comes from reported price.
    assert all(r["bid"] is None for r in rows)
    assert all(r["ask"] is None for r in rows)
    assert rows[0]["mid"] == 0.5
    assert rows[1]["mid"] == 0.6
    assert all(r["mid_source"] == "reported_price" for r in rows)
