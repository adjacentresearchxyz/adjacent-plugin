from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from tests._hookutil import ROOT, load_script


# ----- catalog_check -----

def test_catalog_check_blocks_when_placeholder_true(tmp_path, monkeypatch):
    module = load_script("rebalance-index.py")
    monkeypatch.setenv("ADJACENT_DATA_DIR", str(tmp_path))
    catalog = tmp_path / "adjacent_direct_indices.json"
    catalog.write_text(json.dumps({
        "_schema": {"_placeholders": {"value": True}}
    }))
    refuse, path = module.catalog_check()
    assert refuse is True


def test_catalog_check_allows_when_placeholder_false(tmp_path, monkeypatch):
    module = load_script("rebalance-index.py")
    monkeypatch.setenv("ADJACENT_DATA_DIR", str(tmp_path))
    catalog = tmp_path / "adjacent_direct_indices.json"
    catalog.write_text(json.dumps({
        "_schema": {"_placeholders": {"value": False}}
    }))
    refuse, path = module.catalog_check()
    assert refuse is False


def test_catalog_check_blocks_when_file_missing(tmp_path, monkeypatch):
    module = load_script("rebalance-index.py")
    monkeypatch.setenv("ADJACENT_DATA_DIR", str(tmp_path))
    refuse, path = module.catalog_check()
    assert refuse is True


def test_catalog_check_blocks_when_schema_missing(tmp_path, monkeypatch):
    module = load_script("rebalance-index.py")
    monkeypatch.setenv("ADJACENT_DATA_DIR", str(tmp_path))
    catalog = tmp_path / "adjacent_direct_indices.json"
    catalog.write_text(json.dumps({"indices": []}))
    refuse, path = module.catalog_check()
    assert refuse is True


# ----- weekend gate -----

def test_weekend_gate_detects_saturday(monkeypatch):
    module = load_script("rebalance-index.py")

    class FakeDateTime:
        @staticmethod
        def now(tz):
            class FakeDate:
                def weekday(self):
                    return 5  # Saturday
            return FakeDate()

    monkeypatch.setattr(module, "datetime", FakeDateTime)
    assert module.is_weekend_utc() is True


def test_weekend_gate_detects_weekday(monkeypatch):
    module = load_script("rebalance-index.py")

    class FakeDateTime:
        @staticmethod
        def now(tz):
            class FakeDate:
                def weekday(self):
                    return 1  # Tuesday
            return FakeDate()

    monkeypatch.setattr(module, "datetime", FakeDateTime)
    assert module.is_weekend_utc() is False


# ----- order construction -----

def test_kalshi_order_buy_uses_mid_price():
    module = load_script("rebalance-index.py")
    order = module._kalshi_order("buy", {"market_id": "kalshi:DEMO-A", "size": 10, "mid": 0.65}, "demo")
    assert order["action"] == "buy"
    assert order["side"] == "yes"
    assert order["count"] == 10
    assert order["yes_price"] == 65  # 0.65 * 100, rounded
    assert order["type"] == "limit"
    assert order["ticker"] == "DEMO-A"
    assert "demo" in order["client_order_id"]


def test_kalshi_order_sell_uses_mid_minus_one():
    module = load_script("rebalance-index.py")
    order = module._kalshi_order("sell", {"market_id": "kalshi:DEMO-A", "size": 5, "mid": 0.65}, "demo")
    assert order["action"] == "sell"
    assert order["yes_price"] == 64  # 65 - 1


def test_kalshi_order_clamps_extreme_prices():
    module = load_script("rebalance-index.py")
    order_high = module._kalshi_order("buy", {"market_id": "kalshi:X", "size": 1, "mid": 1.5}, "demo")
    assert order_high["yes_price"] == 99  # clamped to max
    order_low = module._kalshi_order("buy", {"market_id": "kalshi:X", "size": 1, "mid": 0.001}, "demo")
    assert order_low["yes_price"] == 1  # clamped to min (0.1 rounds to 0, clamped to 1)


# ----- dry-run and JSON bypass -----

def test_dry_run_bypasses_catalog_check(tmp_path, monkeypatch):
    monkeypatch.setenv("ADJACENT_DATA_DIR", str(tmp_path))
    # No catalog file created - would block if catalog check ran.
    plan = tmp_path / "plan.json"
    plan.write_text(json.dumps({"index": "demo", "sells": [], "buys": []}))
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts/rebalance-index.py"),
         "--index", "demo", "--plan", str(plan), "--dry-run"],
        capture_output=True, text=True, check=False,
    )
    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert payload["index"] == "demo"


def test_json_mode_bypasses_catalog_check(tmp_path, monkeypatch):
    monkeypatch.setenv("ADJACENT_DATA_DIR", str(tmp_path))
    plan = tmp_path / "plan.json"
    plan.write_text(json.dumps({"index": "demo", "sells": [], "buys": []}))
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts/rebalance-index.py"),
         "--index", "demo", "--plan", str(plan), "--json"],
        capture_output=True, text=True, check=False,
    )
    assert result.returncode == 0


# ----- partial-failure dispatch (characterization) -----

def test_kalshi_adapter_continues_after_http_error(monkeypatch):
    module = load_script("rebalance-index.py")
    # Set up env so the adapter doesn't bail on missing env for API key,
    # but leaves RSA key path empty so it reports missing env.
    monkeypatch.setattr(module, "KALSHI_API_KEY", "test-key")
    monkeypatch.setattr(module, "KALSHI_RSA_KEY_PATH", "")
    results, missing = module.kalshi_adapter({"index": "demo", "sells": [], "buys": []})
    assert "KALSHI_RSA_KEY_PATH" in missing
    assert results["sells"] == []
    assert results["buys"] == []
