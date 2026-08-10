from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from tests._hookutil import ROOT, load_script


def test_capability_status_reflects_live_news_and_offline_correlation():
    payload = json.loads(
        (
            ROOT / "data" / "capabilities.json"
        ).read_text(encoding="utf-8")
    )
    capabilities = payload["capabilities"]
    assert capabilities["news_latest"]["api_status"] == "live"
    assert capabilities["news_latest"]["plugin_status"] == "guided"
    assert capabilities["index_correlation"]["api_status"] == "unavailable"
    assert "rates_oracles" not in capabilities


def test_capability_status_json_carries_onboarding_intro():
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "capability-status.py"), "--json"],
        capture_output=True,
        text=True,
        check=True,
    )
    payload = json.loads(result.stdout)
    assert "intro_text" in payload
    intro = payload["intro_text"]
    assert "Adjacent is live." in intro
    # Each scheduled workflow renders as an ASCII bullet the agent can relay.
    assert "- Daily morning brief" in intro
    assert "- Mover alerts" in intro
    # Writing conventions: no percentage-points, no em-dash.
    assert "pp" not in intro
    assert "\u2014" not in intro


def test_capability_status_intro_flag_prints_only_intro():
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "capability-status.py"), "--intro"],
        capture_output=True,
        text=True,
        check=True,
    )
    assert result.stdout.startswith("Adjacent is live.")
    # The intro-only path must not leak the capability status lines.
    assert "api_status" not in result.stdout
    assert "news_latest:" not in result.stdout


def test_capability_status_json_includes_runtime_probe():
    """The --json payload must carry a runtime probe with matplotlib and
    datawrapper_key booleans, alongside the existing capabilities map and
    intro_text."""
    import importlib.util

    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "capability-status.py"), "--json"],
        capture_output=True,
        text=True,
        check=True,
    )
    payload = json.loads(result.stdout)
    assert "capabilities" in payload, "existing capabilities map must remain"
    assert "intro_text" in payload, "intro_text must remain"
    runtime = payload["runtime"]
    assert isinstance(runtime, dict)
    assert "matplotlib" in runtime
    assert isinstance(runtime["matplotlib"], bool)
    # The probe must reflect the actual importability of matplotlib.
    assert runtime["matplotlib"] is (
        importlib.util.find_spec("matplotlib") is not None
    )
    assert "datawrapper_key" in runtime
    assert isinstance(runtime["datawrapper_key"], bool)


def test_capability_status_text_mode_prints_charting_line():
    """The human text output must include a charting line after the
    capability list, while the intro still leads."""
    import importlib.util

    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "capability-status.py")],
        capture_output=True,
        text=True,
        check=True,
    )
    assert result.stdout.startswith("Adjacent is live.")
    assert "charting:" in result.stdout
    has_mpl = importlib.util.find_spec("matplotlib") is not None
    if has_mpl:
        assert "matplotlib available" in result.stdout
    else:
        assert "matplotlib missing" in result.stdout
        assert "requirements.txt" in result.stdout


def test_shared_data_dir_defaults_to_repository_root(monkeypatch):
    monkeypatch.delenv("ADJACENT_DATA_DIR", raising=False)
    monkeypatch.delenv("ADJACENT_PLUGIN_ROOT", raising=False)
    module = load_script("_paths.py")
    assert module.data_dir() == ROOT / "data"
    assert module.scripts_dir() == ROOT / "scripts"


def test_paths_respect_plugin_root_and_scripts_overrides(monkeypatch, tmp_path):
    module = load_script("_paths.py")
    root = tmp_path / "install"
    scripts = root / "scripts"
    data = root / "data"
    scripts.mkdir(parents=True)
    data.mkdir()
    monkeypatch.setenv("ADJACENT_PLUGIN_ROOT", str(root))
    monkeypatch.delenv("ADJACENT_DATA_DIR", raising=False)
    monkeypatch.delenv("ADJACENT_PLUGIN_SCRIPTS", raising=False)
    assert module.plugin_root() == root.resolve()
    assert module.scripts_dir() == scripts.resolve()
    assert module.data_dir() == data.resolve()
    other = tmp_path / "other-scripts"
    other.mkdir()
    monkeypatch.setenv("ADJACENT_PLUGIN_SCRIPTS", str(other))
    assert module.scripts_dir() == other.resolve()


