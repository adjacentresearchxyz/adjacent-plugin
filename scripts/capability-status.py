#!/usr/bin/env python3
"""Print the current Adjacent integration capability status."""

from __future__ import annotations

import argparse
import importlib.util
import json
import os

from _paths import data_dir


def runtime_probe() -> dict:
    """Lightweight, side-effect-free runtime probes for the JSON payload.

    Uses importlib.util.find_spec so we never import matplotlib (which is
    heavy and pulls a GUI backend) just to ask whether it is installed.
    """
    matplotlib_ok = importlib.util.find_spec("matplotlib") is not None
    return {
        "matplotlib": matplotlib_ok,
        "datawrapper_key": bool(os.environ.get("DATAWRAPPER_API_KEY")),
    }


def charting_line(probe: dict) -> str:
    """Human-readable charting status for the text-mode output."""
    if probe["matplotlib"]:
        return "- charting: matplotlib available"
    return (
        "- charting: matplotlib missing (PNG disabled; CSV still works; "
        "pip install -r requirements.txt)"
    )


def capabilities_path():
    """Resolved per call so ADJACENT_DATA_DIR applies after import."""
    return data_dir() / "capabilities.json"


def render_intro(onboarding: dict) -> str:
    """Render the first-use onboarding block into a relay-ready message.

    Every host that runs capability-status on install (doctor,
    capabilities, capability_status) can print this string verbatim, so
    the intro fires during the natural install-then-verify flow instead
    of relying on a skill that only loads when the model chooses to.
    """
    lines = [onboarding["intro"], "", onboarding["offer"]]
    for item in onboarding.get("schedules", []):
        lines.append(f"- {item}")
    fallback = onboarding.get("fallback")
    if fallback:
        lines.extend(["", fallback])
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", action="store_true")
    parser.add_argument(
        "--intro",
        action="store_true",
        help="Print only the first-use onboarding intro and exit.",
    )
    args = parser.parse_args()
    payload = json.loads(capabilities_path().read_text(encoding="utf-8"))
    onboarding = payload.get("onboarding")
    intro_text = render_intro(onboarding) if onboarding else ""

    if args.intro:
        print(intro_text)
        return 0

    probe = runtime_probe()

    if args.json:
        out = dict(payload)
        if intro_text:
            out["intro_text"] = intro_text
        out["runtime"] = probe
        print(json.dumps(out, indent=2))
        return 0

    if intro_text:
        print(intro_text)
        print()
    for name, capability in payload["capabilities"].items():
        print(
            f"- {name}: API {capability['api_status']}, "
            f"plugin {capability['plugin_status']}"
        )
    print(charting_line(probe))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
