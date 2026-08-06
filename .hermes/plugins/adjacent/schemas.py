"""schemas.py - tool schema definitions for the Adjacent Hermes plugin.

Each schema follows the documented Hermes tool-schema shape:

    {
        "name": "<tool name>",
        "description": "<what the LLM reads to decide when to call it>",
        "parameters": { <JSON Schema (draft-07 shaped) object> },
    }

The `parameters` sub-object is what the handler-side validator in
tools.py checks against. Schemas are plain dicts so they work without a
Hermes installation and can be exercised directly in unit tests.

Conventions: ASCII only, no em-dash, no unicode bullet, `%` never `pp`.
"""

from __future__ import annotations

# Shared building blocks ---------------------------------------------------

_SLUG = {
    "type": "string",
    "minLength": 1,
    "maxLength": 128,
    "pattern": r"^[A-Za-z0-9][A-Za-z0-9_-]*$",
    "description": "Adjacent index slug (matches a catalog key or position file stem).",
}

_ENTITY_ID = {
    "type": "string",
    "minLength": 1,
    "maxLength": 256,
    "pattern": r"^[A-Za-z0-9][A-Za-z0-9_.:-]*$",
    "description": (
        "Adjacent entity id: index/rate slug (e.g. red) or market id in "
        "platform:raw form (e.g. kalshi:KXPRESPARTY-28-R)."
    ),
}

_ENTITY_TYPE = {
    "type": "string",
    "enum": ["index", "rate", "event", "market", "news"],
    "description": "Entity kind required by get/price (and optional for find/list).",
}

_PRICE_TYPE = {
    "type": "string",
    "enum": ["index", "rate", "event", "market"],
    "description": "Entity kind for price (news has no price series).",
}

_OUTPUT_PATH = {
    "type": "string",
    "minLength": 1,
    "description": "Optional filesystem path to write output to instead of capturing stdout.",
}


def _object(properties: dict, required: list[str], extra: bool = False) -> dict:
    return {
        "type": "object",
        "properties": properties,
        "required": required,
        "additionalProperties": extra,
    }


def _schema(name: str, description: str, parameters: dict) -> dict:
    """Build a Hermes-shaped tool schema: name + description + the JSON
    Schema `parameters` object the LLM and validator use."""
    return {
        "name": name,
        "description": description,
        "parameters": parameters,
    }


# Tool schemas -------------------------------------------------------------

PORTFOLIO_SNAPSHOT = _schema(
    "adjacent_portfolio_snapshot",
    (
        "Report portfolio status for one or all indices from cached "
        "position documents. Read-only. Wraps scripts/portfolio-snapshot.py."
    ),
    _object(
        {
            "index": _SLUG,
            "include_pnl": {"type": "boolean", "default": False},
            "as_json": {"type": "boolean", "default": False},
        },
        required=[],
        extra=False,
    ),
)

TRACKING = _schema(
    "adjacent_tracking",
    (
        "Produce a per-position mid-based table for an index: size, mid, "
        "cost basis, notional, %-weight, and return against cost basis. "
        "This is the per-position leg of the tracking report, not the "
        "tracking error itself (that needs an index reference series). "
        "Wraps scripts/tracking-index.py."
    ),
    _object(
        {"index": _SLUG, "as_json": {"type": "boolean", "default": False}},
        required=["index"],
        extra=False,
    ),
)

CHART_CSV = _schema(
    "adjacent_chart_csv",
    (
        "Build a per-index 24h %-return chart CSV (index vs portfolio, "
        "both rebased to 100 at the last fill). Wraps scripts/chart-index.py."
    ),
    _object(
        {"index": _SLUG, "output": _OUTPUT_PATH},
        required=["index"],
        extra=False,
    ),
)