def test_mcp_call_handshakes_and_parses_sse(monkeypatch):
    module = load_script("_mcp.py")
    requested: list[dict] = []

    class Response:
        def __init__(self, status, body, headers):
            self.status = status
            self._body = body
            self._headers = headers

        def read(self):
            return self._body

        def getheaders(self):
            return list(self._headers.items())

    class Connection:
        def __init__(self):
            self._step = 0

        def request(self, method, path, body, headers):
            requested.append(
                {
                    "method": method,
                    "path": path,
                    "body": json.loads(body.decode("utf-8")),
                    "headers": headers,
                }
            )

        def getresponse(self):
            step = self._step
            self._step += 1
            if step == 0:
                # initialize
                return Response(
                    200,
                    b'data: {"jsonrpc":"2.0","id":1,"result":{"protocolVersion":"2024-11-05"}}\n\n',
                    {"mcp-session-id": "sess-1", "content-type": "text/event-stream"},
                )
            if step == 1:
                # notifications/initialized
                return Response(202, b"", {})
            return Response(
                200,
                b'data: {"jsonrpc":"2.0","id":2,"result":{"content":[{"type":"text","text":"{}"}]}}\n\n',
                {"content-type": "text/event-stream"},
            )

        def close(self):
            return None

    monkeypatch.setattr(
        module.http.client,
        "HTTPSConnection",
        lambda *args, **kwargs: Connection(),
    )
    result = module.call("example.com", None, "/custom", "find", {"query": "demo"})
    assert "result" in result
    assert requested[0]["body"]["method"] == "initialize"
    assert requested[0]["headers"]["Accept"] == module.ACCEPT
    assert requested[1]["body"]["method"] == "notifications/initialized"
    assert requested[1]["headers"]["Mcp-Session-Id"] == "sess-1"
    assert requested[2]["body"]["method"] == "tools/call"
    assert requested[2]["path"] == "/custom"


def test_mcp_call_retries_on_5xx_then_succeeds(monkeypatch):
    """A transient HTTP 503 on the first attempt should be retried and
    eventually succeed when the second attempt returns 200."""
    module = load_script("_mcp.py")
    sleeps: list[float] = []
    monkeypatch.setattr(module.time, "sleep", lambda s: sleeps.append(s))
    # Each _call_once creates a new connection, so track attempts across
    # instances with a closure-scoped counter.
    attempt_count = [0]

    class Response:
        def __init__(self, status, body, headers):
            self.status = status
            self._body = body
            self._headers = headers

        def read(self):
            return self._body

        def getheaders(self):
            return list(self._headers.items())

    class RetryConnection:
        def __init__(self):
            self._step = 0

        def request(self, method, path, body, headers):
            pass

        def getresponse(self):
            step = self._step
            self._step += 1
            if attempt_count[0] == 0 and step == 0:
                # First attempt: initialize returns 503.
                attempt_count[0] += 1
                self._step = 0
                return Response(503, b"service unavailable", {})
            # Second attempt: full success.
            if step == 0:
                return Response(
                    200,
                    b'data: {"jsonrpc":"2.0","id":1,"result":{"protocolVersion":"2024-11-05"}}\n\n',
                    {"mcp-session-id": "sess-2", "content-type": "text/event-stream"},
                )
            if step == 1:
                return Response(202, b"", {})
            return Response(
                200,
                b'data: {"jsonrpc":"2.0","id":2,"result":{"content":[{"type":"text","text":"{}"}]}}\n\n',
                {"content-type": "text/event-stream"},
            )

        def close(self):
            return None

    monkeypatch.setattr(
        module.http.client,
        "HTTPSConnection",
        lambda *args, **kwargs: RetryConnection(),
    )
    result = module.call("example.com", None, "/mcp", "find", {"query": "demo"})
    assert "result" in result
    assert len(sleeps) == 1  # one backoff sleep before the retry


def test_mcp_call_does_not_retry_on_4xx(monkeypatch):
    """HTTP 400 is a client error, not transient; no retry."""
    module = load_script("_mcp.py")
    sleeps: list[float] = []
    monkeypatch.setattr(module.time, "sleep", lambda s: sleeps.append(s))

    class Response:
        def __init__(self, status, body, headers):
            self.status = status
            self._body = body
            self._headers = headers

        def read(self):
            return self._body

        def getheaders(self):
            return list(self._headers.items())

    class BadRequestConnection:
        def __init__(self):
            self._step = 0

        def request(self, method, path, body, headers):
            pass

        def getresponse(self):
            step = self._step
            self._step += 1
            if step == 0:
                return Response(400, b"bad request", {})
            return Response(202, b"", {})

        def close(self):
            return None

    monkeypatch.setattr(
        module.http.client,
        "HTTPSConnection",
        lambda *args, **kwargs: BadRequestConnection(),
    )
    result = module.call("example.com", None, "/mcp", "find", {"query": "demo"})
    assert "error" in result
    assert result["error"]["code"] == 400
    assert len(sleeps) == 0  # no retry on 4xx


