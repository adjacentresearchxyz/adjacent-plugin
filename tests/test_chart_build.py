from __future__ import annotations

import csv

from tests.test_offline_signals import load_script


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
