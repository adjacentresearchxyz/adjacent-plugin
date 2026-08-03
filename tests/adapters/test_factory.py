"""Tests for the Factory droid adapter (.factory).

Self-contained unittest, no third-party dependencies.
Run: python -m unittest tests.adapters.test_factory -v
"""

import json
import os
import unittest

from tests.adapters._helpers import (
    EXPECTED_AGENTS,
    FACTORY_DIR,
    MCP_DEV_URL,
    MCP_PROD_URL,
    assert_no_em_dash,
    assert_no_emoji,
    file_exists,
    parse_frontmatter,
    read_file,
)

PACKAGE = ".factory"

# Host tool ids the hooks and droids are written against.
WRITE_TOOLS = ("Create", "Edit", "ApplyPatch")
SHELL_TOOL = "Execute"

EXPECTED_COMMANDS = [
    "daily",
    "briefing-morning",
    "charts-datawrapper-publish",
    "data-ask",
    "data-candles-chart",
    "data-capabilities",
    "data-correlation-regime",
    "data-docs-ask",
    "data-export",
    "data-index-movers",
    "data-market-find",
    "data-news-correlation",
    "data-news-latest",
    "data-similar-hedges",
    "data-snapshot-health",
    "trading-portfolio-snapshot",
    "trading-rebalance-index",
]

EXPECTED_SKILLS = [
    "adjacent-chart-style",
    "adjacent-data-surfaces",
    "adjacent-direct-index",
    "adjacent-index-movers",
    "adjacent-markets",
    "adjacent-news-correlation",
    "adjacent-workflows",
    "briefings",
    "datawrapper-tables",
    "kalshi-api",
    "kalshi-direct-indexing",
]


class TestFactoryManifest(unittest.TestCase):
    """Validate the plugin manifest and the marketplace entry."""

    def test_manifest_exists_at_plugin_root(self):
        self.assertTrue(file_exists("%s/.factory-plugin/plugin.json" % PACKAGE))

    def test_manifest_identity(self):
        data = json.loads(read_file("%s/.factory-plugin/plugin.json" % PACKAGE))
        self.assertEqual(data["name"], "adjacent")
        self.assertTrue(data["version"])
        self.assertTrue(data["description"])

    def test_marketplace_points_at_the_package(self):
        data = json.loads(read_file(".factory-plugin/marketplace.json"))
        self.assertEqual(len(data["plugins"]), 1)
        entry = data["plugins"][0]
        self.assertEqual(entry["name"], "adjacent")
        self.assertEqual(entry["source"], "./%s" % PACKAGE)

    def test_extensibility_dirs_are_at_plugin_root(self):
        """Components must sit beside .factory-plugin/, not inside it."""
        for name in ("commands", "skills", "droids", "hooks", "mcp.json"):
            with self.subTest(component=name):
                self.assertTrue(os.path.exists(os.path.join(FACTORY_DIR, name)))
                self.assertFalse(
                    os.path.exists(
                        os.path.join(FACTORY_DIR, ".factory-plugin", name)
                    )
                )


class TestFactoryMcpJson(unittest.TestCase):
    """Validate mcp.json endpoints."""

    def test_mcp_servers_registered_as_http(self):
        data = json.loads(read_file("%s/mcp.json" % PACKAGE))
        servers = data["mcpServers"]
        for name in ("adjacent-markets", "adjacent-markets-dev"):
            with self.subTest(server=name):
                self.assertEqual(servers[name]["type"], "http")

    def test_urls_are_the_shared_endpoints_without_the_key_param(self):
        """Droid does not expand ${NAME} inside a url, so it must not carry one."""
        data = json.loads(read_file("%s/mcp.json" % PACKAGE))
        servers = data["mcpServers"]
        self.assertEqual(
            servers["adjacent-markets"]["url"], MCP_PROD_URL.split("?")[0]
        )
        self.assertEqual(
            servers["adjacent-markets-dev"]["url"], MCP_DEV_URL.split("?")[0]
        )

    def test_readme_documents_the_realtime_path(self):
        text = read_file("%s/README.md" % PACKAGE).lower()
        self.assertIn("adjacent_api_key", text)
        self.assertIn("delayed", text)


