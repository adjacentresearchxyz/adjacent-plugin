# Adjacent prediction-market plugins

Cross-platform integrations for the
[Adjacent MCP](https://docs.adjacent.markets/explore/mcp).

## Features

- Market discovery and prices
- Mover scans and daily briefs
- Charts
- Portfolio tracking and rebalance plans
- Live news-to-price ranking and similar-market discovery

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

### Install

```
/plugin marketplace add adjacentresearchxyz/adjacent-plugin
/plugin install adjacent@adjacent-plugin
```

Prefix every command with `adjacent:` (e.g. `/adjacent:briefing/morning`).
