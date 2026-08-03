"""test_tools.py - unit tests for the Adjacent native tool handlers.

Run with no Hermes installation: the handlers are pure-Python functions
that dispatch to allowlisted local scripts. We exercise success, error,
invalid-workflow, and the fail-closed rebalance guard.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import adjacent  # noqa: E402  (put on sys.path by conftest)
from adjacent import tools as T


# --- helpers --------------------------------------------------------------


def _decode(result_str: str) -> dict:
    assert isinstance(result_str, str), "handler must return a JSON string"
    return json.loads(result_str)


def _write_position(root: Path, slug: str) -> None:
    p = root / "positions" / f"{slug}.json"
    p.write_text(
        json.dumps(
            {
                "format_version": 1,
                "index": slug,
                "exchange": "kalshi",
                "positions": [
                    {
                        "market_id": "kalshi:DEMO-A",
                        "size": 10,
                        "side": "yes",
                        "notional": 6.5,
                        "mid": 0.65,
                        "mid_open": 0.60,
                        "cost_basis": 0.60,
                        "current_weight": 1.0,
                        "index": slug,
                        "exchange": "kalshi",
                        "fees": 0.0,
                        "fill_queue_pct": 0.0,
                        "as_of": "2026-07-31T16:00:00-04:00",
                    }
                ],
                "last_fill_ts": "2026-07-31T16:00:00-04:00",
                "as_of": "2026-07-31T16:00:00-04:00",
            }
        ),
        encoding="utf-8",
    )


def _write_tracking(root: Path, slug: str) -> None:
    path = root / "tracking" / f"{slug}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "index": slug,
                "rows": [
                    {
                        "market_id": "kalshi:DEMO-A",
                        "size": 10,
                        "notional": 6.5,
                        "weight_pct": 100.0,
                        "pnl_pct_mid": 8.33,
                        "fill_queue_pct": 0.0,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )


def _write_chart_series(root: Path, slug: str) -> None:
    positions = root / "positions"
    anchor = "2026-07-31T16:00:00-04:00"
    (positions / f"{slug}.last_fill_ts").write_text(anchor, encoding="utf-8")
    for suffix, values in (
        ("index", [0.60, 0.66]),
        ("portfolio", [0.60, 0.63]),
    ):
        (positions / f"{slug}.{suffix}.series.json").write_text(
            json.dumps(
                {
                    "series": [
                        {"ts": anchor, "value": values[0]},
                        {"ts": "2026-07-31T17:00:00-04:00", "value": values[1]},
                    ]
                }
            ),
            encoding="utf-8",
        )


# --- unknown / invalid workflow ------------------------------------------


def test_unknown_workflow():
    res = T.run_workflow("does_not_exist", {})
    assert res["ok"] is False
    assert "unknown workflow" in res["error"]
    assert "does_not_exist" in res["error"]


def test_invalid_missing_required():
    # tracking requires `index`.
    res = _decode(T.adjacent_tracking({}))
    assert res["ok"] is False
    assert "missing required field: index" in res["error"]


def test_invalid_unexpected_field():
    res = _decode(T.adjacent_tracking({"index": "demo", "bogus": 1}))
    assert res["ok"] is False
    assert "unexpected field" in res["error"]


def test_invalid_enum_mcp_query():
    res = _decode(T.adjacent_mcp_query({"tool": "bogus"}))
    assert res["ok"] is False
    assert "tool" in res["error"]


def test_invalid_slug_pattern():
    res = _decode(T.adjacent_tracking({"index": "bad slug!"}))
    assert res["ok"] is False
    assert "index" in res["error"]


# --- success path --------------------------------------------------------


def test_portfolio_snapshot_success(tmp_data_root):
    _write_position(tmp_data_root, "demo")
    res = _decode(T.adjacent_portfolio_snapshot({"index": "demo", "as_json": True}))
    assert res["ok"] is True, res
    assert res["returncode"] == 0
    assert "demo" in res["stdout"]


def test_tracking_success(tmp_data_root):
    _write_position(tmp_data_root, "demo")
    res = _decode(T.adjacent_tracking({"index": "demo", "as_json": True}))
    assert res["ok"] is True, res
    payload = json.loads(res["stdout"])
    assert payload["index"] == "demo"
    assert payload["rows"][0]["market_id"] == "kalshi:DEMO-A"


def test_tracking_table_success(tmp_data_root):
    _write_tracking(tmp_data_root, "demo")
    res = _decode(T.adjacent_tracking_table({"index": "demo"}))
    assert res["ok"] is True, res
    assert "market_id,size,notional" in res["stdout"]
    assert "kalshi:DEMO-A" in res["stdout"]


def test_datawrapper_no_publish_returns_csv_without_key(tmp_data_root, monkeypatch):
    _write_chart_series(tmp_data_root, "demo")
    monkeypatch.delenv("DATAWRAPPER_API_KEY", raising=False)
    res = _decode(
        T.adjacent_datawrapper_index(
            {"index": "demo", "chart_id": "unused", "no_publish": True}
        )
    )
    assert res["ok"] is True, res
    assert res["stdout"].startswith("ts,index,portfolio")


def test_capability_status_marks_news_live_and_correlation_unavailable():
    res = _decode(T.adjacent_capability_status({}))
    assert res["ok"] is True, res
    payload = json.loads(res["stdout"])
    assert payload["capabilities"]["news_latest"]["api_status"] == "live"
    assert (
        payload["capabilities"]["index_correlation"]["api_status"]
        == "unavailable"
    )


def test_news_correlation_requires_supplied_files():
    res = _decode(T.adjacent_news_correlation({}))
    assert res["ok"] is False
    assert "missing required field: news" in res["error"]
    assert "missing required field: prices" in res["error"]


def test_correlation_regime_requires_supplied_file():
    res = _decode(T.adjacent_correlation_regime({}))
    assert res["ok"] is False
    assert "missing required field: input" in res["error"]


# --- script error path ---------------------------------------------------


def test_tracking_missing_position_file(tmp_data_root):
    # No position file written for this slug.
    res = _decode(T.adjacent_tracking({"index": "missing-slug", "as_json": True}))
    assert res["ok"] is False
    assert res["returncode"] != 0
    # A script-level error is reported via returncode + stderr, not the
    # handler `error` field (that field is for handler-side failures).
    assert res["stderr"] != ""


def test_handler_catches_subprocess_exception(monkeypatch):
    def _boom(*a, **kw):
        raise FileNotFoundError("simulated missing interpreter")

    monkeypatch.setattr(T.subprocess, "run", _boom)
    res = _decode(T.adjacent_portfolio_snapshot({}))
    # No data dir -> the handler still returns JSON (it never raises).
    assert res["ok"] is False


# --- fail-closed rebalance guard -----------------------------------------


def test_rebalance_plan_argv_always_non_placing():
    argv = T._rebalance_plan_argv({"index": "demo", "plan": "/tmp/plan.json"})
    assert "--dry-run" in argv
    assert "--json" not in argv
    assert argv[argv.index("--plan") + 1] == "/tmp/plan.json"


def test_rebalance_plan_never_places(monkeypatch):
    captured: dict = {}

    def _fake_run(cmd, **kw):
        captured["cmd"] = cmd
        return subprocess.CompletedProcess(cmd, 0, stdout='{"index":"demo"}', stderr="")

    monkeypatch.setattr(T.subprocess, "run", _fake_run)
    res = _decode(
        T.adjacent_rebalance_plan(
            {"index": "demo", "plan": "/tmp/plan.json"}
        )
    )
    assert res["ok"] is True
    cmd = captured["cmd"]
    # The script path must be the allowlisted rebalance script.
    assert cmd[1].endswith("rebalance-index.py")
    # Fail-closed: one of the non-placing flags must be present and the
    # placing path (no --json and no --dry-run) must never happen.
    assert "--json" in cmd or "--dry-run" in cmd


def test_rebalance_plan_invalid_no_index():
    res = _decode(T.adjacent_rebalance_plan({}))
    assert res["ok"] is False
    assert "index" in res["error"]


def test_rebalance_plan_requires_plan():
    res = _decode(T.adjacent_rebalance_plan({"index": "demo"}))
    assert res["ok"] is False
    assert "plan" in res["error"]


# --- allowlist boundary --------------------------------------------------


def test_allowlist_excludes_order_scripts():
    # No handler may dispatch to a script outside ALLOWED_SCRIPTS.
    allowed_paths = set(T.ALLOWED_SCRIPTS.values())
    # The raw order-placing path is the rebalance script, but it is only
    # ever invoked with non-placing flags (tested above).
    assert any(p.endswith("rebalance-index.py") for p in allowed_paths)
    # There is no generic "run arbitrary command" entry.
    for workflow, (_schema_key, builder) in T.ALLOWED_WORKFLOWS.items():
        argv = builder(
            {
                "index": "demo",
                "tool": "list",
                "chart_id": "x",
                "plan": "plan.json",
                "news": "news.json",
                "prices": "prices.json",
                "input": "correlations.json",
            }
        )
        assert argv[0] in allowed_paths


def test_every_handler_returns_json_string(monkeypatch):
    # Fake subprocess so handlers with no required args (e.g. news_latest)
    # never touch the network or filesystem during this contract test.
    def _fake_run(cmd, **kw):
        return subprocess.CompletedProcess(cmd, 0, stdout="{}", stderr="")

    monkeypatch.setattr(T.subprocess, "run", _fake_run)
    for name, handler in T.TOOL_HANDLERS.items():
        out = handler({})
        assert isinstance(out, str), f"{name} did not return a string"
        json.loads(out)  # must parse


def test_tool_schemas_match_handlers():
    assert set(T.TOOL_HANDLERS) == set(T.schemas.TOOL_SCHEMAS)

def test_mcp_query_price_argv_includes_type():
    argv = T._mcp_query_argv(
        {
            "tool": "price",
            "id": "red",
            "type": "index",
            "timeframe": "7d",
        }
    )
    assert argv[1] == "price"
    assert "red" in argv
    assert "7d" in argv
    assert "--type" in argv
    assert "index" in argv


def test_mcp_query_get_requires_type():
    try:
        T._mcp_query_argv({"tool": "get", "id": "red"})
    except T.WorkflowError as exc:
        assert "type" in str(exc)
    else:
        raise AssertionError("expected WorkflowError")


def test_mcp_query_find_accepts_query():
    argv = T._mcp_query_argv({"tool": "find", "query": "republican", "type": "index"})
    assert argv[1] == "find"
    assert "republican" in argv
    assert "--type" in argv