class TestFactoryCommands(unittest.TestCase):
    """Validate the flattened command set."""

    def test_expected_commands_exist(self):
        for name in EXPECTED_COMMANDS:
            path = "%s/commands/%s.md" % (PACKAGE, name)
            with self.subTest(command=name):
                self.assertTrue(file_exists(path), "missing command: %s" % path)

    def test_commands_dir_is_flat_and_has_no_extras(self):
        commands_dir = os.path.join(FACTORY_DIR, "commands")
        entries = sorted(os.listdir(commands_dir))
        self.assertEqual(entries, sorted("%s.md" % n for n in EXPECTED_COMMANDS))

    def test_commands_declare_a_description(self):
        for name in EXPECTED_COMMANDS:
            with self.subTest(command=name):
                fm = parse_frontmatter(
                    read_file("%s/commands/%s.md" % (PACKAGE, name))
                )
                self.assertTrue(fm.get("description"), "%s missing description" % name)

    def test_commands_reference_flat_command_names(self):
        """Nested command paths do not exist in this package."""
        for name in EXPECTED_COMMANDS:
            with self.subTest(command=name):
                body = read_file("%s/commands/%s.md" % (PACKAGE, name))
            for stale in ("/data/", "/trading/", "/briefing/", "/charts/"):
                self.assertNotIn(stale, body, "%s references %s" % (name, stale))

    def test_commands_no_em_dash_or_emoji(self):
        for name in EXPECTED_COMMANDS:
            with self.subTest(command=name):
                text = read_file("%s/commands/%s.md" % (PACKAGE, name))
            self.assertEqual(assert_no_em_dash(text), [], "%s has em-dash" % name)
            self.assertEqual(assert_no_emoji(text), [], "%s has emoji" % name)


class TestFactoryDroids(unittest.TestCase):
    """Validate the droid definitions."""

    def test_expected_droids_exist(self):
        for name in EXPECTED_AGENTS:
            path = "%s/droids/%s.md" % (PACKAGE, name)
            with self.subTest(droid=name):
                self.assertTrue(file_exists(path), "missing droid: %s" % path)

    def test_droids_dir_has_no_extras(self):
        droids_dir = os.path.join(FACTORY_DIR, "droids")
        entries = sorted(os.listdir(droids_dir))
        self.assertEqual(entries, sorted("%s.md" % n for n in EXPECTED_AGENTS))

    def test_droid_name_matches_filename(self):
        for name in EXPECTED_AGENTS:
            with self.subTest(droid=name):
                fm = parse_frontmatter(read_file("%s/droids/%s.md" % (PACKAGE, name)))
                self.assertEqual(fm.get("name"), name)

    def test_droids_inherit_the_session_model(self):
        for name in EXPECTED_AGENTS:
            with self.subTest(droid=name):
                fm = parse_frontmatter(read_file("%s/droids/%s.md" % (PACKAGE, name)))
                self.assertEqual(fm.get("model"), "inherit")

    def test_droids_expose_the_adjacent_mcp_servers(self):
        for name in EXPECTED_AGENTS:
            with self.subTest(droid=name):
                fm = parse_frontmatter(read_file("%s/droids/%s.md" % (PACKAGE, name)))
                servers = fm.get("mcpServers")
                self.assertIsInstance(servers, list, "%s mcpServers not a list" % name)
                self.assertIn("adjacent-markets", servers)
                self.assertIn("adjacent-markets-dev", servers)

    def test_droids_declare_no_write_tool(self):
        for name in EXPECTED_AGENTS:
            with self.subTest(droid=name):
                fm = parse_frontmatter(read_file("%s/droids/%s.md" % (PACKAGE, name)))
                tools = fm.get("tools")
                self.assertIsInstance(tools, list, "%s tools not a list" % name)
            for tool in tools:
                self.assertNotIn(
                    tool, ("Create", "ApplyPatch"), "%s declares a write tool" % name
                )

    def test_droids_state_read_only(self):
        for name in EXPECTED_AGENTS:
            with self.subTest(droid=name):
                body = read_file("%s/droids/%s.md" % (PACKAGE, name)).lower()
            self.assertTrue(
                "read-only" in body or "do not place" in body or "never place" in body,
                "%s does not state its read-only limit" % name,
            )

    def test_droids_no_em_dash_or_emoji(self):
        for name in EXPECTED_AGENTS:
            with self.subTest(droid=name):
                text = read_file("%s/droids/%s.md" % (PACKAGE, name))
            self.assertEqual(assert_no_em_dash(text), [], "%s has em-dash" % name)
            self.assertEqual(assert_no_emoji(text), [], "%s has emoji" % name)


