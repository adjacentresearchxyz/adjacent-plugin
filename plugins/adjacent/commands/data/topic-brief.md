---
name: topic-brief
description: Topic update - live news bullets, short take, related markets with mid quotes, and branded charts.
allowed-tools:
  - Bash
  - Read
  - adjacent-markets/find
  - adjacent-markets/get
  - adjacent-markets/price
  - adjacent-markets-dev/find
  - adjacent-markets-dev/get
  - adjacent-markets-dev/price
argument-hint: "<topic>, e.g. 'washington football'  [--chart] [--png]"
---

# Topic brief

Load the `adjacent-topic-brief` skill, then run the topic update for
$ARGUMENTS.

Preferred path:

```bash
python3 scripts/topic-brief.py $ARGUMENTS --chart --png
```

If the user omitted chart flags, still default to charts when they asked
for "with charts" or any topic brief. Always pass --chart --png.
Never ship Charts: (none); if the orchestrator has no chartable series,
pick the substantive market and chart it manually per the skill.

Then format stdout JSON into the skill template:

1. News bullets (title, source, date)
2. Short take grounded in the mids (no invention)
3. Markets with mid quotes and full ids
4. Chart CSV/PNG paths when present

Rules:

- Mid-quote only
- Full news and market ids (never truncate UUIDs)
- Adjacent-branded charts only
- Read-only; no orders