MCP_QUERY = _schema(
    "adjacent_mcp_query",
    (
        "Run a read-only Adjacent MCP query (list / find / get / price) "
        "via scripts/mcp-cli.py. No API key required for the delayed tier. "
        "get and price require type; find takes query (topic is a legacy alias); "
        "price takes id (slug is a legacy alias for index/rate ids)."
    ),
    _object(
        {
            "tool": {
                "type": "string",
                "enum": ["list", "find", "get", "price"],
                "description": "Adjacent MCP tool to invoke (read-only).",
            },
            "type": {
                "type": "string",
                "enum": [
                    "events",
                    "event",
                    "market",
                    "markets",
                    "index",
                    "indices",
                    "rate",
                    "news",
                ],
                "description": (
                    "Entity kind. Required for get and price; optional filter "
                    "for find/list."
                ),
            },
            "query": {
                "type": "string",
                "minLength": 1,
                "description": "Free-text query for the `find` tool.",
            },
            "topic": {
                "type": "string",
                "minLength": 1,
                "description": "Legacy alias for `query` on `find`.",
            },
            "id": _ENTITY_ID,
            "slug": {
                **_ENTITY_ID,
                "description": (
                    "Legacy alias for `id` on `price` (index/rate slugs or "
                    "platform:raw market ids)."
                ),
            },
            "timeframe": {
                "type": "string",
                "description": "Timeframe for the `price` tool (e.g. 24h, 7d, 30d, 1d).",
            },
            "raw": {
                "type": "boolean",
                "default": False,
                "description": "Return raw timeseries for `price`.",
            },
            "fallback_venue": {
                "type": "string",
                "enum": ["kalshi", "polymarket"],
                "description": (
                    "Optional read-only fallback for a market price when "
                    "Adjacent MCP fails. Requires a prefixed market id."
                ),
            },
            "side": {
                "type": "string",
                "enum": ["yes", "no"],
                "default": "yes",
                "description": (
                    "Outcome side for a Kalshi fallback quote. Ignored for "
                    "Polymarket and normal Adjacent price calls."
                ),
            },
        },
        required=["tool"],
        extra=False,
    ),
)

TRACKING_TABLE = _schema(
    "adjacent_tracking_table",
    (
        "Build a per-position table CSV for an index from a prior "
        "tracking-index.py run. Same columns as adjacent_tracking, so it "
        "is not a tracking-error table. Wraps scripts/table-tracking.py."
    ),
    _object(
        {"index": _SLUG, "output": _OUTPUT_PATH},
        required=["index"],
        extra=False,
    ),
)

REBALANCE_PLAN = _schema(
    "adjacent_rebalance_plan",
    (
        "Compute a direct-index rebalance PLAN only. This tool is "
        "fail-closed and never places orders: it forces --dry-run so "
        "no exchange credentials are exercised. Wraps "
        "scripts/rebalance-index.py."
    ),
    _object(
        {
            "index": _SLUG,
            "exchange": {
                "type": "string",
                "enum": ["kalshi"],
                "default": "kalshi",
                "description": "Exchange adapter to target.",
            },
            "plan": {
                "type": "string",
                "minLength": 1,
                "description": "Path to a compact plan JSON.",
            },
        },
        required=["index", "plan"],
        extra=False,
    ),
)

DATAWRAPPER_INDEX = _schema(
    "adjacent_datawrapper_index",
    (
        "Rebuild a per-index tracking chart CSV and optionally publish "
        "it to Datawrapper. Defaults to no_publish=true so the safe "
        "path is CSV-only. Wraps scripts/datawrapper-index.py."
    ),
    _object(
        {
            "index": _SLUG,
            "chart_id": {
                "type": "string",
                "minLength": 1,
                "description": "Datawrapper chart id.",
            },
            "no_publish": {
                "type": "boolean",
                "default": True,
                "description": "When true (the default), build the CSV only and do not publish.",
            },
        },
        required=["index", "chart_id"],
        extra=False,
    ),
)

CAPABILITY_STATUS = _schema(
    "adjacent_capability_status",
    "Report live, guided, offline-only, and unavailable Adjacent data surfaces.",
    _object({}, required=[], extra=False),
)

NEWS_CORRELATION = _schema(
    "adjacent_news_correlation",
    (
        "Rank news events by minute-aligned mid moves. Accepts article "
        "JSON from the live news/latest surface (see adjacent_news_latest) "
        "or supplied files."
    ),
    _object(
        {
            "news": {
                "type": "string",
                "minLength": 1,
                "description": "Path to article JSON.",
            },
            "prices": {
                "type": "string",
                "minLength": 1,
                "description": "Path to mid-price JSON.",
            },
            "window_minutes": {
                "type": "integer",
                "default": 30,
                "minimum": 1,
            },
        },
        required=["news", "prices"],
        extra=False,
    ),
)

