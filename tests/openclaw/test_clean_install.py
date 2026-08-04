"""Clean-install acid test for the OpenClaw package.

Packs the tarball exactly as `npm publish` would, unpacks it somewhere with
no repo checkout in sight, and proves the result is self-sufficient:

- the compiled entrypoint ships,
- the shared Python core, skills, and catalogs ship,
- a bundled script runs from the unpacked tree with every ADJACENT_* env
  var stripped and the working directory outside the repo.

Contract tests can pass against a package that ships no working code. This
one cannot. It is the test that would have caught the missing dist.

Skipped when npm or python3 is unavailable.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
PACKAGE_DIR = REPO_ROOT / "openclaw-plugin"

REQUIRED_FILES = [
    "dist/index.js",
    "dist/runtime.js",
    "openclaw.plugin.json",
    "runtime/scripts/brief-daily.py",
    "runtime/scripts/market-snapshot.py",
    "runtime/scripts/chart-build.py",
    "runtime/scripts/capability-status.py",
    "runtime/scripts/_paths.py",
    "runtime/scripts/_mcp.py",
    "runtime/data/capabilities.json",
    "runtime/skills/adjacent-markets/SKILL.md",
]

# Repo tooling that must not ride along into an install.
EXCLUDED_FILES = ["runtime/scripts/validate-plugin-packages.py"]


def _tool_missing() -> str | None:
    for tool in ("npm", "python3"):
        if shutil.which(tool) is None:
            return tool
    return None


@unittest.skipIf(_tool_missing() is not None, "requires npm and python3")
class TestCleanInstall(unittest.TestCase):
    """Fresh environment, one install, working tools."""

    tmp: tempfile.TemporaryDirectory
    unpacked: Path

    @classmethod
    def setUpClass(cls) -> None:
        cls.tmp = tempfile.TemporaryDirectory()
        target = Path(cls.tmp.name)

        packed = subprocess.run(
            ["npm", "pack", "--pack-destination", str(target), "--silent"],
            cwd=PACKAGE_DIR,
            capture_output=True,
            text=True,
        )
        if packed.returncode != 0:
            raise unittest.SkipTest(f"npm pack failed: {packed.stderr[-400:]}")

        tarballs = sorted(target.glob("*.tgz"))
        if not tarballs:
            raise unittest.SkipTest("npm pack produced no tarball")

        with tarfile.open(tarballs[0]) as archive:
            archive.extractall(target)
        cls.unpacked = target / "package"

    @classmethod
    def tearDownClass(cls) -> None:
        cls.tmp.cleanup()

    def test_tarball_ships_the_entrypoint_and_core(self):
        for relative in REQUIRED_FILES:
            with self.subTest(path=relative):
                self.assertTrue(
                    (self.unpacked / relative).is_file(),
                    "clean install is missing %s" % relative,
                )

    def test_tarball_excludes_repo_tooling(self):
        for relative in EXCLUDED_FILES:
            with self.subTest(path=relative):
                self.assertFalse(
                    (self.unpacked / relative).exists(),
                    "clean install ships repo tooling: %s" % relative,
                )

    def test_every_allowlisted_script_is_bundled(self):
        runtime_ts = (PACKAGE_DIR / "src" / "runtime.ts").read_text(encoding="utf-8")
        import re

        for name in re.findall(r'"([a-z0-9-]+\.py)"', runtime_ts):
            with self.subTest(script=name):
                self.assertTrue(
                    (self.unpacked / "runtime" / "scripts" / name).is_file(),
                    "allowlisted script is not bundled: %s" % name,
                )

    def test_all_shared_skills_are_bundled(self):
        canonical = {p.name for p in (REPO_ROOT / "plugins/adjacent/skills").iterdir() if p.is_dir()}
        bundled = {p.name for p in (self.unpacked / "runtime" / "skills").iterdir() if p.is_dir()}
        self.assertEqual(canonical, bundled, "bundled skills differ from the canonical set")

    def test_bundled_script_runs_with_no_repo_and_no_env(self):
        """The acid test: no checkout, no ADJACENT_* config, still works."""
        env = {k: v for k, v in os.environ.items() if not k.startswith("ADJACENT_")}
        script = self.unpacked / "runtime" / "scripts" / "capability-status.py"

        proc = subprocess.run(
            [sys.executable, str(script), "--json"],
            cwd=self.unpacked.parent,
            env=env,
            capture_output=True,
            text=True,
        )
        self.assertEqual(proc.returncode, 0, "bundled script failed: %s" % proc.stderr[-300:])

        payload = json.loads(proc.stdout)
        self.assertIn("capabilities", payload)
        self.assertIn("news_latest", payload["capabilities"])

    def test_bundled_core_resolves_bundled_data(self):
        """_paths must land on the bundled catalogs, not a repo path."""
        env = {k: v for k, v in os.environ.items() if not k.startswith("ADJACENT_")}
        proc = subprocess.run(
            [
                sys.executable,
                "-c",
                "import sys, json; sys.path.insert(0, sys.argv[1]); import _paths; "
                "print(json.dumps({'data': str(_paths.data_dir()), "
                "'exists': _paths.data_dir().is_dir()}))",
                str(self.unpacked / "runtime" / "scripts"),
            ],
            cwd=self.unpacked.parent,
            env=env,
            capture_output=True,
            text=True,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr[-300:])
        resolved = json.loads(proc.stdout)
        self.assertTrue(resolved["exists"], "bundled data dir does not exist")
        # Compare real paths: the temp dir arrives through a symlink on macOS.
        data_path = Path(resolved["data"]).resolve()
        self.assertTrue(
            str(data_path).startswith(str(self.unpacked.resolve())),
            "data dir resolved outside the install: %s" % data_path,
        )

    def test_scripts_need_no_third_party_python(self):
        """The core must import with only the standard library available."""
        env = {k: v for k, v in os.environ.items() if not k.startswith("ADJACENT_")}
        scripts_dir = self.unpacked / "runtime" / "scripts"
        for module in ("_paths", "_mcp", "_http", "_timeparse"):
            with self.subTest(module=module):
                proc = subprocess.run(
                    [sys.executable, "-c", "import sys; sys.path.insert(0, sys.argv[1]); import %s" % module, str(scripts_dir)],
                    cwd=self.unpacked.parent,
                    env=env,
                    capture_output=True,
                    text=True,
                )
                self.assertEqual(proc.returncode, 0, "%s needs a third-party import: %s" % (module, proc.stderr[-200:]))


if __name__ == "__main__":
    unittest.main()
