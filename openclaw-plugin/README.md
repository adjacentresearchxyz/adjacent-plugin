# Adjacent for OpenClaw

Read-only tools for market discovery, mid-quote pricing, and mover
thresholds. `adjacent_capabilities` reports live surfaces (including
news) and marks index correlation unavailable until its endpoint is
live.

## Install

```bash
openclaw plugins install ./openclaw-plugin
openclaw plugins inspect adjacent-markets --runtime --json
```

## Develop

```bash
cd openclaw-plugin
npm install
npm run build
npm run plugin:validate
```

```bash
python3 -m unittest tests.openclaw.test_openclaw -v
```

Set `ADJACENT_API_KEY` for realtime data. The plugin is read-only and
never places an order.
