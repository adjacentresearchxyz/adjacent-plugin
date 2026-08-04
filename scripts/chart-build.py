#!/usr/bin/env python3
"""chart-build.py -- one call from data to chart artifact.

Chains the pieces a host agent would otherwise run by hand: fetch the
series, build the mid-based CSV through the existing transformer, then
optionally render an Adjacent-branded PNG and publish to Datawrapper.

Two sources:

- ``candles`` (default): pulls the raw mid timeseries from the MCP price
  surface, so it works on a clean install with no local data.
- ``tracking``: builds from ``data/tracking/<slug>.json`` through
  chart-index.py, for installs that carry local index data.

The CSV is always produced. The PNG is best-effort: it needs matplotlib,
and its absence is reported rather than raised. Publishing requires
DATAWRAPPER_API_KEY and is skipped without one.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from _mcp import McpError, fetch
from _paths import scripts_dir, state_dir


def _run(argv: list[str], stdin_text: str | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(argv, input=stdin_text, capture_output=True, text=True)


def _series_of(payload):
    """Find the timeseries rows in a raw price payload."""
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        for key in ("candles", "series", "timeseries", "points", "data", "items"):
            rows = payload.get(key)
            if isinstance(rows, list):
                return rows
    return []


def candles_csv(
    entity_id: str,
    entity_type: str,
    timeframe: str,
    tier: str,
    api_key: str | None,
    output: Path,
    rebase: bool,
) -> dict:
    payload = fetch(
        "price",
        {"id": entity_id, "type": entity_type, "timeframe": timeframe, "raw": True},
        tier=tier,
        api_key=api_key,
    )
    series = _series_of(payload)
    if not series:
        return {"ok": False, "error": f"no timeseries returned for {entity_id}"}

    script = scripts_dir() / "candles-chart.py"
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as tmp:
        json.dump(series, tmp)
        tmp_path = tmp.name
    try:
        argv = [sys.executable, str(script), "--input", tmp_path, "--output", str(output)]
        if rebase:
            argv.append("--rebase")
        proc = _run(argv)
    finally:
        os.unlink(tmp_path)

    if proc.returncode != 0:
        return {"ok": False, "error": (proc.stderr.strip().split("\n") or ["candle build failed"])[-1]}
    return {"ok": True, "points": len(series)}


def tracking_csv(index: str, output: Path) -> dict:
    script = scripts_dir() / "chart-index.py"
    proc = _run([sys.executable, str(script), "--index", index, "--output", str(output)])
    if proc.returncode != 0:
        return {"ok": False, "error": (proc.stderr.strip().split("\n") or ["chart build failed"])[-1]}
    return {"ok": True}


def render_png(csv_path: Path, png_path: Path, headline: str, deck: str) -> dict:
    """Render the CSV as an Adjacent-branded chart. Needs matplotlib."""
    sys.path.insert(0, str(scripts_dir()))
    try:
        import adjacent_chart_style as adj
    except ImportError as exc:
        return {"ok": False, "error": f"chart style helper unavailable: {exc}"}

    try:
        import csv as csv_module

        xs: list[str] = []
        ys: list[float] = []
        with csv_path.open(encoding="utf-8") as handle:
            for row in csv_module.DictReader(handle):
                keys = list(row.keys())
                if len(keys) < 2:
                    continue
                value = row[keys[1]]
                if value in (None, ""):
                    continue
                xs.append(row[keys[0]])
                ys.append(float(value))
        if not ys:
            return {"ok": False, "error": "CSV held no plottable rows"}

        fig, ax = adj.figure(headline=headline, deck=deck)
        ax.plot(range(len(ys)), ys, color=adj.PALETTE["ink"])
        png_path.parent.mkdir(parents=True, exist_ok=True)
        adj.save(fig, str(png_path))
        return {"ok": True, "points": len(ys)}
    except ImportError as exc:
        return {"ok": False, "error": f"matplotlib not installed: {exc}"}
    except Exception as exc:  # rendering is best-effort; never fail the CSV
        return {"ok": False, "error": f"render failed: {exc}"}


def publish(csv_path: Path, chart_id: str) -> dict:
    if not os.environ.get("DATAWRAPPER_API_KEY"):
        return {"ok": False, "error": "DATAWRAPPER_API_KEY unset; skipped publishing"}
    script = scripts_dir() / "datawrapper-publish.py"
    proc = _run([sys.executable, str(script), chart_id, "--csv", str(csv_path)])
    if proc.returncode != 0:
        return {"ok": False, "error": (proc.stderr.strip().split("\n") or ["publish failed"])[-1]}
    return {"ok": True, "output": proc.stdout.strip()[:400]}


def main() -> int:
    ap = argparse.ArgumentParser(description="Build a chart artifact end to end.")
    ap.add_argument("--source", choices=["candles", "tracking"], default="candles")
    ap.add_argument("--id", help="market or index id for the candles source")
    ap.add_argument(
        "--type",
        default="market",
        choices=["market", "index", "event", "rate"],
        help="entity type for the candles source (default market)",
    )
    ap.add_argument("--timeframe", default="7d", help="candle timeframe (default 7d)")
    ap.add_argument("--index", help="index slug for the tracking source")
    ap.add_argument("--rebase", action="store_true", help="rebase closes to 100 at the first point")
    ap.add_argument("--output-dir", help="artifact directory (default: state dir charts/)")
    ap.add_argument("--png", action="store_true", help="also render a branded PNG")
    ap.add_argument("--datawrapper-chart-id", help="publish the CSV to this Datawrapper chart")
    ap.add_argument("--prod", action="store_true", help="use the realtime tier (needs a key)")
    args = ap.parse_args()

    if args.source == "candles" and not args.id:
        ap.error("--id is required for the candles source")
    if args.source == "tracking" and not args.index:
        ap.error("--index is required for the tracking source")

    api_key = os.environ.get("ADJACENT_API_KEY")
    tier = "prod" if (args.prod and api_key) else "dev"

    out_dir = Path(args.output_dir).expanduser() if args.output_dir else state_dir() / "charts"
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = (args.index or args.id or "chart").replace(":", "-").replace("/", "-")
    csv_path = out_dir / f"{stem}.csv"

    if args.source == "candles":
        try:
            built = candles_csv(
                args.id, args.type, args.timeframe, tier, api_key, csv_path, args.rebase
            )
        except McpError as exc:
            built = {"ok": False, "error": str(exc)}
    else:
        built = tracking_csv(args.index, csv_path)

    if not built.get("ok"):
        json.dump({"ok": False, "source": args.source, "error": built.get("error")}, sys.stdout, indent=2)
        sys.stdout.write("\n")
        return 1

    result = {
        "format_version": 1,
        "ok": True,
        "as_of": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source": args.source,
        "tier": tier,
        "basis": "mid-quote",
        "artifacts": {"csv": str(csv_path)},
        "points": built.get("points"),
    }

    if args.png:
        png_path = out_dir / f"{stem}.png"
        rendered = render_png(
            csv_path,
            png_path,
            headline=f"{stem} mid quote",
            deck=f"{args.timeframe}, mid-quote basis",
        )
        if rendered.get("ok"):
            result["artifacts"]["png"] = str(png_path)
        else:
            result["png_skipped"] = rendered.get("error")

    if args.datawrapper_chart_id:
        published = publish(csv_path, args.datawrapper_chart_id)
        if published.get("ok"):
            result["artifacts"]["datawrapper"] = args.datawrapper_chart_id
            result["publish_output"] = published.get("output")
        else:
            result["publish_skipped"] = published.get("error")

    json.dump(result, sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
