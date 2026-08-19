---
name: using-adjacent
description: Use when starting any conversation that mentions Adjacent, prediction markets, indices, movers, briefs, charts, news-to-price, or rebalancing.
version: 1.0.0
category: productivity
---

# Using Adjacent

Check Adjacent skills before discovery, pricing, charts, briefs, or
orders. If a skill might apply, load it. Do not improvise the
workflow from memory.

Announce "Using [skill] to [purpose]" and follow that skill. For
routing, load `adjacent-workflows`.

## The rule

**Load the matching Adjacent skill BEFORE any response or action** -
including clarifying questions, MCP calls, and script runs. If it
turns out wrong, you do not have to keep it.

User instructions (`AGENTS.md`, direct requests) take precedence.
Skip a skill only when the human partner has explicitly told you to.

## Evidence before claims

No mid, move, tracking error, or P&L figure without a fresh `price`
MCP call or producer script in this turn. Typed failures
(`NO_PRICE_AT_AS_OF`, `RATE_LIMITED`, `SEARCH_NO_MATCH`) are answers.
Never invent an endpoint response.

## Defaults

- Mid quotes for every price, return, move, and tracking figure.
- Dev MCP unless `ADJACENT_API_KEY` is set and the task publishes.
- Live slug discovery. Never assume a baked-in index id.
- Charts load `adjacent-chart-style` before render or publish.
- Trading is fail-closed: no orders without an explicit non-dry-run
  instruction and a catalog whose placeholders are off.

## When not to spray every skill

- Pure writing-convention edits: `briefings` is enough.
- A slash command already names the workflow: still load that
  workflow's skill, not the whole set.
- After `using-adjacent` has run once this session, do not re-inject
  it. Load the next matching skill instead.

## Red flags

| Thought | Reality |
| --- | --- |
| "I know the mid-quote rule" | Load the skill. Conventions drift. |
| "Just one price call" | Skill check comes first. |
| "The user named a ticker, I can guess the slug" | Discover live. Never invent ids. |
| "No data, I will approximate" | Say there is no data and stop. |
| "Rebalance is obviously wanted" | Fail closed. Dry-run unless told otherwise. |
