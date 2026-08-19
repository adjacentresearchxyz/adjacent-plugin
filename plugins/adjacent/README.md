# Adjacent for Claude Code

## Install

```text
/plugin marketplace add adjacentresearchxyz/adjacent-plugin
/plugin install adjacent@adjacent-plugin
```

Commands use the `adjacent:` prefix. Set `ADJACENT_API_KEY` for
realtime data. Delayed data works without it.

A SessionStart hook injects the `using-adjacent` skill so routing,
mid-quote math, and fail-closed trading load before the first MCP
call. Skill descriptions are `Use when` triggers, not workflow
summaries.
