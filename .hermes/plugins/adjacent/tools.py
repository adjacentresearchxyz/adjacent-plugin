"""tools.py - native tool handlers for the Adjacent Hermes plugin.

Each handler follows the documented Hermes tool-handler contract:

    def handler(args: dict, **kwargs) -> str

- `args` is the dict of parameters the LLM passed,
- `**kwargs` accepts any extra context the host may pass in the future,
- the handler validates `args` against the `parameters` schema in
  schemas.py,
- it dispatches ONLY to an entry in ALLOWED_WORKFLOWS (an explicit
  allowlist of existing local Python scripts and the exact argv shape),
- it catches every exception and returns a JSON string (never raises),
- it returns a JSON string of the form:
    {"ok": true|false, "workflow": <name>, "returncode": <int>,
     "stdout": "...", "stderr": "...", "error": "..."?}

The allowlist is the security boundary. No handler may shell out to an
arbitrary command; every argv is built from a fixed script path plus
validated, enumerated flags. The rebalance workflow is fail-closed: it
always passes --dry-run or --json so no exchange order is ever placed
through this plugin.

Conventions: ASCII only, no em-dash, no unicode bullet, `%` never `pp`.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

from . import schemas

_PLUGIN_DIR = Path(__file__).resolve().parent


def _resolve_scripts_dir() -> Path:
    """Locate the shared scripts directory across install layouts.

    Resolved on each call so ``ADJACENT_PLUGIN_SCRIPTS`` /
    ``ADJACENT_PLUGIN_ROOT`` take effect even after import. Order:

    1. ``ADJACENT_PLUGIN_SCRIPTS`` explicit override.
    2. ``ADJACENT_PLUGIN_ROOT/scripts`` when the whole package is installed.
    3. Repo layout: ``.hermes/plugins/adjacent`` -> plugin root ``scripts/``.
    """
    override = os.environ.get("ADJACENT_PLUGIN_SCRIPTS")
    if override:
        return Path(override).expanduser().resolve()
    root = os.environ.get("ADJACENT_PLUGIN_ROOT")
    if root:
        return Path(root).expanduser().resolve() / "scripts"
    # In-repo: adjacent-plugin/.hermes/plugins/adjacent -> adjacent-plugin/scripts
    return _PLUGIN_DIR.parents[2] / "scripts"


def _script(name: str) -> str:
    return str(_resolve_scripts_dir() / name)


class _ScriptAllowlist(dict):
    """Map script basename -> absolute path, resolved lazily from env."""

    def __init__(self, names: list[str]) -> None:
        super().__init__()
        self._names = list(names)

    def __getitem__(self, name: str) -> str:  # type: ignore[override]
        if name not in self._names:
            raise KeyError(name)
        return _script(name)

    def __contains__(self, name: object) -> bool:  # type: ignore[override]
        return isinstance(name, str) and name in self._names

    def keys(self):  # type: ignore[override]
        return list(self._names)

    def values(self):  # type: ignore[override]
        return [_script(name) for name in self._names]

    def items(self):  # type: ignore[override]
        return [(name, _script(name)) for name in self._names]

    def __iter__(self):  # type: ignore[override]
        return iter(self._names)


# The explicit allowlist. Each entry is a frozen argv template plus the
# handler that turns validated kwargs into the remaining argv. A
# workflow NOT in this dict can never be invoked. Scripts that place
# exchange orders are excluded entirely; the rebalance workflow below
# forces non-placing flags.
ALLOWED_SCRIPTS: _ScriptAllowlist = _ScriptAllowlist(
    [
        "portfolio-snapshot.py",
        "tracking-index.py",
        "chart-index.py",
        "mcp-cli.py",
        "table-tracking.py",
        "rebalance-index.py",
        "datawrapper-index.py",
        "capability-status.py",
        "news-correlation.py",
        "correlation-regime.py",
        "news-latest.py",
        "topic-brief.py",
        "candles-chart.py",
        "similar-hedges.py",
        "snapshot-health.py",
        "http-get.py",
    ]
)


class WorkflowError(ValueError):
    """Raised for unknown workflows or invalid arguments."""


# --- argv builders --------------------------------------------------------


def _portfolio_snapshot_argv(params: dict[str, Any]) -> list[str]:
    argv: list[str] = [ALLOWED_SCRIPTS["portfolio-snapshot.py"]]
    if params.get("as_json"):
        argv.append("--json")
    if params.get("index"):
        argv += ["--index", str(params["index"])]
    if params.get("include_pnl"):
        argv.append("--include-pnl")
    return argv


def _tracking_argv(params: dict[str, Any]) -> list[str]:
    argv: list[str] = [ALLOWED_SCRIPTS["tracking-index.py"], "--index", str(params["index"])]
    if params.get("as_json"):
        argv.append("--json")
    return argv


def _chart_csv_argv(params: dict[str, Any]) -> list[str]:
    argv: list[str] = [ALLOWED_SCRIPTS["chart-index.py"], "--index", str(params["index"])]
    if params.get("output"):
        argv += ["--output", str(params["output"])]
    return argv


def _mcp_query_argv(params: dict[str, Any]) -> list[str]:
    tool = params["tool"]
    argv: list[str] = [ALLOWED_SCRIPTS["mcp-cli.py"], tool]
    if tool == "list":
        argv += ["--type", str(params.get("type", "event"))]
    elif tool == "find":
        query = params.get("query") or params.get("topic")
        if not query:
            raise WorkflowError("mcp_query `find` requires `query`")
        argv.append(str(query))
        if params.get("type"):
            argv += ["--type", str(params["type"])]
    elif tool == "get":
        ident = params.get("id")
        entity_type = params.get("type")
        if not ident or not entity_type:
            raise WorkflowError("mcp_query `get` requires `id` and `type`")
        argv += [str(ident), "--type", str(entity_type)]
    elif tool == "price":
        # Prefer id; accept slug as a legacy alias for index/rate identifiers.
        ident = params.get("id") or params.get("slug")
        entity_type = params.get("type")
        timeframe = params.get("timeframe")
        if not ident or not entity_type or not timeframe:
            raise WorkflowError(
                "mcp_query `price` requires `id` (or `slug`), `type`, and `timeframe`"
            )
        argv += [str(ident), str(timeframe), "--type", str(entity_type)]
        if params.get("raw"):
            argv.append("--raw")
        if params.get("fallback_venue"):
            argv += ["--fallback-venue", str(params["fallback_venue"])]
        if params.get("side"):
            argv += ["--side", str(params["side"])]
    return argv


def _tracking_table_argv(params: dict[str, Any]) -> list[str]:
    argv: list[str] = [ALLOWED_SCRIPTS["table-tracking.py"], "--index", str(params["index"])]
    if params.get("output"):
        argv += ["--output", str(params["output"])]
    return argv


def _rebalance_plan_argv(params: dict[str, Any]) -> list[str]:
    return [
        ALLOWED_SCRIPTS["rebalance-index.py"],
        "--index",
        str(params["index"]),
        "--exchange",
        str(params.get("exchange", "kalshi")),
        "--plan",
        str(params["plan"]),
        "--dry-run",
    ]


def _datawrapper_index_argv(params: dict[str, Any]) -> list[str]:
    argv: list[str] = [
        ALLOWED_SCRIPTS["datawrapper-index.py"],
        "--index",
        str(params["index"]),
        "--chart-id",
        str(params["chart_id"]),
    ]
    # Default to no_publish=True so the safe path is CSV-only. Only when
    # the caller explicitly sets no_publish=False do we attempt a publish.
    if params.get("no_publish", True):
        argv.append("--no-publish")
    return argv


def _capability_status_argv(params: dict[str, Any]) -> list[str]:
    return [ALLOWED_SCRIPTS["capability-status.py"], "--json"]


def _news_correlation_argv(params: dict[str, Any]) -> list[str]:
    return [
        ALLOWED_SCRIPTS["news-correlation.py"],
        "--news",
        str(params["news"]),
        "--prices",
        str(params["prices"]),
        "--window-minutes",
        str(params.get("window_minutes", 30)),
    ]


def _correlation_regime_argv(params: dict[str, Any]) -> list[str]:
    return [
        ALLOWED_SCRIPTS["correlation-regime.py"],
        "--input",
        str(params["input"]),
        "--sigma",
        str(params.get("sigma", 2.0)),
    ]


def _news_latest_argv(params: dict[str, Any]) -> list[str]:
    argv: list[str] = [ALLOWED_SCRIPTS["news-latest.py"]]
    if params.get("normalize"):
        argv.append("--normalize")
    return argv


def _topic_brief_argv(params: dict[str, Any]) -> list[str]:
    argv: list[str] = [ALLOWED_SCRIPTS["topic-brief.py"], str(params["topic"])]
    if "news_limit" in params:
        argv += ["--news-limit", str(params["news_limit"])]
    if "market_limit" in params:
        argv += ["--market-limit", str(params["market_limit"])]
    if params.get("timeframe"):
        argv += ["--timeframe", str(params["timeframe"])]
    if params.get("chart"):
        argv.append("--chart")
    if params.get("png"):
        argv.append("--png")
    if params.get("prod"):
        argv.append("--prod")
    if params.get("output_dir"):
        argv += ["--output-dir", str(params["output_dir"])]
    return argv


def _candles_chart_argv(params: dict[str, Any]) -> list[str]:
    argv: list[str] = [ALLOWED_SCRIPTS["candles-chart.py"]]
    if params.get("input"):
        argv += ["--input", str(params["input"])]
    if params.get("output"):
        argv += ["--output", str(params["output"])]
    if params.get("rebase"):
        argv.append("--rebase")
    return argv


def _similar_hedges_argv(params: dict[str, Any]) -> list[str]:
    argv: list[str] = [ALLOWED_SCRIPTS["similar-hedges.py"]]
    if params.get("input"):
        argv += ["--input", str(params["input"])]
    if "min_abs_correlation" in params:
        argv += ["--min-abs-correlation", str(params["min_abs_correlation"])]
    return argv


def _snapshot_health_argv(params: dict[str, Any]) -> list[str]:
    argv: list[str] = [ALLOWED_SCRIPTS["snapshot-health.py"]]
    if params.get("input"):
        argv += ["--input", str(params["input"])]
    if params.get("live"):
        argv.append("--live")
    return argv


def _http_get_argv(params: dict[str, Any]) -> list[str]:
    argv: list[str] = [ALLOWED_SCRIPTS["http-get.py"]]
    if params.get("url"):
        argv += ["--url", str(params["url"])]
    if params.get("output"):
        argv += ["--output", str(params["output"])]
    return argv


# workflow name -> (schema key, argv builder)
ALLOWED_WORKFLOWS: dict[str, tuple[str, Any]] = {
    "portfolio_snapshot": ("adjacent_portfolio_snapshot", _portfolio_snapshot_argv),
    "tracking": ("adjacent_tracking", _tracking_argv),
    "chart_csv": ("adjacent_chart_csv", _chart_csv_argv),
    "mcp_query": ("adjacent_mcp_query", _mcp_query_argv),
    "tracking_table": ("adjacent_tracking_table", _tracking_table_argv),
    "rebalance_plan": ("adjacent_rebalance_plan", _rebalance_plan_argv),
    "datawrapper_index": ("adjacent_datawrapper_index", _datawrapper_index_argv),
    "capability_status": ("adjacent_capability_status", _capability_status_argv),
    "news_correlation": ("adjacent_news_correlation", _news_correlation_argv),
    "correlation_regime": ("adjacent_correlation_regime", _correlation_regime_argv),
    "news_latest": ("adjacent_news_latest", _news_latest_argv),
    "topic_brief": ("adjacent_topic_brief", _topic_brief_argv),
    "candles_chart": ("adjacent_candles_chart", _candles_chart_argv),
    "similar_hedges": ("adjacent_similar_hedges", _similar_hedges_argv),
    "snapshot_health": ("adjacent_snapshot_health", _snapshot_health_argv),
    "http_get": ("adjacent_http_get", _http_get_argv),
}


# --- validation -----------------------------------------------------------


def _validate(schema: dict, params: dict[str, Any]) -> list[str]:
    """Minimal JSON-Schema-ish validation. Returns a list of error
    strings (empty == valid). Deliberately dependency-free so tests run
    without a Hermes install or jsonschema package."""
    errors: list[str] = []
    if schema.get("type") != "object":
        return errors
    props = schema.get("properties", {}) or {}
    for req in schema.get("required", []) or []:
        if req not in params or params[req] in (None, ""):
            errors.append(f"missing required field: {req}")
    if not schema.get("additionalProperties", False):
        for key in params:
            if key not in props:
                errors.append(f"unexpected field: {key}")
    for key, val in params.items():
        spec = props.get(key)
        if spec is None or val is None:
            continue
        t = spec.get("type")
        ok = True
        if t == "string":
            ok = isinstance(val, str)
            if ok and "minLength" in spec and len(val) < spec["minLength"]:
                errors.append(f"{key}: shorter than minLength {spec['minLength']}")
            if ok and "maxLength" in spec and len(val) > spec["maxLength"]:
                errors.append(f"{key}: longer than maxLength {spec['maxLength']}")
            if ok and "pattern" in spec:
                import re

                if not re.match(spec["pattern"], val):
                    errors.append(f"{key}: does not match pattern {spec['pattern']}")
        elif t == "boolean":
            ok = isinstance(val, bool)
        elif t == "integer":
            ok = isinstance(val, int) and not isinstance(val, bool)
        elif t == "number":
            ok = isinstance(val, (int, float)) and not isinstance(val, bool)
        if not ok:
            errors.append(f"{key}: expected {t}, got {type(val).__name__}")
        if ok and "minimum" in spec and val < spec["minimum"]:
            errors.append(f"{key}: less than minimum {spec['minimum']}")
        if t == "string" and ok and "enum" in spec and val not in spec["enum"]:
            errors.append(f"{key}: {val!r} not in enum {spec['enum']}")
    return errors


# --- core runner ----------------------------------------------------------


def run_workflow(workflow: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    """Run an allowlisted workflow and return a result dict. Never
    raises; errors are reported in the `error` field with ok=False."""
    params = params or {}
    if workflow not in ALLOWED_WORKFLOWS:
        return {
            "ok": False,
            "workflow": workflow,
            "error": f"unknown workflow: {workflow!r}; allowed: {sorted(ALLOWED_WORKFLOWS)}",
        }
    schema_key, builder = ALLOWED_WORKFLOWS[workflow]
    schema = schemas.TOOL_SCHEMAS[schema_key]
    # The documented Hermes schema shape is {name, description, parameters};
    # validate against the JSON-Schema `parameters` sub-object.
    parameters = schema.get("parameters", schema)
    errors = _validate(parameters, params)
    if errors:
        return {
            "ok": False,
            "workflow": workflow,
            "error": "invalid arguments: " + "; ".join(errors),
        }
    try:
        argv = builder(params)
    except WorkflowError as exc:
        return {"ok": False, "workflow": workflow, "error": str(exc)}
    # Final guard: the script path must be in the allowlist.
    if not any(argv[0] == p for p in ALLOWED_SCRIPTS.values()):
        return {"ok": False, "workflow": workflow, "error": "script not in allowlist"}
    env = os.environ.copy()
    try:
        proc = subprocess.run(
            [sys.executable, argv[0], *argv[1:]],
            capture_output=True,
            text=True,
            timeout=60,
            env=env,
        )
    except FileNotFoundError as exc:
        return {"ok": False, "workflow": workflow, "error": f"script not found: {exc}"}
    except subprocess.TimeoutExpired:
        return {"ok": False, "workflow": workflow, "error": "script timed out after 60s"}
    except Exception as exc:  # noqa: BLE001 - last-resort guard for the host
        return {"ok": False, "workflow": workflow, "error": f"{type(exc).__name__}: {exc}"}
    return {
        "ok": proc.returncode == 0,
        "workflow": workflow,
        "returncode": proc.returncode,
        "stdout": proc.stdout,
        "stderr": proc.stderr,
    }


# --- public tool handlers -------------------------------------------------
# Each handler follows the documented Hermes contract:
#     def handler(args: dict, **kwargs) -> str
# `args` is the parameter dict from the LLM; **kwargs absorbs any
# future host context. They return a JSON string and never raise.


def _json(result: dict[str, Any]) -> str:
    return json.dumps(result, ensure_ascii=True)


def adjacent_portfolio_snapshot(args: dict, **kwargs: Any) -> str:
    return _json(run_workflow("portfolio_snapshot", args))


def adjacent_tracking(args: dict, **kwargs: Any) -> str:
    return _json(run_workflow("tracking", args))


def adjacent_chart_csv(args: dict, **kwargs: Any) -> str:
    return _json(run_workflow("chart_csv", args))


def adjacent_mcp_query(args: dict, **kwargs: Any) -> str:
    return _json(run_workflow("mcp_query", args))


def adjacent_tracking_table(args: dict, **kwargs: Any) -> str:
    return _json(run_workflow("tracking_table", args))


def adjacent_rebalance_plan(args: dict, **kwargs: Any) -> str:
    return _json(run_workflow("rebalance_plan", args))


def adjacent_datawrapper_index(args: dict, **kwargs: Any) -> str:
    return _json(run_workflow("datawrapper_index", args))


def adjacent_capability_status(args: dict, **kwargs: Any) -> str:
    return _json(run_workflow("capability_status", args))


def adjacent_news_correlation(args: dict, **kwargs: Any) -> str:
    return _json(run_workflow("news_correlation", args))


def adjacent_correlation_regime(args: dict, **kwargs: Any) -> str:
    return _json(run_workflow("correlation_regime", args))


def adjacent_news_latest(args: dict, **kwargs: Any) -> str:
    return _json(run_workflow("news_latest", args))


def adjacent_topic_brief(args: dict, **kwargs: Any) -> str:
    return _json(run_workflow("topic_brief", args))


def adjacent_candles_chart(args: dict, **kwargs: Any) -> str:
    return _json(run_workflow("candles_chart", args))


def adjacent_similar_hedges(args: dict, **kwargs: Any) -> str:
    return _json(run_workflow("similar_hedges", args))


def adjacent_snapshot_health(args: dict, **kwargs: Any) -> str:
    return _json(run_workflow("snapshot_health", args))


def adjacent_http_get(args: dict, **kwargs: Any) -> str:
    return _json(run_workflow("http_get", args))


# Registry: tool name -> handler callable. Used by __init__.py.
TOOL_HANDLERS: dict[str, Any] = {
    "adjacent_portfolio_snapshot": adjacent_portfolio_snapshot,
    "adjacent_tracking": adjacent_tracking,
    "adjacent_chart_csv": adjacent_chart_csv,
    "adjacent_mcp_query": adjacent_mcp_query,
    "adjacent_tracking_table": adjacent_tracking_table,
    "adjacent_rebalance_plan": adjacent_rebalance_plan,
    "adjacent_datawrapper_index": adjacent_datawrapper_index,
    "adjacent_capability_status": adjacent_capability_status,
    "adjacent_news_correlation": adjacent_news_correlation,
    "adjacent_correlation_regime": adjacent_correlation_regime,
    "adjacent_news_latest": adjacent_news_latest,
    "adjacent_topic_brief": adjacent_topic_brief,
    "adjacent_candles_chart": adjacent_candles_chart,
    "adjacent_similar_hedges": adjacent_similar_hedges,
    "adjacent_snapshot_health": adjacent_snapshot_health,
    "adjacent_http_get": adjacent_http_get,
}
