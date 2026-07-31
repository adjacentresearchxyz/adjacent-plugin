---
name: ask
description: Free-form Q&A against the Adjacent MCP. Routes the question through find -> get -> price and returns a structured market card; falls back to a structured explanation when no market matches.
allowed-tools:
  - adjacent-markets/find
  - adjacent-markets/get
  - adjacent-markets/price
  - adjacent-markets-dev/find
  - adjacent-markets-dev/get
  - adjacent-markets-dev/price
  - Read
argument-hint: "<free-form question or entity, e.g. 'house control' or 'kalshi:<example-market-id>'>"
---

# Ask

Route `$ARGUMENTS` to the `ask-assistant` sub-agent
(`agents/ask-assistant.md`). If the host cannot spawn the agent, perform
the exact same workflow in-line.

## Workflow

1. Treat `$ARGUMENTS` as the topic. If it contains `:` (e.g.
   `kalshi:<example-market-id>`), it is already a market id - skip step 2.
2. Else call `adjacent-markets-dev/find(topic=$ARGUMENTS)`. If multiple
   matches, sort by 24h volume descending and cap at 5; if a parent
   event matches, prefer the most liquid child.
3. For each id, chain `get(id)` for static fields, then
   `price(id, "24h")` for the move. Pull `price(id, "7d")` only when
   `|move_1d| >= 2%` or when the topic suggests a longer horizon.
4. Render per the `briefings` skill (mid-quote pricing, `%` not `pp`,
   ASCII bullets, no em-dash, no emoji).

## Output shapes

Market card (1 per relevant id):

```
# <name>
[type]   [platform]   expires <YYYY-MM-DD>
last (mid): <price>  (bid <bid>  ask <ask>)
24h: open <o>  close <c>  high <h>  low <l>  move <move-1d>%
volume 24h: <v>
```

Meta / explanation (no market match, or question about the MCP itself):

```
<one sentence framing>

- see: <skill or command name> for <purpose>
- see: <skill or command name> for <purpose>
```

If `find` returns zero matches, emit exactly `no match: $ARGUMENTS` and
stop. Do not invent market data and do not retry against unrelated
topics.
