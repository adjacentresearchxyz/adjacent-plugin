# Adjacent for droid

## Install

```bash
droid plugin marketplace add https://github.com/adjacentresearchxyz/adjacent-plugin
droid plugin install adjacent@adjacent-plugin --scope user
```

Or browse and install from `/plugins` inside a droid session.

## What ships

| Component | Path | Invocation |
| --- | --- | --- |
| Skills | `skills/<name>/SKILL.md` | model-triggered |
| Commands | `commands/<name>.md` | `/<name>` |
| Droids | `droids/<name>.md` | task subagent |
| Hooks | `hooks/hooks.json` | lifecycle events |
| MCP servers | `mcp.json` | `adjacent-markets`, `adjacent-markets-dev` |

Commands are flat, with the group in the name: `/daily`,
`/briefing-morning`, `/data-ask`, `/data-index-movers`,
`/data-news-latest`, `/charts-datawrapper-publish`,
`/trading-portfolio-snapshot`, `/trading-rebalance-index`, and the rest
of the `/data-*` set.

Droids: `coordinator`, `index-monitor`, `data-monitor`,
`briefing-writer`, `ask-assistant`. All read-only; none place orders.

Hooks map to this host's tool ids: `conventions` and `secret-redactor`
and `chart-style` run on `Create` / `Edit` / `ApplyPatch` and `Execute`;
`mover-logger` runs after any `price` MCP call.

## Data tier

The shipped `mcp.json` points at the public 15-min-delayed tier. Droid
does not expand `${NAME}` inside an MCP `url` (only inside `headers` and
stdio `env`), and the Adjacent MCP authenticates through an `apiKey`
query param, so a key cannot be injected from the environment here.

For the realtime tier, register the server yourself with the key in the
URL:

```bash
droid mcp add --transport http adjacent-markets \
  "https://mcp.adjacent.markets/mcp?apiKey=$ADJACENT_API_KEY"
```

That command expands the key in your shell before droid stores it. Keep
the resulting entry out of version control.

## Environment

- `ADJACENT_API_KEY` - realtime tier. Optional; delayed data works
  without it.
- `ADJACENT_PLUGIN_ROOT` / `ADJACENT_PLUGIN_SCRIPTS` - install root and
  scripts directory when the package runs outside the monorepo.
- `ADJACENT_STATE_DIR` - logs and chart output.
- `DATAWRAPPER_API_KEY` - chart publishing.
- `KALSHI_API_KEY`, `KALSHI_PASSPHRASE`, `KALSHI_RSA_KEY_PATH` - live
  rebalance orders only.

Never commit secrets.
