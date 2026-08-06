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
import csv
import json
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

from _mcp import McpError, fetch
from _paths import data_dir, scripts_dir, state_dir


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
    entity_ids: list[str],
    entity_type: str,
    timeframe: str,
    tier: str,
    api_key: str | None,
    output: Path,
    rebase: bool,
) -> dict:
    def load_series(entity_id: str) -> tuple[str, list]:
        payload = fetch(
            "price",
            {"id": entity_id, "type": entity_type, "timeframe": timeframe, "raw": True},
            tier=tier,
            api_key=api_key,
        )
        return entity_id, _series_of(payload)

    series_by_id: dict[str, list] = {}
    with ThreadPoolExecutor(max_workers=min(4, max(1, len(entity_ids)))) as executor:
        for entity_id, series in executor.map(load_series, entity_ids):
            if not series:
                return {"ok": False, "error": f"no timeseries returned for {entity_id}"}
            series_by_id[entity_id] = series

    # candles-chart.py intentionally handles one series. Build an overlay
    # here so all series share a timestamp axis and can be rebased together.
    rows_by_ts: dict[str, dict[str, float]] = {}
    for entity_id, series in series_by_id.items():
        values = []
        for row in series:
            if not isinstance(row, dict):
                continue
            ts = row.get("ts") or row.get("timestamp") or row.get("time")
            value = row.get("mid", row.get("close", row.get("value")))
            if ts is not None and value is not None:
                values.append((str(ts), float(value)))
        if not values:
            return {"ok": False, "error": f"no plottable timeseries returned for {entity_id}"}
        if rebase:
            base = values[0][1]
            if base == 0:
                return {"ok": False, "error": f"cannot rebase zero-valued series for {entity_id}"}
            values = [(ts, 100.0 * value / base) for ts, value in values]
        for ts, value in values:
            rows_by_ts.setdefault(ts, {})[entity_id] = value

    with output.open("w", encoding="utf-8", newline="") as handle:
        fieldnames = ["ts", *entity_ids]
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for ts in sorted(rows_by_ts):
            writer.writerow({"ts": ts, **rows_by_ts[ts]})
    return {"ok": True, "points": len(rows_by_ts), "series": len(entity_ids)}


def tracking_csv(index: str, output: Path) -> dict:
    positions = data_dir() / "positions"
    # A clean OpenClaw install has no fills or cached tracking series. Fail
    # before invoking chart-index.py so the caller gets a useful remedy.
    required = [
        positions / f"{index}.last_fill_ts",
        positions / f"{index}.index.series.json",
        positions / f"{index}.portfolio.series.json",
    ]
    missing = [str(path) for path in required if not path.exists()]
    if missing:
        return {
            "ok": False,
            "error": (
                f"tracking data for {index!r} is not installed "
                f"(missing {', '.join(missing)}). "
                "Run a portfolio snapshot and populate the index/portfolio "
                "series, or use the candles source with id=<index>."
            ),
        }
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
        columns: dict[str, list[float | None]] = {}
        with csv_path.open(encoding="utf-8") as handle:
            rows = list(csv.DictReader(handle))
        if not rows:
            return {"ok": False, "error": "CSV held no plottable rows"}
        keys = list(rows[0].keys())
        for key in keys[1:]:
            columns[key] = [
                None if row.get(key) in (None, "") else float(row[key]) for row in rows
            ]
        if not any(any(value is not None for value in values) for values in columns.values()):
            return {"ok": False, "error": "CSV held no plottable rows"}

        fig, ax = adj.figure(headline=headline, deck=deck)
        legend_entries = [
            (label, adj.SERIES[position % len(adj.SERIES)])
            for position, label in enumerate(columns)
        ]
        for (label, color), values in zip(legend_entries, columns.values()):
            xs = [i for i, value in enumerate(values) if value is not None]
            ys = [value for value in values if value is not None]
            ax.plot(xs, ys, color=color, label=label)
        if len(columns) > 1:
            adj.swatch_legend(fig, legend_entries)
        png_path.parent.mkdir(parents=True, exist_ok=True)
        adj.save(fig, str(png_path))
        return {"ok": True, "points": len(rows), "series": len(columns)}
    except ImportError as exc:
        return {
            "ok": False,
            "error": f"matplotlib not installed: {exc}",
            "remedy": (
                "Install it in the Python runtime used by the plugin: "
                "python3 -m pip install matplotlib. "
                "For a clean install, create a virtual environment and set "
                "ADJACENT_PYTHON to its python executable."
            ),
        }
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
    ap.add_argument("--id", action="append", help="market or index id; repeat for overlays")
    ap.add_argument("--ids", help="comma-separated market or index ids for overlays")
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

    ids = list(args.id or [])
    if args.ids:
        ids.extend(part.strip() for part in args.ids.split(",") if part.strip())
    ids = list(dict.fromkeys(ids))
    if args.source == "candles" and not ids:
        ap.error("--id or --ids is required for the candles source")
    if args.source == "tracking" and not args.index:
        ap.error("--index is required for the tracking source")

    api_key = os.environ.get("ADJACENT_API_KEY")
    tier = "prod" if (args.prod and api_key) else "dev"

    out_dir = Path(args.output_dir).expanduser() if args.output_dir else state_dir() / "charts"
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = (args.index or ids[0] or "chart").replace(":", "-").replace("/", "-")
    csv_path = out_dir / f"{stem}.csv"

    if args.source == "candles":
        try:
            built = candles_csv(
                ids, args.type, args.timeframe, tier, api_key, csv_path, args.rebase
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
            if rendered.get("remedy"):
                result["png_remedy"] = rendered["remedy"]

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