def test_mcp_call_retries_on_network_exception(monkeypatch):
    """A network exception (no HTTP code) is retryable."""
    module = load_script("_mcp.py")
    sleeps: list[float] = []
    monkeypatch.setattr(module.time, "sleep", lambda s: sleeps.append(s))
    attempts = [0]

    class FlakyConnection:
        def __init__(self):
            self._step = 0

        def request(self, method, path, body, headers):
            attempts[0] += 1
            if attempts[0] == 1:
                raise ConnectionRefusedError("connection refused")

        def getresponse(self):
            step = self._step
            self._step += 1
            if step == 0:
                return Response(
                    200,
                    b'data: {"jsonrpc":"2.0","id":1,"result":{"protocolVersion":"2024-11-05"}}\n\n',
                    {"mcp-session-id": "sess-3", "content-type": "text/event-stream"},
                )
            if step == 1:
                return Response(202, b"", {})
            return Response(
                200,
                b'data: {"jsonrpc":"2.0","id":2,"result":{"content":[{"type":"text","text":"{}"}]}}\n\n',
                {"content-type": "text/event-stream"},
            )

        def close(self):
            return None

    class Response:
        def __init__(self, status, body, headers):
            self.status = status
            self._body = body
            self._headers = headers

        def read(self):
            return self._body

        def getheaders(self):
            return list(self._headers.items())

    monkeypatch.setattr(
        module.http.client,
        "HTTPSConnection",
        lambda *args, **kwargs: FlakyConnection(),
    )
    result = module.call("example.com", None, "/mcp", "find", {"query": "demo"})
    assert "result" in result
    assert len(sleeps) == 1


def test_rebalance_plan_index_must_match_argument(tmp_path):
    plan = tmp_path / "plan.json"
    plan.write_text(
        json.dumps({"index": "other", "sells": [], "buys": []}),
        encoding="utf-8",
    )
    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "rebalance-index.py"),
            "--index",
            "expected",
            "--plan",
            str(plan),
            "--dry-run",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode != 0
    assert "does not match" in result.stderr


def test_datawrapper_csv_reader_uses_explicit_file(tmp_path):
    module = load_script("_datawrapper.py")
    source = tmp_path / "data.csv"
    source.write_bytes(b"name,value\nA,1\n")
    assert module.read_csv(str(source)) == b"name,value\nA,1\n"


def test_news_correlation_uses_minute_aligned_mid_moves():
    module = load_script("news-correlation.py")
    results = module.correlate(
        [
            {
                "market_id": "kalshi:demo",
                "published_at": "2026-08-01T12:00:20+00:00",
                "headline": "Demo headline",
            }
        ],
        [
            {
                "market_id": "kalshi:demo",
                "ts": "2026-08-01T12:00:00+00:00",
                "mid": 0.50,
            },
            {
                "market_id": "kalshi:demo",
                "ts": "2026-08-01T12:30:00+00:00",
                "mid": 0.55,
            },
        ],
        30,
    )
    assert results[0]["move_pct"] == 10.0


def test_correlation_regime_flags_two_sigma_shift():
    module = load_script("correlation-regime.py")
    rows = [
        {
            "ts": f"2026-07-{day:02d}",
            "index": "demo",
            "benchmark": "spx",
            "correlation": value,
        }
        for day, value in enumerate([0.10, 0.12, 0.11, 0.50], start=1)
    ]
    results = module.find_regime_shifts(rows, 2.0)
    assert results[0]["index"] == "demo"
    assert results[0]["z_score"] > 2.0


