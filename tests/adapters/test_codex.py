"""Tests for the Codex adapter (.codex/).

Self-contained unittest, no third-party dependencies.
Run: python -m unittest tests.adapters.test_codex -v
"""

import os
import unittest

from tests.adapters._helpers import (
    CODEX_DIR,
    EXPECTED_AGENTS,
    MCP_DEV_URL,
    MCP_PROD_URL,
    READONLY_TOOL_PREFIXES,
    assert_no_em_dash,
    assert_no_emoji,
    file_exists,
    parse_toml,
    read_file,
)

# Required top-level fields in every agent TOML (official Codex format).
REQUIRED_AGENT_FIELDS = (
    "name",
    "description",
    "model",
    "model_reasoning_effort",
    "sandbox_mode",
    "developer_instructions",
)

# sandbox_mode value that enforces read-only / no-orders intent.
READONLY_SANDBOX = "read-only"

# Tools that would mutate files or place trades; forbidden in any agent.
FORBIDDEN_TOOLS = ("write", "edit", "multiedit", "create", "delete", "trade", "order")


class TestCodexConfig(unittest.TestCase):
    """Validate .codex/config.toml structure, MCP endpoints, and agent declarations."""

    def test_config_file_exists(self):
        self.assertTrue(
            file_exists(".codex/config.toml"),
            ".codex/config.toml is missing",
        )

    def test_config_parses_as_toml(self):
        data = parse_toml(read_file(".codex/config.toml"))
        self.assertIn("mcp_servers", data)

    def test_mcp_servers_registered(self):
        data = parse_toml(read_file(".codex/config.toml"))
        servers = data.get("mcp_servers", {})
        self.assertIn("adjacent-markets", servers)
        self.assertIn("adjacent-markets-dev", servers)

    def test_mcp_urls_match_canonical(self):
        data = parse_toml(read_file(".codex/config.toml"))
        servers = data["mcp_servers"]
        self.assertEqual(servers["adjacent-markets"]["url"], MCP_PROD_URL)
        self.assertEqual(servers["adjacent-markets-dev"]["url"], MCP_DEV_URL)

    def test_config_declares_four_agents(self):
        data = parse_toml(read_file(".codex/config.toml"))
        agents = data.get("agents", {})
        for name in EXPECTED_AGENTS:
            with self.subTest(agent=name):
                self.assertIn(name, agents, "config.toml missing [agents.%s]" % name)

    def test_agent_declarations_have_description_and_config_file(self):
        data = parse_toml(read_file(".codex/config.toml"))
        agents = data["agents"]
        for name in EXPECTED_AGENTS:
            with self.subTest(agent=name):
                entry = agents[name]
                self.assertTrue(
                    entry.get("description"),
                    "%s missing description in config" % name,
                )
                cfg = entry.get("config_file")
                self.assertTrue(cfg, "%s missing config_file in config" % name)
                # config_file must point at the agents/<role>.toml file.
                self.assertTrue(
                    cfg.endswith("agents/%s.toml" % name),
                    "%s config_file does not point at agents/%s.toml: %s"
                    % (name, name, cfg),
                )

    def test_config_agent_config_files_exist(self):
        data = parse_toml(read_file(".codex/config.toml"))
        for name in EXPECTED_AGENTS:
            with self.subTest(agent=name):
                cfg = data["agents"][name]["config_file"]
                # Resolve relative to the .codex directory.
                full = os.path.join(CODEX_DIR, cfg)
                self.assertTrue(
                    os.path.isfile(full),
                    "%s config_file %s does not exist" % (name, cfg),
                )

    def test_config_has_no_em_dash_or_emoji(self):
        text = read_file(".codex/config.toml")
        self.assertEqual(assert_no_em_dash(text), [], "config.toml has em-dash")
        self.assertEqual(assert_no_emoji(text), [], "config.toml has emoji")


