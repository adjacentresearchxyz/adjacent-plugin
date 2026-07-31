---
name: market-find
description: Discover a market or index by topic, then fetch its detail and a 24h price series in one shot.
allowed-tools:
  - adjacent-markets/find
  - adjacent-markets/get
  - adjacent-markets/price
  - adjacent-markets-dev/find
  - adjacent-markets-dev/get
  - adjacent-markets-dev/price
argument-hint: "<topic or entity name>, e.g. 'house control' or 'kalshi:<example-market-id>'"
---

# Market find

You are running the find -> get -> price chain for $ARGUMENTS.

Steps:

1. Use the dev MCP server.
2. If $ARGUMENTS contains a colon (`platform:raw`), treat as a market id and
   skip `find` -- go straight to `get(market_id)`.
3. Else, call `find($ARGUMENTS, "market")` first. If exactly one result,
   use that id; if multiple, pick the highest-volume YES/NO per-day market
   in the last 7 days. If a market looks like an event, prefer the most
   liquid child.
4. Chain `get(id)` -> extract: name, type, platform, last price (mid),
   YES ask/bid, volume, expiry, sources/links.
5. Chain `price(id, "24h")` -> extract: open, close, high, low, %-move.
6. Render using `briefings` formatting rules.

Output is a single markdown card (no preamble):

```
# <name>
[type]   [platform]   expires <YYYY-MM-DD>
last (mid): <price>  (bid <bid>  ask <ask>)
24h: open <o>  close <c>  high <h>  low <l>  move <move-1d>%
volume 24h: <v>
```

If `find` returns zero results, emit a single line: `no match: $ARGUMENTS`.