def test_news_latest_normalizes_aliased_fields():
    module = load_script("news-latest.py")
    response = {
        "result": {
            "content": [
                {
                    "text": json.dumps(
                        {
                            "news": [
                                {
                                    "marketId": "kalshi:DEMO",
                                    "publishedAt": "2026-08-01T12:00:00+00:00",
                                    "title": "Live headline",
                                },
                                {"title": "no market id"},
                            ]
                        }
                    )
                }
            ]
        }
    }
    articles = module.normalize_articles(response)
    assert articles == [
        {
            "market_id": "kalshi:DEMO",
            "published_at": "2026-08-01T12:00:00+00:00",
            "headline": "Live headline",
        }
    ]


def test_candles_chart_uses_mid_based_close():
    module = load_script("candles-chart.py")
    candles = [
        {"ts": "2026-08-01T00:01:00+00:00", "bid": 0.40, "ask": 0.60},
        {"ts": "2026-08-01T00:00:00+00:00", "mid": 0.50},
        {"ts": "2026-08-01T00:02:00+00:00"},
        {
            "end_period_ts": "2026-08-01T00:03:00+00:00",
            "yes_bid_dollars": 0.30,
            "yes_ask_dollars": 0.50,
        },
    ]
    series = module.to_series(candles)
    # Sorted by ts; the row with no price is dropped.
    assert series == [
        ("2026-08-01T00:00:00+00:00", 0.50),
        ("2026-08-01T00:01:00+00:00", 0.50),
        ("2026-08-01T00:03:00+00:00", 0.40),
    ]
    rebased = module.rebase(series)
    assert rebased[0][1] == 100.0


def test_heikin_ashi_transform_matches_house_formulas():
    module = load_script("adjacent_chart_style.py")
    ha = module.heikin_ashi_transform(
        opens=[10, 11],
        highs=[12, 13],
        lows=[9, 10],
        closes=[11, 12],
    )
    # First HA-open = (O+C)/2 = 10.5; HA-close = (10+12+9+11)/4 = 10.5
    assert ha[0] == (10.5, 12.0, 9.0, 10.5)
    # Second HA-open = (10.5+10.5)/2 = 10.5; HA-close = (11+13+10+12)/4 = 11.5
    assert ha[1][0] == 10.5
    assert ha[1][3] == 11.5


def test_similar_hedges_splits_hedges_and_proxies():
    module = load_script("similar-hedges.py")
    rows = [
        {"market_id": "a", "correlation": -0.8},
        {"market_id": "b", "correlation": 0.7},
        {"market_id": "c", "correlation": 0.1},
        {"market_id": "d", "correlation": -0.4},
    ]
    result = module.classify(rows, 0.3)
    assert [row["market_id"] for row in result["hedges"]] == ["a", "d"]
    assert [row["market_id"] for row in result["proxies"]] == ["b"]


def test_snapshot_health_grades_freshness():
    module = load_script("snapshot-health.py")
    now = module.datetime(2026, 8, 1, 12, 0, tzinfo=module.timezone.utc)
    snapshots = [
        {"name": "fresh", "as_of": "2026-08-01T11:45:00+00:00", "max_age_minutes": 30},
        {"name": "stale", "as_of": "2026-08-01T10:00:00+00:00", "max_age_minutes": 30},
        {"name": "broken", "error": "HTTP 500"},
    ]
    report = module.evaluate(snapshots, now)
    assert report["healthy"] is False
    statuses = {row["name"]: row["status"] for row in report["snapshots"]}
    assert statuses == {"fresh": "fresh", "stale": "stale", "broken": "error"}


def test_snapshot_health_live_uses_http_date_when_body_has_no_as_of(monkeypatch):
    module = load_script("snapshot-health.py")

    def fake_get(url, api_key=None, timeout=20):
        body = json.dumps([{"index_id": "red", "latest_price": 96.3}]).encode("utf-8")
        headers = {"date": "Sat, 01 Aug 2026 11:50:00 GMT"}
        return 200, body, headers

    monkeypatch.setattr(module, "get_with_headers", fake_get)
    resolved = module._fetch_live(
        [{"name": "indices", "url": "https://api.adjacent.markets/api/v1/public/indices"}],
        None,
    )
    assert "as_of" in resolved[0]
    assert resolved[0]["as_of"].startswith("2026-08-01T11:50:00")

def test_http_get_rejects_non_adjacent_host():
    module = load_script("_http.py")
    try:
        module._check_host("https://evil.example.com/export/x.csv")
    except ValueError:
        pass
    else:
        raise AssertionError("expected ValueError for disallowed host")
    assert module._check_host("https://mcp.adjacent.markets/docs.zip") == "mcp.adjacent.markets"
