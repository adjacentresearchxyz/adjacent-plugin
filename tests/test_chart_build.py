from __future__ import annotations

import csv

from tests.test_offline_signals import load_script


def test_derive_headline_single_series_states_finding():
    module = load_script("chart-build.py")
    columns = {"RED": [100.0, 100.4, 100.9, 101.2, 101.6, 102.1, 102.4]}
    headline = module._derive_headline(columns, "7d")
    # States the last value, direction, and percent move - not a raw slug.
    assert headline.startswith("RED at 102.4")
    assert "up 2.4%" in headline
    assert "over 7d" in headline
    # No em-dash, no pp.
    assert "\u2014" not in headline
    assert "pp" not in headline


def test_derive_headline_fraction_series_uses_percent_value():
    module = load_script("chart-build.py")
    # A market mid series is 0-1 fractions; the last value reads as a percent.
    columns = {"kalshi:abc": [0.40, 0.41, 0.42]}
    headline = module._derive_headline(columns, "1d")
    assert "kalshi abc at 42.0%" in headline
    assert "up 5.0%" in headline
    assert "over 1d" in headline


def test_derive_headline_down_series():
    module = load_script("chart-build.py")
    columns = {"BLUE": [105.0, 104.0, 103.0]}
    headline = module._derive_headline(columns, "7d")
    assert "BLUE at 103.0" in headline
    assert "down 1.9%" in headline


def test_derive_headline_multi_series_is_generic_non_slug():
    module = load_script("chart-build.py")
    columns = {"RED": [100.0, 101.0], "BLUE": [100.0, 99.0]}
    headline = module._derive_headline(columns, "7d")
    assert "2 mid-quote series compared over 7d" == headline
    assert "pp" not in headline


def test_candles_csv_accepts_timestamp_price_rows(monkeypatch, tmp_path):
    """Live index raw series uses {timestamp, price} under points."""
    module = load_script("chart-build.py")

    def fake_fetch(*args, **kwargs):
        return {
            "count": 2,
            "id": "red",
            "interval": "1hour",
            "points": [
                {"timestamp": "2026-08-06T12:00:00Z", "price": 96.4},
                {"timestamp": "2026-08-06T13:00:00Z", "price": 96.5},
            ],
            "timeframe": "7d",
            "type": "indices",
        }

    monkeypatch.setattr(module, "fetch", fake_fetch)
    output = tmp_path / "chart.csv"

    result = module.candles_csv(
        ["RED"],
        "index",
        "7d",
        "dev",
        None,
        output,
        False,
    )

    assert result == {"ok": True, "points": 2, "series": 1}
    with output.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    assert rows == [
        {"ts": "2026-08-06T12:00:00Z", "RED": "96.4"},
        {"ts": "2026-08-06T13:00:00Z", "RED": "96.5"},
    ]


def test_candles_csv_prefers_mid_over_price(monkeypatch, tmp_path):
    module = load_script("chart-build.py")

    def fake_fetch(*args, **kwargs):
        return {
            "series": [
                {"ts": "2026-08-06T12:00:00Z", "mid": 0.40, "price": 0.99},
                {"ts": "2026-08-06T12:01:00Z", "mid": 0.41, "price": 0.99},
            ]
        }

    monkeypatch.setattr(module, "fetch", fake_fetch)
    output = tmp_path / "chart.csv"

    result = module.candles_csv(
        ["MKT"],
        "market",
        "7d",
        "dev",
        None,
        output,
        False,
    )

    assert result["ok"] is True
    with output.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    assert rows == [
        {"ts": "2026-08-06T12:00:00Z", "MKT": "0.4"},
        {"ts": "2026-08-06T12:01:00Z", "MKT": "0.41"},
    ]


def test_candles_csv_uses_bid_ask_midpoint(monkeypatch, tmp_path):
    module = load_script("chart-build.py")

    def fake_fetch(*args, **kwargs):
        return {
            "candles": [
                {"timestamp": "2026-08-06T12:00:00Z", "bid": 0.40, "ask": 0.42},
            ]
        }

    monkeypatch.setattr(module, "fetch", fake_fetch)
    output = tmp_path / "chart.csv"

    result = module.candles_csv(
        ["MKT"],
        "market",
        "7d",
        "dev",
        None,
        output,
        False,
    )

    assert result == {"ok": True, "points": 1, "series": 1}
    with output.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) == 1
    assert rows[0]["ts"] == "2026-08-06T12:00:00Z"
    assert abs(float(rows[0]["MKT"]) - 0.41) < 1e-9


def test_candles_csv_rejects_empty_points(monkeypatch, tmp_path):
    module = load_script("chart-build.py")

    def fake_fetch(*args, **kwargs):
        return {
            "count": 0,
            "id": "red",
            "points": [],
            "type": "markets",
        }

    monkeypatch.setattr(module, "fetch", fake_fetch)
    output = tmp_path / "chart.csv"

    result = module.candles_csv(
        ["RED"],
        "market",
        "7d",
        "dev",
        None,
        output,
        False,
    )

    assert result["ok"] is False
    assert "no timeseries returned for RED" in result["error"]
