---
name: adjacent-markets
description: Adjacent index monitoring - mid-quote pricing convention, SMA smoothing, dev vs prod MCP hygiene, SPX cross-reference, and first-use onboarding intro.
version: 1.2.1
category: research
allowed-tools:
  - adjacent-markets/list
  - adjacent-markets/find
  - adjacent-markets/get
  - adjacent-markets/price
  - adjacent-markets-dev/list
  - adjacent-markets-dev/find
  - adjacent-markets-dev/get
  - adjacent-markets-dev/price
  - Bash
---

# Adjacent markets

The research-side conventions for monitoring Adjacent indices. This
skill collects the three findings that take the longest to discover
into one place, plus the first-use onboarding intro.

## First-use onboarding

The intro is shipped as data, not free text: it lives in
`data/capabilities.json` under `onboarding` and is rendered by
`scripts/capability-status.py`. Every install-time verification path
carries it, so you never compose it by hand:

- `capability-status.py --json` returns an `intro_text` field.
- `capability-status.py --intro` prints only the intro.
- The doctor tool returns `intro` (plus `relay_intro`) on a healthy
  install; the capabilities tool returns `intro`.

When you verify or first exercise the install (any of the checks above,
or the server responds to a list/find/get/price call on the user's
first conversation), relay that `intro`/`intro_text` to the user
verbatim BEFORE the technical summary. Do not paraphrase it and do not
lead with the doctor report - the intro comes first.

Only show the intro once per session or when the user explicitly asks
what the plugin can do. Do not repeat it on every turn.

## 1. Mid-quote pricing (the most-confirmed finding)

Always track at mid. Ask or bid makes tracking error look worse than it
is. The `price` MCP returns `bid`, `ask`, `mid`. Use `mid` for every
return, move, and tracking computation.

Bad: `move = (close_ask - open_ask) / open_ask`
Good: `move = (close_mid - open_mid) / open_mid`

## 2. SMA smoothing for stability

Wherever you compute a "level" for an index over time, prefer SMA-7
over the raw close. Daily raw prints include a lot of single-day noise
that fights the eye. SMA-7 still moves the same day-over-day but
smooths the chart. The Adjacent MCP `price(raw: true)` returns the
underlying daily series; compute SMA yourself.

## 3. Dev MCP for new workflows

When you prototype a workflow, use `adjacent-markets-dev`. Promote to
prod (`adjacent-markets`) only when:

- the workflow needs realtime quality (sub-minute latency)
- the workflow publishes to charts (no tolerance for staleness)
- the workflow is being demoed to a paying user

Default everything else to dev.

## Move thresholds

See the `adjacent-index-movers` skill for the canonical formulas and
threshold table.

## News correlation

The live `news/latest` endpoint is available. Pull it with
`scripts/news-latest.py` (or the `list(type=news)` MCP tool), then use
`adjacent-news-correlation` to rank headlines against mid moves.
Supplied article JSON is still accepted for backfill.

## SPX cross-reference

The live correlation endpoint is unavailable. Use
`scripts/correlation-regime.py` only with supplied observations.
