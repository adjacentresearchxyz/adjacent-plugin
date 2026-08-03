# Adjacent prediction-market plugins

Cross-platform integrations for the
[Adjacent MCP](https://docs.adjacent.markets/explore/mcp).

## Features

- Market discovery, prices, and Q&A.
- Mover scans and daily briefs.
- Adjacent-branded charts, including candles-backed charts.
- Portfolio tracking and rebalance plans.
- Live news-to-price ranking and similar-market hedge discovery.
- Docs Q&A, data exports, and public snapshot health checks.
- Mid-quote math and fail-closed trading.

The `news/latest` surface is live. Index correlation is not live yet;
its regime analysis accepts supplied JSON only.

## Packages

Each adapter is self-contained in its package directory. Shared
`scripts/` and `data/` stay host-neutral, so every package reads the
same code paths and catalogs.

| Host | Package | Setup |
| --- | --- | --- |
| Claude Code | `plugins/adjacent` | [README](plugins/adjacent/README.md) |
| Hermes | `.hermes` | [README](.hermes/README.md) |
| Codex | `.codex` | [README](.codex/README.md) |
| Cursor | `.cursor` | [README](.cursor/README.md) |
| OpenClaw | `openclaw-plugin` | [README](openclaw-plugin/README.md) |

### Claude Code

```
/plugin marketplace add adjacentresearchxyz/adjacent-plugin
/plugin install adjacent@adjacent-plugin
```

Prefix every command with `adjacent:` (e.g. `/adjacent:briefing/morning`).

## Environment

- `ADJACENT_API_KEY`: realtime data. Optional for delayed data.
- `ADJACENT_PLUGIN_ROOT`: install root containing `scripts/` and `data/`.
- `ADJACENT_PLUGIN_SCRIPTS`: explicit scripts-directory override when the
  host package is installed outside the monorepo.
- `ADJACENT_DATA_DIR`: optional shared data-directory override.
- `ADJACENT_STATE_DIR`: optional logs and chart-output directory.
- `DATAWRAPPER_API_KEY`: chart publishing.
- `KALSHI_API_KEY`, `KALSHI_PASSPHRASE`, `KALSHI_RSA_KEY_PATH`: trading.

Never commit secrets.

## Validate

```bash
python3 scripts/validate-plugin-packages.py
python3 -m pytest tests -q
```