CORRELATION_REGIME = _schema(
    "adjacent_correlation_regime",
    (
        "Flag sigma-level shifts from supplied correlation observations. "
        "Offline analysis only; never calls the unavailable correlation endpoint."
    ),
    _object(
        {
            "input": {
                "type": "string",
                "minLength": 1,
                "description": "Path to correlation observation JSON.",
            },
            "sigma": {
                "type": "number",
                "default": 2.0,
                "minimum": 0.1,
            },
        },
        required=["input"],
        extra=False,
    ),
)

NEWS_LATEST = _schema(
    "adjacent_news_latest",
    (
        "Fetch the live Adjacent news/latest surface via the read-only MCP "
        "list tool. Set normalize=true to emit rows shaped for "
        "adjacent_news_correlation. Wraps scripts/news-latest.py."
    ),
    _object(
        {"normalize": {"type": "boolean", "default": False}},
        required=[],
        extra=False,
    ),
)

CANDLES_CHART = _schema(
    "adjacent_candles_chart",
    (
        "Build a mid-based ts,close chart CSV from Adjacent market candles "
        "(markets/{id}/candles). Wraps scripts/candles-chart.py."
    ),
    _object(
        {
            "input": {
                "type": "string",
                "minLength": 1,
                "description": "Path to candle JSON.",
            },
            "output": _OUTPUT_PATH,
            "rebase": {"type": "boolean", "default": False},
        },
        required=["input"],
        extra=False,
    ),
)

SIMILAR_HEDGES = _schema(
    "adjacent_similar_hedges",
    (
        "Rank similar markets (markets/{id}/similar) into hedges (negative "
        "mid correlation) and proxies (positive). Wraps "
        "scripts/similar-hedges.py."
    ),
    _object(
        {
            "input": {
                "type": "string",
                "minLength": 1,
                "description": "Path to similar-markets JSON with signed correlations.",
            },
            "min_abs_correlation": {
                "type": "number",
                "default": 0.3,
                "minimum": 0.0,
            },
        },
        required=["input"],
        extra=False,
    ),
)

SNAPSHOT_HEALTH = _schema(
    "adjacent_snapshot_health",
    (
        "Grade Adjacent public snapshots (/public/*) fresh, stale, or "
        "error against a max age. Wraps scripts/snapshot-health.py."
    ),
    _object(
        {
            "input": {
                "type": "string",
                "minLength": 1,
                "description": "Path to snapshot descriptor JSON.",
            },
            "live": {"type": "boolean", "default": False},
        },
        required=["input"],
        extra=False,
    ),
)

HTTP_GET = _schema(
    "adjacent_http_get",
    (
        "GET a read-only Adjacent surface (exports, docs archive, public "
        "data). HTTPS Adjacent hosts only. Backs the export cookbook and "
        "docs Q&A. Wraps scripts/http-get.py."
    ),
    _object(
        {
            "url": {
                "type": "string",
                "minLength": 1,
                "description": "HTTPS Adjacent URL to fetch.",
            },
            "output": _OUTPUT_PATH,
        },
        required=["url"],
        extra=False,
    ),
)

# Registry exposed to tools.py / __init__.py. Keys are the tool names
# registered with the host; values are the Hermes-shaped schema dicts.
TOOL_SCHEMAS: dict[str, dict] = {
    "adjacent_portfolio_snapshot": PORTFOLIO_SNAPSHOT,
    "adjacent_tracking": TRACKING,
    "adjacent_chart_csv": CHART_CSV,
    "adjacent_mcp_query": MCP_QUERY,
    "adjacent_tracking_table": TRACKING_TABLE,
    "adjacent_rebalance_plan": REBALANCE_PLAN,
    "adjacent_datawrapper_index": DATAWRAPPER_INDEX,
    "adjacent_capability_status": CAPABILITY_STATUS,
    "adjacent_news_correlation": NEWS_CORRELATION,
    "adjacent_correlation_regime": CORRELATION_REGIME,
    "adjacent_news_latest": NEWS_LATEST,
    "adjacent_candles_chart": CANDLES_CHART,
    "adjacent_similar_hedges": SIMILAR_HEDGES,
    "adjacent_snapshot_health": SNAPSHOT_HEALTH,
    "adjacent_http_get": HTTP_GET,
}
