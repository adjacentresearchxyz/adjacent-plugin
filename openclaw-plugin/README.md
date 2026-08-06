# Adjacent for OpenClaw

Prediction-market workflows that execute and return results: briefs,
tradable snapshots, and chart artifacts. Every tool runs the work and
returns structured data plus artifact paths.

## Install

```bash
openclaw plugins install ./openclaw-plugin
openclaw plugins inspect adjacent-markets --runtime --json
```

The package bundles the shared Python core, the Adjacent skills, and the
catalogs, so a clean install needs no repo checkout, no skill copying,
and no path configuration. It requires `python3` (3.11+) on PATH and
nothing from PyPI: the core is standard-library only.

Start with `adjacent_doctor`. It reports the Python runtime, the bundled
core, the data tier, Datawrapper config, and local index data, with a
remedy for anything degraded.

## Tools

| Tool | Does | Returns |
| --- | --- | --- |
| `adjacent_doctor` | checks this install | per-check status and remedies |
| `adjacent_brief` | daily / index brief | movers, thresholds, brief text |
| `adjacent_snapshot` | tradable snapshot | normalized mid-quote rows, CSV path |
| `adjacent_chart` | chart from live data | CSV path, PNG path, chart id; supports overlays |
| `adjacent_movers` | threshold scan | sorted movers |
| `adjacent_capabilities` | live data surfaces | live and unavailable lists |

Two example prompts for a fresh install:

- "Run the Adjacent daily brief and show me anything that moved."
- "Build a 7d chart for kalshi:SENATETX-26-R."
- "Overlay the RED and BLUE indices over 30 days and rebase them to 100."

## Data tier and artifacts

Without `ADJACENT_API_KEY` the tools use the public 15-min-delayed tier,
which is enough for every read-only workflow here. Set the key (or the
`apiKey` config value) for realtime.

Artifacts are written to `ADJACENT_STATE_DIR`, defaulting to `.adjacent`
in the working directory, never inside the install. Charts always
produce a CSV. The PNG needs matplotlib and publishing needs
`DATAWRAPPER_API_KEY`; both report a reason and a remedy when skipped.

To enable PNGs, install matplotlib in the runtime used by the plugin:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install matplotlib
export ADJACENT_PYTHON="$PWD/.venv/bin/python"
```

The plugin reports this command when PNG rendering is requested without
matplotlib. It does not install packages silently.

## Safety

The plugin is read-only and never places an order. Direct-index execution is
not exposed through this package.
Scripts run from that allowlist with an argv array and the shell
disabled; no tool builds a command string.

All price math is mid-quote: `mid = (bid + ask) / 2`. Rows record
`mid_source` so downstream tracking math knows whether a real spread was
available. Percentages use `%`, never `pp`.

## Develop

```bash
cd openclaw-plugin
npm install
npm run build
npm run bundle
npm run plugin:validate
```

```bash
python3 -m pytest tests/openclaw -q
python3 -m unittest tests.openclaw.test_openclaw -v
```

`tests/openclaw/test_clean_install.py` is the acid test: it packs the
tarball, unpacks it away from the repo, and runs the bundled core with
every ADJACENT_ variable stripped.

`npm run bundle` refreshes the bundled core from the repo. `prepack`
runs the build and the bundle, so `npm pack` and `npm publish` always
ship a current copy.
