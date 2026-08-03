#!/usr/bin/env python3
"""Print the current Adjacent integration capability status."""

from __future__ import annotations

import argparse
import json

from _paths import data_dir


CAPABILITIES = data_dir() / "capabilities.json"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    payload = json.loads(CAPABILITIES.read_text(encoding="utf-8"))
    if args.json:
        print(json.dumps(payload, indent=2))
        return 0
    for name, capability in payload["capabilities"].items():
        print(
            f"- {name}: API {capability['api_status']}, "
            f"plugin {capability['plugin_status']}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
