---
name: morning
description: Build the daily Adjacent briefing from the index-movers scan. One timestamp line + 1 bullet per idea, stdout only, no Twitter publishing.
allowed-tools:
  - adjacent-markets/list
  - adjacent-markets/find
  - adjacent-markets/get
  - adjacent-markets/price
  - adjacent-markets-dev/list
  - adjacent-markets-dev/find
  - adjacent-markets-dev/get
  - adjacent-markets-dev/price
  - Read
argument-hint: "[<slug1>,<slug2>,...] or empty for default watchlist or --quiet"
---

# Morning briefing

Run the daily briefing. Delegates to the `briefing-writer` sub-agent
defined at `agents/briefing-writer.md`. The host (cron or interactive
prompt) decides where the briefing text lands; this command never
publishes, never tweets, never writes files.

## Inputs

- `$ARGUMENTS == "--quiet"` (or contains `quiet`) -> short-circuit. Print
  the timestamp header, emit `briefing-too-quiet`, and exit. No agent
  invocation, no MCP calls.
- `$ARGUMENTS` non-empty and not `--quiet` -> treat as a comma-separated
  slug list. Validate each via `adjacent-markets-dev/find`.
- `$ARGUMENTS` empty -> use the default watchlist from
  `<plugin-root>/data/watchlist.json`.

## Behavior (when not --quiet)

1. Resolve the slug list (default or `$ARGUMENTS`).
2. Pull prices via `adjacent-markets-dev/price(slug, "24h")` and
   `adjacent-markets-dev/price(slug, "7d")` for each slug. Switch to
   `adjacent-markets` (prod) only if `ADJACENT_API_KEY` is set.
3. Apply 1.5% (1D) and 4% (7D) thresholds from
   `adjacent-rate-movers` / `data/index-movers`.
4. Forward the resolved movers to `briefing-writer`.
5. `briefing-writer` formats and prints the briefing per
   `skills/briefings/SKILL.md`.

## Output shape

```
YYYY-MM-DD HH:MM ET briefing
- <slug>: 1d <move>%, 7d <move>% <one-line reason>
```

If fewer than 3 movers clear the threshold, the agent emits a final line
`briefing-too-quiet` and the briefing is empty between the timestamp and
that line. The `--quiet` short-circuit produces the same final line
without invoking the agent.
