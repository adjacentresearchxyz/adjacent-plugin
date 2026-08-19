"""Hermes-native Adjacent prediction-market plugin."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from . import hooks as _hooks
from . import schemas as _schemas
from . import tools as _tools

__version__ = "1.0.1"
__all__ = [
    "register",
    "adjacent_command_handler",
    "hooks",
    "schemas",
    "tools",
    "__version__",
]

_PLUGIN_DIR = Path(__file__).resolve().parent
_SKILLS_DIR = _PLUGIN_DIR / "skills"

# Skill name -> relative path of the bundled SKILL.md.
BUNDLED_SKILLS: dict[str, str] = {
    "hermes": "hermes/SKILL.md",
    "adjacent-markets": "adjacent-markets/SKILL.md",
    "adjacent-data-surfaces": "adjacent-data-surfaces/SKILL.md",
    "adjacent-index-movers": "adjacent-index-movers/SKILL.md",
    "adjacent-news-correlation": "adjacent-news-correlation/SKILL.md",
    "adjacent-topic-brief": "adjacent-topic-brief/SKILL.md",
    "adjacent-direct-index": "adjacent-direct-index/SKILL.md",
    "adjacent-chart-style": "adjacent-chart-style/SKILL.md",
    "adjacent-workflows": "adjacent-workflows/SKILL.md",
    "using-adjacent": "using-adjacent/SKILL.md",
    "briefings": "briefings/SKILL.md",
    "kalshi-api": "kalshi-api/SKILL.md",
    "kalshi-direct-indexing": "kalshi-direct-indexing/SKILL.md",
    "datawrapper-tables": "datawrapper-tables/SKILL.md",
}

# Workflow name -> tool handler callable, used by the /adjacent command.
_WORKFLOW_TOOLS: dict[str, Any] = {
    "brief_daily": _tools.adjacent_brief_daily,
    "market_snapshot": _tools.adjacent_market_snapshot,
    "movers": _tools.adjacent_movers,
    "portfolio_snapshot": _tools.adjacent_portfolio_snapshot,
    "tracking": _tools.adjacent_tracking,
    "chart_csv": _tools.adjacent_chart_csv,
    "mcp_query": _tools.adjacent_mcp_query,
    "tracking_table": _tools.adjacent_tracking_table,
    "rebalance_plan": _tools.adjacent_rebalance_plan,
    "datawrapper_index": _tools.adjacent_datawrapper_index,
    "capability_status": _tools.adjacent_capability_status,
    "news_correlation": _tools.adjacent_news_correlation,
    "correlation_regime": _tools.adjacent_correlation_regime,
    "news_latest": _tools.adjacent_news_latest,
    "topic_brief": _tools.adjacent_topic_brief,
    "candles_chart": _tools.adjacent_candles_chart,
    "similar_hedges": _tools.adjacent_similar_hedges,
    "snapshot_health": _tools.adjacent_snapshot_health,
    "http_get": _tools.adjacent_http_get,
}

_HELP_TEXT = (
    "/adjacent - safe Adjacent prediction-market workflows.\n"
    "\n"
    "Usage:\n"
    "  /adjacent                        show this help\n"
    "  /adjacent --explain              show this help\n"
    "  /adjacent workflow <name> [--flag value ...]\n"
    "\n"
    "Workflows:\n"
    "  brief_daily          daily brief with movers and text\n"
    "  market_snapshot      tradable snapshot from topic/index/ids\n"
    "  movers               threshold movers scan (no prose)\n"
    "  portfolio_snapshot   read-only portfolio status\n"
    "  tracking             per-row mid-based tracking error\n"
    "  chart_csv            build a chart CSV\n"
    "  mcp_query            read-only Adjacent MCP query\n"
    "  tracking_table       tracking-error table CSV\n"
    "  rebalance_plan       fail-closed rebalance PLAN (never places)\n"
    "  datawrapper_index    rebuild a Datawrapper chart CSV\n"
    "  capability_status    show live and unavailable data surfaces\n"
    "  news_correlation     rank live or supplied news vs mid moves\n"
    "  correlation_regime   analyze supplied correlation JSON\n"
    "  news_latest          fetch the live news/latest surface\n"
    "  topic_brief          topic news + markets + mids (+ charts)\n"
    "  candles_chart        build a mid-based candle chart CSV\n"
    "  similar_hedges       rank similar markets into hedges/proxies\n"
    "  snapshot_health      grade public snapshot freshness\n"
    "  http_get             fetch an Adjacent export or docs surface\n"
    "\n"
    "Conventions: mid-quote pricing, % never pp, ASCII only, no em-dash,\n"
    "no emoji.\n"
)


_TRUE_TOKENS = {"true", "1", "yes", "on"}
_FALSE_TOKENS = {"false", "0", "no", "off"}


def _parse_command_args(tokens: list[str]) -> dict[str, Any]:
    """Parse a list of `--flag value` tokens into a dict. A flag with no
    following value defaults to True (boolean). This is pure Python
    token handling: it never shells out and never interpolates user
    input into a command string."""
    args: dict[str, Any] = {}
    i = 0
    while i < len(tokens):
        tok = tokens[i]
        if tok.startswith("--"):
            key = tok[2:].replace("-", "_")
            if i + 1 < len(tokens) and not tokens[i + 1].startswith("--"):
                args[key] = tokens[i + 1]
                i += 2
            else:
                args[key] = True
                i += 1
        else:
            i += 1
    return args


def _coerce_params(workflow: str, params: dict[str, Any]) -> dict[str, Any]:
    """Cast command-line strings to the JSON types the schema declares.

    Command tokens always arrive as strings, but the handler-side
    validator in tools.py type-checks against the `parameters` schema,
    so an uncoerced `--sigma 2.5` is rejected as "expected number, got
    str". A value that cannot be cast is passed through untouched so
    the validator reports the mismatch instead of this function
    swallowing it.
    """
    entry = _tools.ALLOWED_WORKFLOWS.get(workflow)
    if entry is None:
        return params
    parameters = _schemas.TOOL_SCHEMAS[entry[0]].get("parameters", {})
    properties = parameters.get("properties", {}) or {}
    coerced: dict[str, Any] = {}
    for key, value in params.items():
        declared = (properties.get(key) or {}).get("type")
        coerced[key] = _coerce_one(declared, value)
    return coerced


def _coerce_one(declared: str | None, value: Any) -> Any:
    if not isinstance(value, str):
        return value
    if declared == "boolean":
        lowered = value.strip().lower()
        if lowered in _TRUE_TOKENS:
            return True
        if lowered in _FALSE_TOKENS:
            return False
        return value
    if declared == "integer":
        try:
            return int(value.strip())
        except ValueError:
            return value
    if declared == "number":
        try:
            return float(value.strip())
        except ValueError:
            return value
    return value


def adjacent_command_handler(raw_args: str) -> str:
    """Handler for the /adjacent slash command.

    Receives the raw argument string the user typed after the command
    name, parses a simple `--flag value` grammar, and either shows help
    or routes to an allowlisted tool handler. It never shells out and
    never interpolates user input into a command string; it hands a
    parsed dict straight to the Python tool handler, which itself only
    dispatches to the fixed allowlist of local scripts.
    """
    tokens = (raw_args or "").split()
    if not tokens or tokens[0] in ("--explain", "-h", "help"):
        return _HELP_TEXT
    if tokens[0] != "workflow":
        return _HELP_TEXT + "\nUnknown subcommand: " + tokens[0] + "\n"
    if len(tokens) < 2:
        return _HELP_TEXT + "\nworkflow requires a <name> argument.\n"
    name = tokens[1]
    handler = _WORKFLOW_TOOLS.get(name)
    if handler is None:
        return (
            _HELP_TEXT
            + "\nUnknown workflow: "
            + name
            + "\nAllowed: "
            + ", ".join(sorted(_WORKFLOW_TOOLS))
            + "\n"
        )
    params = _coerce_params(name, _parse_command_args(tokens[2:]))
    # Tool handlers follow def handler(args: dict, **kwargs) -> str.
    return handler(params)


def register(ctx: Any) -> None:
    for name, handler in _tools.TOOL_HANDLERS.items():
        schema = _schemas.TOOL_SCHEMAS[name]
        ctx.register_tool(
            name=name,
            toolset="adjacent",
            schema=schema,
            handler=handler,
            description=schema["description"],
        )

    for name, relative_path in BUNDLED_SKILLS.items():
        ctx.register_skill(name, str(_SKILLS_DIR / relative_path))

    ctx.register_hook("pre_tool_call", _hooks.pre_tool_call)
    ctx.register_hook("post_tool_call", _hooks.post_tool_call)
    ctx.register_command(
        "adjacent",
        handler=adjacent_command_handler,
        description="Explain and dispatch the safe Adjacent workflows.",
    )