class TestFactoryHooksJson(unittest.TestCase):
    """Validate hook registration against this host's tool ids."""

    def _hooks(self):
        return json.loads(read_file("%s/hooks/hooks.json" % PACKAGE))["hooks"]

    def test_events_are_supported_names(self):
        for event in self._hooks():
            with self.subTest(event=event):
                self.assertIn(event, ("PreToolUse", "PostToolUse"))

    def test_hook_scripts_exist(self):
        for event, groups in self._hooks().items():
            for group in groups:
                for entry in group["hooks"]:
                    command = entry["command"]
                    with self.subTest(event=event, command=command):
                        self.assertEqual(entry["type"], "command")
                        self.assertIn("DROID_PLUGIN_ROOT", command)
                        relative = command.split("DROID_PLUGIN_ROOT}/")[1].rstrip('"')
                        self.assertTrue(
                            file_exists("%s/%s" % (PACKAGE, relative)),
                            "missing hook script: %s" % relative,
                        )

    def test_pre_tool_matchers_use_host_tool_ids(self):
        matchers = [group["matcher"] for group in self._hooks()["PreToolUse"]]
        joined = "|".join(matchers)
        for tool in WRITE_TOOLS + (SHELL_TOOL,):
            with self.subTest(tool=tool):
                self.assertIn(tool, joined)
        for foreign in ("Bash", "Write", "MultiEdit"):
            with self.subTest(tool=foreign):
                self.assertNotIn(foreign, joined)

    def test_conventions_runs_only_on_write_tools(self):
        group = next(
            g
            for g in self._hooks()["PreToolUse"]
            if any("conventions.py" in h["command"] for h in g["hooks"])
        )
        self.assertNotIn(SHELL_TOOL, group["matcher"])
        for tool in WRITE_TOOLS:
            with self.subTest(tool=tool):
                self.assertIn(tool, group["matcher"])

    def test_mover_logger_matches_price_mcp_calls(self):
        groups = self._hooks()["PostToolUse"]
        self.assertTrue(
            any("price" in g["matcher"] for g in groups),
            "mover-logger is not bound to price calls",
        )


class TestFactorySkills(unittest.TestCase):
    """Validate the bundled skills."""

    def test_expected_skills_exist(self):
        for name in EXPECTED_SKILLS:
            path = "%s/skills/%s/SKILL.md" % (PACKAGE, name)
            with self.subTest(skill=name):
                self.assertTrue(file_exists(path), "missing skill: %s" % path)

    def test_skills_declare_name_and_description(self):
        for name in EXPECTED_SKILLS:
            with self.subTest(skill=name):
                fm = parse_frontmatter(
                    read_file("%s/skills/%s/SKILL.md" % (PACKAGE, name))
                )
                self.assertTrue(fm.get("name"), "%s missing name" % name)
                self.assertTrue(fm.get("description"), "%s missing description" % name)


if __name__ == "__main__":
    unittest.main()
