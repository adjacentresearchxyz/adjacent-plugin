---
name: adjacent-topic-brief
description: >
  Use when the user asks about a person, topic, or event and wants news
  and prediction markets (e.g. "tell me about trump", "updates on
  washington football", "what's going on with X", "news and markets for
  Y", "topic brief Z"). Pulls news bullets, a short take, related markets
  with mid quotes, and at least one Adjacent-branded chart PNG via
  scripts/topic-brief.py.
version: 1.1.0
category: research
---

# Adjacent topic brief

The common interactive loop. User says something like "updates on
washington football", "tell me about trump", or "topic brief: house
control". Respond with:

1. Bulleted news
2. A short take (1-3 sentences)
3. Related markets with mid quotes
4. At least one Adjacent-branded chart PNG (mandatory)

## When to use

- "tell me about X"
- "updates on X"
- "what's going on with X"
- "news and markets for X"
- "topic brief X"
- Slash command `/data/topic-brief` (flat host package: `data-topic-brief`)

Do not use this for pure market discovery (use market-find) or the
morning movers brief (use `/briefing/morning`).

## Steps

1. Run the orchestrator (preferred). Always request charts + PNG:

```bash
python3 scripts/topic-brief.py "<topic>" --chart --png
```

Flags:

- `--news-limit N` (default 5)
- `--market-limit N` (default 5 after ranking; script over-fetches 3x,
  at least 15 candidates, then ranks)
- `--timeframe 7d` (default)
- `--chart` build candle CSVs for chartable markets
- `--png` render Adjacent-branded PNGs (implies `--chart`)
- `--prod` use realtime tier when `ADJACENT_API_KEY` is set

2. Or chain by hand:

- `find(query=<topic>, type=news)` then `get(id, type=news)` for detail
- `find(query=<topic>, type=market)` for related markets (pull a wide
  set; do not stop at the first five thin hits)
- `price(id, type=market, timeframe=7d)` for each candidate (mid only)
- Rank: chartable traded series first, then liquid books, then
  find-quote fallbacks
- `scripts/chart-build.py --id <market_id> --type market --timeframe 7d --png`
  for chartable markets only

3. Format the reply per the template below. Never invent headlines or
   mids. If news or markets is empty, say so and continue with what
   exists.

## Mandatory chart rule

Every topic brief ships **at least one branded chart PNG**, always.
Never deliver `Charts: (none)` or an empty charts section.

- Prefer charts returned by the orchestrator (`charts[].png` with
  `ok: true`).
- If the orchestrator returns only thin / no-history markets
  (`chartable: false`, `quote_source: find_probability`, or a warning
  that nothing is chartable), **manually** pick the substantive market
  (highest volume / open interest, or the market the news most clearly
  moves), fetch its 7d mid history, and render with
  `scripts/chart-build.py` + `adjacent-chart-style`.
- If PNG fails for missing matplotlib, keep the CSV, surface the install
  remedy, and still attempt the chart path - do not silently drop charts.
- Charts must use Adjacent branding. Never a stock library default.

## Discovery rules

- News discovery often works on prod when dev returns empty hits. The
  script prefers prod for news find, then falls back. Prefer full news
  UUIDs from MCP; never paste a truncated id into
  `https://api.adjacent.markets/api/v1/news/<id>` (404s).
- Markets use the selected tier (dev by default). The script over-fetches
  candidates and ranks them; carry volume / open-interest when present.
- All prices are mid-quote. Report `mid` as percent when it is a
  probability-style market (`0.565` -> `56.5%`).
- Prefer markets with real volume / open interest when ranking a take.
  Call out thin or unquoted books.
- When candle history is empty, the script may fall back to the find
  hit `probability` as mid and label `quote_source: find_probability`
  with `chartable: false`. Say so in the take; do not pretend it is a
  traded mid series, and do not chart it - pick a chartable market
  instead (mandatory chart rule).

## Output template

```
YYYY-MM-DD HH:MM ET topic brief: <topic>

News
- <headline> (<source>, <YYYY-MM-DD>)
- ...

Take
- <1-3 sentences: what the news implies for the markets, mid-quoted>

Markets (mid)
- <name>: <mid%>  id=<platform:raw>  [volume note if thin]
- ...

Charts
- <png path>  (<market name or id>)
```

ASCII `-` bullets only. `%` never `pp`. No em-dash. No emoji.

## Limits

- Read-only. Never place orders.
- Do not publish or tweet unless the user asks.
- Do not fabricate article ids, mids, or volume.
- Never ship a topic brief without at least one chart attempt (PNG
  preferred; CSV + matplotlib remedy if PNG cannot render).
