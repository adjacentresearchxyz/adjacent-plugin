"""Read-only venue quote fallback contract tests."""

from __future__ import annotations

from tests.test_offline_signals import load_script


def test_kalshi_orderbook_normalizes_yes_bid_and_reciprocal_ask():
    module = load_script("_venue.py")
    quote = module.kalshi_quote(
        {
            "orderbook_fp": {
                "yes_dollars": [["0.42", "10"]],
                "no_dollars": [["0.55", "8"]],
            }
        },
        side="yes",
    )
    assert quote == {
        "bid": 0.42,
        "ask": 0.45,
        "mid": 0.435,
        "venue": "kalshi",
        "basis": "mid-quote",
    }


def test_polymarket_orderbook_uses_best_bid_and_ask():
    module = load_script("_venue.py")
    quote = module.polymarket_quote(
        {
            "bids": [{"price": "0.40", "size": "2"}],
            "asks": [{"price": "0.46", "size": "3"}],
        }
    )
    assert quote["bid"] == 0.40
    assert quote["ask"] == 0.46
    assert quote["mid"] == 0.43
    assert quote["venue"] == "polymarket"


def test_market_id_parser_requires_explicit_supported_venue():
    module = load_script("_venue.py")
    assert module.parse_market_id("kalshi:KXTEST-26") == ("kalshi", "KXTEST-26")
    assert module.parse_market_id("polymarket:123456") == ("polymarket", "123456")
    assert module.parse_market_id("KXTEST-26") is None
