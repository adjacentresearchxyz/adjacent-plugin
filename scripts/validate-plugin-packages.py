#!/usr/bin/env python3
"""Validate shared contracts and host-package boundaries."""

from __future__ import annotations

import json
import os
import sys
import tomllib
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
IGNORED_DIRS = {"node_modules", "dist", "__pycache__", ".git"}
FORBIDDEN = {
    "\u2014": "em-dash",
    "\u2022": "unicode bullet",
}
EXPECTED_SERVERS = {
    "adjacent-markets": "https://mcp.adjacent.markets/mcp?apiKey=${ADJACENT_API_KEY}",
    "adjacent-markets-dev": "https://mcp.dev.adjacent.markets/mcp?apiKey=${ADJACENT_API_KEY}",
}
CODEX_AGENTS = {
    "coordinator",
    "index-monitor",
    "data-monitor",
    "briefing-writer",
    "ask-assistant",
}
# Skills that legitimately ship in one package only, with the reason.
# Everything else must exist in both packages and be byte-identical;
# the shared set is derived from the directories rather than listed, so
# a new skill added to one package cannot silently escape the check.
HOST_SPECIFIC_SKILLS = {
    "hermes": "documents this host's own runtime; the name is a foreign "
    "platform reference in the other package",
}
PACKAGES = {
    ".claude-plugin": {"hermes", "codex", "cursor", "openclaw"},
    "plugins/adjacent": {"hermes", "codex", "cursor", "openclaw"},
    ".hermes": {"claude", "codex", "cursor", "openclaw"},
    ".codex": {"claude", "hermes", "cursor", "openclaw"},
    ".cursor": {"claude", "hermes", "codex", "openclaw"},
    "openclaw-plugin": {"claude", "hermes", "codex", "cursor"},
}
TEXT_SUFFIXES = {".md", ".py", ".toml", ".yaml", ".json", ".ts"}
HOST_NAMES = set().union(*PACKAGES.values())
# Agent-facing docs stay host-neutral so no package inherits another host's
# instructions. The root README is exempt: it is the repo landing page and has
# to name every host to route a reader to the right package directory.
SHARED_DOCS = (ROOT / "AGENTS.md", ROOT / "ROADMAP.md")


def fail(message: str) -> None:
    print(f"error: {message}", file=sys.stderr)
    raise SystemExit(1)


def iter_source_files(root: Path):
    for current, dirs, files in os.walk(root):
        dirs[:] = [name for name in dirs if name not in IGNORED_DIRS]
        yield from (Path(current) / name for name in files)


def load_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        fail(f"{path.relative_to(ROOT)} is not valid JSON: {exc}")


def assert_mcp_contract(path: Path) -> None:
    payload = load_json(path)
    servers = payload.get("mcpServers")
    if not isinstance(servers, dict):
        fail(f"{path.relative_to(ROOT)} must contain an mcpServers object")
    actual = {name: item.get("url") for name, item in servers.items()}
    if actual != EXPECTED_SERVERS:
        fail(f"{path.relative_to(ROOT)} MCP URLs do not match the shared contract")


def assert_hermes_manifest() -> None:
    manifest = ROOT / ".hermes/plugins/adjacent/plugin.yaml"
    text = manifest.read_text(encoding="utf-8")
    for field in ("name: adjacent", "version:", "description:", "provides_tools:", "provides_hooks:"):
        if field not in text:
            fail(f"Hermes manifest is missing {field!r}")


def assert_capability_contract() -> None:
    payload = load_json(ROOT / "data/capabilities.json")
    capabilities = payload.get("capabilities", {})
    news = capabilities.get("news_latest", {})
    if news.get("api_status") != "live":
        fail("news_latest must be live")
    if news.get("plugin_status") != "guided":
        fail("news_latest must be guided now that the endpoint is live")
    correlation = capabilities.get("index_correlation", {})
    if correlation.get("api_status") != "unavailable":
        fail("index_correlation must remain unavailable until its endpoint is live")
    if correlation.get("plugin_status") != "offline_analysis_only":
        fail("index_correlation must remain offline-analysis-only")
    if "rates_oracles" in capabilities:
        fail("rates_oracles surface has been removed; drop it from capabilities.json")


def assert_codex_contract() -> None:
    config_path = ROOT / ".codex/config.toml"
    try:
        config = tomllib.loads(config_path.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError) as exc:
        fail(f".codex/config.toml is not valid TOML: {exc}")
    servers = config.get("mcp_servers")
    if not isinstance(servers, dict):
        fail(".codex/config.toml must define mcp_servers")
    if {name: item.get("url") for name, item in servers.items()} != EXPECTED_SERVERS:
        fail(".codex/config.toml MCP URLs do not match the shared contract")
    agents = config.get("agents")
    if not isinstance(agents, dict) or set(agents) != CODEX_AGENTS:
        fail(".codex/config.toml must declare exactly the shared role agents")
    for name, definition in agents.items():
        if not isinstance(definition, dict):
            fail(f"Codex agent {name} must be a TOML table")
        config_file = definition.get("config_file")
        if not isinstance(config_file, str):
            fail(f"Codex agent {name} is missing config_file")
        path = ROOT / ".codex" / config_file
        if not path.is_file():
            fail(f"Codex agent {name} config file does not exist: {config_file}")


