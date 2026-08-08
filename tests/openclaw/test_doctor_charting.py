"""Static contract test for the charting check surfaced by adjacent_doctor.

Asserts that openclaw-plugin/src/index.ts declares a "charting" check in
the adjacent_doctor execute block that references matplotlib and a
remedy mentioning requirements.txt. Self-contained: no Node.js, npm, or
OpenClaw CLI required. Follows the _read/_PLUGIN_ROOT pattern from
tests/openclaw/test_openclaw.py.

Run: python3 -m pytest tests/openclaw/test_doctor_charting.py -q
"""

from __future__ import annotations

import os
import unittest


# Resolve the openclaw-plugin root from this file's location:
#   tests/openclaw/test_doctor_charting.py -> openclaw-plugin is two
#   parents up then into openclaw-plugin/.
_PLUGIN_ROOT = os.path.normpath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")
)
OPENCLAW_DIR = os.path.join(_PLUGIN_ROOT, "openclaw-plugin")


def _read(rel_path: str) -> str:
    full = os.path.join(OPENCLAW_DIR, rel_path)
    with open(full, "r", encoding="utf-8") as fh:
        return fh.read()


class TestDoctorCharting(unittest.TestCase):
    """adjacent_doctor must surface a charting check for matplotlib."""

    def test_index_ts_declares_charting_check(self):
        text = _read("src/index.ts")
        # The doctor execute block must push a check named "charting".
        self.assertIn(
            'name: "charting"',
            text,
            "adjacent_doctor must push a charting check",
        )

    def test_charting_check_reads_runtime_matplotlib(self):
        text = _read("src/index.ts")
        # The parsed type must include the runtime probe from the shared
        # core capability-status payload.
        self.assertIn("runtime?", text)
        self.assertIn("matplotlib", text)
        # The doctor must derive the charting status from the runtime probe.
        self.assertIn("runtime?.matplotlib", text)

    def test_charting_check_has_warn_status_when_missing(self):
        text = _read("src/index.ts")
        # When matplotlib is missing the check is a warn, not a fail, so a
        # clean install is still "ready" (CSV charts still work).
        self.assertIn('"charting"', text)
        self.assertIn('"warn"', text)

    def test_charting_remedy_mentions_requirements(self):
        text = _read("src/index.ts")
        # The remedy for a missing matplotlib must point at requirements.txt
        # so the user knows how to enable branded PNG charts.
        self.assertIn("requirements.txt", text)
        self.assertIn("PNG", text)

    def test_charting_check_detail_mentions_matplotlib(self):
        text = _read("src/index.ts")
        # The detail line must name matplotlib so the doctor report is clear.
        # Both the ok and warn branches reference matplotlib.
        self.assertGreaterEqual(
            text.count("matplotlib"),
            2,
            "charting check must reference matplotlib in status and detail",
        )


if __name__ == "__main__":
    unittest.main()
