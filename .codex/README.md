# Adjacent for Codex

Codex MCP configuration and read-only role agents.

## Setup

1. Use `.codex/config.toml` as the project config or merge its
   `[mcp_servers.*]` and `[agents.*]` sections into your config.
2. Set `ADJACENT_API_KEY` for realtime data. The dev endpoint works
   without it.
3. Select a role from `.codex/agents/`.

## Included roles

- `coordinator`: daily workflow coordinator.
- `index-monitor`: mover scans.
- `data-monitor`: similar markets, candles, snapshots, exports, docs, and news.
- `briefing-writer`: daily briefs.
- `ask-assistant`: market Q&A.

Codex does not run the runtime hooks or slash commands included in
other packages. Mid-quote pricing and fail-closed trading still apply.
