"""Tests for the Cursor adapter (.cursor/).

Self-contained unittest, no third-party dependencies.
Run: python -m unittest tests.adapters.test_cursor -v
"""

import json
import os
import unittest

from tests.adapters._helpers import (
    CURSOR_DIR,
    EXPECTED_MDC_RULES,
    MCP_DEV_URL,
    MCP_PROD_URL,
    assert_no_em_dash,
    assert_no_emoji,
    file_exists,
    parse_frontmatter,
    read_file,
)


class TestCursorMcpJson(unittest.TestCase):
    """Validate .cursor/mcp.json structure and endpoints."""

    def test_mcp_json_exists(self):
        self.assertTrue(file_exists(".cursor/mcp.json"))

    def test_mcp_json_is_valid_json(self):
        data = json.loads(read_file(".cursor/mcp.json"))
        self.assertIsInstance(data, dict)

    def test_mcp_servers_registered(self):
        data = json.loads(read_file(".cursor/mcp.json"))
        servers = data.get("mcpServers", {})
        self.assertIn("adjacent-markets", servers)
        self.assertIn("adjacent-markets-dev", servers)

    def test_mcp_urls_match_canonical(self):
        data = json.loads(read_file(".cursor/mcp.json"))
        servers = data["mcpServers"]
        self.assertEqual(servers["adjacent-markets"]["url"], MCP_PROD_URL)
        self.assertEqual(servers["adjacent-markets-dev"]["url"], MCP_DEV_URL)

    def test_mcp_headers_present(self):
        data = json.loads(read_file(".cursor/mcp.json"))
        for name in ("adjacent-markets", "adjacent-markets-dev"):
            with self.subTest(server=name):
                self.assertEqual(servers := data["mcpServers"][name].get("headers"), {})

    def test_mcp_json_no_em_dash_or_emoji(self):
        text = read_file(".cursor/mcp.json")
        self.assertEqual(assert_no_em_dash(text), [])
        self.assertEqual(assert_no_emoji(text), [])


class TestCursorMdcRules(unittest.TestCase):
    """Validate the .mdc rule files."""

    def test_expected_mdc_rules_exist(self):
        for rule in EXPECTED_MDC_RULES:
            path = ".cursor/rules/%s" % rule
            self.assertTrue(file_exists(path), "missing rule: %s" % path)

    def test_rules_dir_has_no_extra_mdc(self):
        rules_dir = os.path.join(CURSOR_DIR, "rules")
        mdc_files = sorted(f for f in os.listdir(rules_dir) if f.endswith(".mdc"))
        expected = sorted(EXPECTED_MDC_RULES)
        self.assertEqual(mdc_files, expected, "unexpected .mdc files")

    def test_mdc_frontmatter_fields(self):
        for rule in EXPECTED_MDC_RULES:
            with self.subTest(rule=rule):
                fm = parse_frontmatter(read_file(".cursor/rules/%s" % rule))
            self.assertTrue(fm.get("description"), "%s missing description" % rule)
            # globs must be a list
            globs = fm.get("globs")
            self.assertIsInstance(globs, list, "%s globs not a list" % rule)
            # alwaysApply must be a bool
            self.assertIn(
                fm.get("alwaysApply"),
                (True, False),
                "%s alwaysApply not boolean" % rule,
            )

    def test_conventions_rule_always_applies(self):
        fm = parse_frontmatter(
            read_file(".cursor/rules/adjacent-conventions.mdc")
        )
        self.assertTrue(fm.get("alwaysApply"), "conventions rule must alwaysApply")

    def test_json_rule_exists_and_covers_schema(self):
        fm = parse_frontmatter(read_file(".cursor/rules/adjacent-json.mdc"))
        body = fm.get("_body", "").lower()
        self.assertIn("mcp.json", body)
        self.assertIn("position file schema", body)
        self.assertIn("format_version", body)

    def test_tokens_rule_references_design_tokens(self):
        fm = parse_frontmatter(read_file(".cursor/rules/adjacent-tokens.mdc"))
        body = fm.get("_body", "")
        # Must reference at least a few design tokens by name.
        for token in ("--comp-green", "--comp-canvas", "--font-main", "--font-mono"):
            self.assertIn(token, body, "tokens rule missing %s" % token)

    def test_pricing_rule_uses_mid_quote(self):
        fm = parse_frontmatter(read_file(".cursor/rules/adjacent-pricing.mdc"))
        body = fm.get("_body", "").lower()
        self.assertIn("mid", body)
        self.assertIn("pp", body)  # mentions the ban on pp

    def test_mdc_rules_no_em_dash_or_emoji(self):
        for rule in EXPECTED_MDC_RULES:
            with self.subTest(rule=rule):
                text = read_file(".cursor/rules/%s" % rule)
            self.assertEqual(assert_no_em_dash(text), [], "%s has em-dash" % rule)
            self.assertEqual(assert_no_emoji(text), [], "%s has emoji" % rule)


class TestCursorReadme(unittest.TestCase):
    """Validate the concise Cursor setup guide."""

    def test_readme_exists(self):
        self.assertTrue(file_exists(".cursor/README.md"))

    def test_readme_documents_setup_and_limits(self):
        text = read_file(".cursor/README.md").lower()
        self.assertIn(".cursor/mcp.json", text)
        self.assertIn(".cursor/rules/", text)
        self.assertIn("not runtime hooks", text)

    def test_readme_no_em_dash_or_emoji(self):
        text = read_file(".cursor/README.md")
        self.assertEqual(assert_no_em_dash(text), [])
        self.assertEqual(assert_no_emoji(text), [])


if __name__ == "__main__":
    unittest.main()