def assert_openclaw_contract() -> None:
    manifest_path = ROOT / "openclaw-plugin/openclaw.plugin.json"
    manifest = load_json(manifest_path)
    if manifest.get("id") != "adjacent-markets":
        fail("OpenClaw manifest must use id adjacent-markets")
    tools = manifest.get("contracts", {}).get("tools")
    expected_tools = {
        "adjacent_discover",
        "adjacent_price",
        "adjacent_movers",
        "adjacent_capabilities",
    }
    if not isinstance(tools, list) or set(tools) != expected_tools:
        fail("OpenClaw manifest tool contract does not match the supported tools")
    entrypoint = ROOT / "openclaw-plugin/src/index.ts"
    if not entrypoint.is_file():
        fail("OpenClaw TypeScript entrypoint is missing")
    source = entrypoint.read_text(encoding="utf-8")
    if "defineToolPlugin" not in source:
        fail("OpenClaw entrypoint must use defineToolPlugin")
    for tool in expected_tools:
        if f'name: "{tool}"' not in source:
            fail(f"OpenClaw entrypoint is missing {tool}")
    servers = manifest.get("mcpServers")
    if not isinstance(servers, dict):
        fail("OpenClaw manifest must define mcpServers")
    for name, url in EXPECTED_SERVERS.items():
        args = servers.get(name, {}).get("args", [])
        if not isinstance(args, list) or url not in args:
            fail(f"OpenClaw MCP server {name} does not use the shared endpoint")


def _skill_names(root: Path) -> set[str]:
    if not root.is_dir():
        fail(f"skills directory does not exist: {root.relative_to(ROOT)}")
    return {child.name for child in root.iterdir() if child.is_dir()}


def assert_skill_parity() -> None:
    canonical = ROOT / "plugins/adjacent/skills"
    other = ROOT / ".hermes/plugins/adjacent/skills"
    canonical_names = _skill_names(canonical)
    other_names = _skill_names(other)

    for name in sorted(canonical_names.symmetric_difference(other_names)):
        if name in HOST_SPECIFIC_SKILLS:
            continue
        present, absent = (
            ("plugins/adjacent", ".hermes") if name in canonical_names else (".hermes", "plugins/adjacent")
        )
        fail(
            f"skill {name!r} ships in {present} but not {absent}; add it to both "
            f"or record it in HOST_SPECIFIC_SKILLS with a reason"
        )

    for name in sorted(canonical_names & other_names):
        canonical_path = canonical / name / "SKILL.md"
        other_path = other / name / "SKILL.md"
        for path in (canonical_path, other_path):
            if not path.is_file():
                fail(f"skill {name!r} is missing {path.relative_to(ROOT)}")
        if canonical_path.read_bytes() != other_path.read_bytes():
            fail(f"Shared skill has drifted between packages: {name}")


def assert_package_boundaries() -> None:
    for relative_root, forbidden_names in PACKAGES.items():
        package = ROOT / relative_root
        for path in iter_source_files(package):
            relative_path = str(path.relative_to(package)).lower()
            for name in forbidden_names:
                if name in relative_path:
                    fail(f"{relative_root} contains foreign platform path: {relative_path}")
            if path.suffix not in TEXT_SUFFIXES:
                continue
            text = path.read_text(encoding="utf-8")
            lower_text = text.lower()
            for name in forbidden_names:
                if name in lower_text:
                    fail(f"{relative_root} contains foreign platform reference in {relative_path}")
            for codepoint, name in FORBIDDEN.items():
                if codepoint in text:
                    fail(f"{path.relative_to(ROOT)} contains forbidden {name}")


def assert_shared_assets_are_neutral() -> None:
    scripts = (
        path
        for path in iter_source_files(ROOT / "scripts")
        if path.name != Path(__file__).name
    )
    paths = (*SHARED_DOCS, *iter_source_files(ROOT / "data"), *scripts)
    for path in paths:
        text = path.read_text(encoding="utf-8").lower()
        for name in HOST_NAMES:
            if name in text:
                fail(f"{path.relative_to(ROOT)} contains host-specific reference: {name}")


def main() -> None:
    assert_mcp_contract(ROOT / "plugins/adjacent/mcp.json")
    assert_mcp_contract(ROOT / ".cursor/mcp.json")
    assert_hermes_manifest()
    assert_capability_contract()
    assert_codex_contract()
    assert_openclaw_contract()
    assert_skill_parity()
    assert_package_boundaries()
    assert_shared_assets_are_neutral()
    print("plugin package validation passed")


if __name__ == "__main__":
    main()
