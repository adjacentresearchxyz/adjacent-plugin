# Adjacent for Cursor

Cursor MCP configuration and project rules.

## Setup

1. Open this repository as a trusted workspace.
2. Approve the servers in `.cursor/mcp.json`.
3. Set `ADJACENT_API_KEY` for realtime data. The dev endpoint works
   without it.

Rules under `.cursor/rules/` cover pricing, charts, writing, and JSON
contracts, including the live news surface and the still-unavailable
index-correlation endpoint. Cursor treats them as guidance,
not runtime hooks.
