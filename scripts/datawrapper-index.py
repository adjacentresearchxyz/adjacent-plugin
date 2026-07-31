#!/usr/bin/env python3
"""datawrapper-index.py - rebuild a per-index tracking chart.

1. Run scripts/chart-index.py --index <slug> to build the %-return CSV.
2. Pipe CSV into scripts/datawrapper-publish.py <chart-id>.

Chart id and index slug are provided positionally/via flags; no
hardcoded chart references.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--index", required=True)
    ap.add_argument("--chart-id", required=True)
    ap.add_argument("--no-publish", action="store_true")
    args = ap.parse_args()
    here = Path(__file__).resolve().parent
    csv_proc = subprocess.run(
        [sys.executable, str(here / "chart-index.py"), "--index", args.index],
        capture_output=True,
        text=True,
    )
    if csv_proc.returncode != 0:
        sys.stderr.write(csv_proc.stderr)
        return csv_proc.returncode
    pub_args = [sys.executable, str(here / "datawrapper-publish.py"), args.chart_id]
    if args.no_publish:
        pub_args.append("--no-publish")
    pub = subprocess.run(pub_args, input=csv_proc.stdout, capture_output=True, text=True)
    sys.stdout.write(pub.stdout)
    sys.stderr.write(pub.stderr)
    return pub.returncode


if __name__ == "__main__":
    sys.exit(main())