class TestCodexAgents(unittest.TestCase):
    """Validate the Codex agent TOML files."""

    def test_agent_toml_files_exist(self):
        for name in EXPECTED_AGENTS:
            path = ".codex/agents/%s.toml" % name
            self.assertTrue(file_exists(path), "missing agent file: %s" % path)

    def test_no_markdown_agent_files_remain(self):
        agents_dir = os.path.join(CODEX_DIR, "agents")
        md_files = [f for f in os.listdir(agents_dir) if f.endswith(".md")]
        self.assertEqual(
            md_files,
            [],
            "legacy .md agent files still present: %s" % md_files,
        )

    def test_agents_dir_has_no_extra_toml(self):
        agents_dir = os.path.join(CODEX_DIR, "agents")
        toml_files = sorted(
            f for f in os.listdir(agents_dir) if f.endswith(".toml")
        )
        expected = sorted("%s.toml" % n for n in EXPECTED_AGENTS)
        self.assertEqual(
            toml_files, expected, "unexpected agent files in .codex/agents"
        )

    def test_agent_required_fields(self):
        for name in EXPECTED_AGENTS:
            with self.subTest(agent=name):
                data = parse_toml(read_file(".codex/agents/%s.toml" % name))
            for field in REQUIRED_AGENT_FIELDS:
                self.assertIn(
                    field,
                    data,
                    "%s missing required field %s" % (name, field),
                )

    def test_agent_name_matches_filename(self):
        for name in EXPECTED_AGENTS:
            with self.subTest(agent=name):
                data = parse_toml(read_file(".codex/agents/%s.toml" % name))
            self.assertEqual(
                data.get("name"),
                name,
                "%s name field does not match filename" % name,
            )

    def test_agent_description_matches_config(self):
        config = parse_toml(read_file(".codex/config.toml"))
        for name in EXPECTED_AGENTS:
            with self.subTest(agent=name):
                agent = parse_toml(read_file(".codex/agents/%s.toml" % name))
            self.assertEqual(
                agent.get("description"),
                config["agents"][name].get("description"),
                "%s description diverges between config and agent TOML" % name,
            )

    def test_agent_sandbox_mode_is_readonly(self):
        for name in EXPECTED_AGENTS:
            with self.subTest(agent=name):
                data = parse_toml(read_file(".codex/agents/%s.toml" % name))
            self.assertEqual(
                data.get("sandbox_mode"),
                READONLY_SANDBOX,
                "%s sandbox_mode is not read-only" % name,
            )

    def test_agent_model_reasoning_effort_set(self):
        for name in EXPECTED_AGENTS:
            with self.subTest(agent=name):
                data = parse_toml(read_file(".codex/agents/%s.toml" % name))
            self.assertTrue(
                data.get("model_reasoning_effort"),
                "%s missing model_reasoning_effort value" % name,
            )

    def test_agent_tools_are_readonly(self):
        """No agent may declare a write/trade tool."""
        for name in EXPECTED_AGENTS:
            with self.subTest(agent=name):
                data = parse_toml(read_file(".codex/agents/%s.toml" % name))
            tools = data.get("tools", [])
            self.assertIsInstance(tools, list, "%s tools not a list" % name)
            for tool in tools:
                lower = tool.lower()
                for bad in FORBIDDEN_TOOLS:
                    self.assertNotIn(
                        bad,
                        lower,
                        "%s declares forbidden tool %s" % (name, tool),
                    )

    def test_agent_tools_reference_adjacent_mcp(self):
        for name in EXPECTED_AGENTS:
            with self.subTest(agent=name):
                data = parse_toml(read_file(".codex/agents/%s.toml" % name))
            tools = data.get("tools", [])
            adjacent_tools = [
                t for t in tools if t.startswith(READONLY_TOOL_PREFIXES)
            ]
            self.assertTrue(
                adjacent_tools,
                "%s has no adjacent-markets MCP tools" % name,
            )

    def test_agents_no_em_dash_or_emoji(self):
        for name in EXPECTED_AGENTS:
            with self.subTest(agent=name):
                text = read_file(".codex/agents/%s.toml" % name)
            self.assertEqual(
                assert_no_em_dash(text), [], "%s has em-dash" % name
            )
            self.assertEqual(
                assert_no_emoji(text), [], "%s has emoji" % name
            )

    def test_developer_instructions_state_readonly(self):
        """Each developer_instructions body must state it is read-only / no orders."""
        for name in EXPECTED_AGENTS:
            with self.subTest(agent=name):
                data = parse_toml(read_file(".codex/agents/%s.toml" % name))
            body = (data.get("developer_instructions") or "").lower()
            self.assertTrue(
                "read-only" in body or "read only" in body,
                "%s developer_instructions does not state read-only" % name,
            )
            self.assertNotIn(
                "place an order",
                body.replace("never place an order", ""),
                "%s developer_instructions should not encourage placing orders"
                % name,
            )


class TestCodexReadme(unittest.TestCase):
    """Validate the concise Codex setup guide."""

    def test_readme_exists(self):
        self.assertTrue(file_exists(".codex/README.md"))

    def test_readme_documents_setup_and_limits(self):
        text = read_file(".codex/README.md").lower()
        self.assertIn(".codex/config.toml", text)
        self.assertIn(".codex/agents/", text)
        self.assertIn("does not run the runtime hooks", text)

    def test_readme_no_em_dash_or_emoji(self):
        text = read_file(".codex/README.md")
        self.assertEqual(assert_no_em_dash(text), [])
        self.assertEqual(assert_no_emoji(text), [])


if __name__ == "__main__":
    unittest.main()
