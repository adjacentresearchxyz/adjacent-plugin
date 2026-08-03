"""test_regressions.py - regression cover for previously shipped bugs.

Each test here pins a specific defect that reached the package and was
fixed. They are grouped by the surface that broke rather than by
script, so a future refactor that reintroduces the failure mode trips
the test closest to the behaviour a caller depends on.
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def load_script(name: str):
    path = ROOT / "scripts" / name
    scripts_path = str(path.parent)
    if scripts_path not in sys.path:
        sys.path.insert(0, scripts_path)
    spec = importlib.util.spec_from_file_location(path.stem.replace("-", "_"), path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _write(path: Path, payload) -> Path:
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


# --- chart CSV: gaps between the two series -------------------------------


def test_chart_index_tolerates_series_with_different_timestamps(tmp_path):
    """The index and portfolio series are rebased independently and rarely
    share an identical timestamp set. A missing point must render as an
    empty cell, not raise on formatting an empty string as a float."""
    positions = tmp_path / "positions"
    positions.mkdir(parents=True)
    _write(
        positions / "demo.index.series.json",
        {"series": [{"ts": "2026-01-01T00:00:00Z", "value": 100.0},
                    {"ts": "2026-01-01T00:01:00Z", "value": 101.0}]},
    )
    _write(
        positions / "demo.portfolio.series.json",
        {"series": [{"ts": "2026-01-01T00:00:00Z", "value": 50.0},
                    {"ts": "2026-01-01T00:02:00Z", "value": 51.0}]},
    )
    (positions / "demo.last_fill_ts").write_text("2026-01-01T00:00:00Z", encoding="utf-8")

    proc = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "chart-index.py"), "--index", "demo"],
        capture_output=True,
        text=True,
        env={"PATH": "/usr/bin:/bin", "ADJACENT_DATA_DIR": str(tmp_path)},
    )
    assert proc.returncode == 0, proc.stderr
    lines = proc.stdout.strip().splitlines()
    assert lines[0] == "ts,index,portfolio"
    # Row present in one series only leaves the other column blank.
    assert lines[2] == "2026-01-01T00:01:00Z,101.0000,"
    assert lines[3] == "2026-01-01T00:02:00Z,,102.0000"


def test_chart_index_honours_data_dir_set_after_import(tmp_path, monkeypatch):
    """Path constants resolved at import time ignored ADJACENT_DATA_DIR."""
    module = load_script("chart-index.py")
    monkeypatch.setenv("ADJACENT_DATA_DIR", str(tmp_path))
    assert module.positions_dir() == tmp_path / "positions"


# --- timestamp encodings across the news pipeline -------------------------


def test_parse_timestamp_accepts_iso_and_epoch_encodings():
    parse = load_script("_timeparse.py").parse_timestamp
    expected = datetime(2024, 4, 5, 18, 14, 38, tzinfo=timezone.utc)
    assert parse("2024-04-05T18:14:38Z") == expected
    assert parse("2024-04-05T18:14:38+00:00") == expected
    assert parse(1712340878) == expected          # epoch seconds
    assert parse(1712340878000) == expected       # epoch milliseconds
    assert parse("1712340878") == expected        # epoch as a string
    # Naive input is read as UTC rather than rejected.
    assert parse("2024-04-05T18:14:38").tzinfo is timezone.utc


def test_parse_timestamp_rejects_junk_with_a_readable_message():
    parse = load_script("_timeparse.py").parse_timestamp
    for bad in ("not-a-date", "", True, None):
        try:
            parse(bad)
        except ValueError as exc:
            assert str(exc)
        else:  # pragma: no cover - only runs on regression
            raise AssertionError(f"expected ValueError for {bad!r}")


def test_news_correlation_reads_epoch_timestamps_from_news_latest(tmp_path):
    """news-latest.py --normalize maps a numeric `ts` into published_at,
    so the correlator must accept an epoch, not only ISO 8601."""
    module = load_script("news-correlation.py")
    articles = [{"market_id": "kalshi:A", "published_at": 1712345700, "headline": "h"}]
    prices = [
        {"market_id": "kalshi:A", "ts": 1712345640, "mid": 0.40},
        {"market_id": "kalshi:A", "ts": 1712347200, "mid": 0.52},
    ]
    rows = module.correlate(articles, prices, 30)
    assert len(rows) == 1
    assert rows[0]["move_pct"] == 30.0


def test_news_correlation_skips_zero_mid_instead_of_dividing_by_zero(tmp_path):
    module = load_script("news-correlation.py")
    articles = [{"market_id": "kalshi:Z", "published_at": "2024-04-05T18:15:00Z", "headline": "h"}]
    prices = [
        {"market_id": "kalshi:Z", "ts": "2024-04-05T18:14:00Z", "mid": 0.0},
        {"market_id": "kalshi:Z", "ts": "2024-04-05T18:40:00Z", "mid": 0.03},
    ]
    assert module.correlate(articles, prices, 30) == []


# --- snapshot health grades, never crashes --------------------------------


def test_snapshot_health_grades_unparseable_timestamps_as_error():
    """The script exists to grade feeds fresh/stale/error. A bad `as_of`
    must produce an error row, not a traceback."""
    module = load_script("snapshot-health.py")
    now = datetime(2024, 4, 5, 18, 30, tzinfo=timezone.utc)
    report = module.evaluate(
        [
            {"name": "iso", "as_of": "2024-04-05T18:25:00Z", "max_age_minutes": 30},
            {"name": "epoch", "as_of": 1712341500, "max_age_minutes": 30},
            {"name": "junk", "as_of": "not-a-date", "max_age_minutes": 30},
            {"name": "bad-age", "as_of": "2024-04-05T18:25:00Z", "max_age_minutes": "soon"},
        ],
        now,
    )
    by_name = {row["name"]: row for row in report["snapshots"]}
    assert by_name["iso"]["status"] == "fresh"
    assert by_name["epoch"]["status"] == "fresh"
    assert by_name["junk"]["status"] == "error"
    assert by_name["bad-age"]["status"] == "error"
    assert report["healthy"] is False
    assert report["checked"] == 4


# --- portfolio snapshot tolerates sparse position rows --------------------


def test_portfolio_snapshot_pnl_survives_rows_without_market_id(tmp_path):
    positions = tmp_path / "positions"
    positions.mkdir(parents=True)
    _write(
        positions / "demo.json",
        {"positions": [{"mid": 0.55, "cost_basis": 0.50, "notional": 100}]},
    )
    proc = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "portfolio-snapshot.py"),
            "--index",
            "demo",
            "--include-pnl",
        ],
        capture_output=True,
        text=True,
        env={"PATH": "/usr/bin:/bin", "ADJACENT_DATA_DIR": str(tmp_path)},
    )
    assert proc.returncode == 0, proc.stderr
    assert "unknown" in proc.stdout
    assert "+10.00%" in proc.stdout
