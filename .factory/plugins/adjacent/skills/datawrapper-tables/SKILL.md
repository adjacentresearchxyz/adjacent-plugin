---
name: datawrapper-tables
description: CSV to Datawrapper API to embed-link workflow with styling conventions. Drives the /charts/datawrapper-publish slash command and the datawrapper-* scripts in scripts/.
version: 1.1.0
category: data-science
allowed-tools:
  - Bash
---

# Datawrapper tables

The repeatable workflow for shipping a CSV as a Datawrapper chart.

## Pipeline (4 stages)

1. Compose CSV in memory (or write to a temp path).
2. POST CSV to Datawrapper (`POST /api/charts/<id>/data`).
3. Update chart metadata (`PATCH /api/charts/<id>` - title, source,
   intro, byline, type).
4. Publish (`POST /api/charts/<id>/publish`). Embargoed until publish.

## Auth header

```
Authorization: Bearer <DATAWRAPPER_API_KEY>
```

Key from `datawrapper.de/account`. Never log it.

## Scripts

| Script | Purpose |
| --- | --- |
| `scripts/datawrapper-create.py` | create new chart, returns id |
| `scripts/datawrapper-publish.py` | push new CSV to an existing chart id |
| `scripts/datawrapper-index.py` | rebuild a per-index tracking chart |
| `scripts/chart-index.py` | build a per-index %-return CSV (stage 1) |
| `scripts/table-tracking.py` | build a per-index tracking-error table (stage 1) |

The canonical entry today is `/charts/datawrapper-publish` for one-off
chart updates; `datawrapper-index.py` is the per-index rebuild path.

## Styling conventions (Adjacent brand)

Every Datawrapper chart must read as Adjacent, not as a Datawrapper
default. The canonical spec lives in the `adjacent-chart-style` skill;
load it. Summary:

- Title: short, Inter, no em-dash, no emoji.
- Intro: 1 sentence, the `--font-serif` generic.
- Source line: `Source: <publisher>, mid-quote`.
- All numbers: `0.00%` format. Never `pp`.
- Background: `#ece9e2` (canvas); plot area `#ffffff`.
- Base / text color: `#0a0f0d`; secondary `#5c5a53`; meta `#7f7d7a`.
- Axis + grid lines: `#d6d2c8` / `#ecebea`.
- Series colors, in order: `#3fae5a`, `#e66b55`, `#6fb7e0`, `#d89a3f`,
  `#a8c49a`, `#f0a8c8`. Up/positive `#3fae5a`; down/negative `#e66b55`.
- Data labels: the `--font-mono` generic, tabular.
- Square corners; no rounded elements.

Apply these in the metadata PATCH (see the `adjacent-chart-style` skill
for the full field map). The `conventions` hook checks the text payload
for em-dash / `pp` / emoji; the `chart-style` hook guards against
non-Adjacent palettes in any Python chart fallback.

## Column-formatting fix

Datawrapper's column type inference can mis-rank numeric columns.
Force types via `metadata.data.columns[].format`:

```json
{
  "columns": {
    "move_1d":  {"format": "0.00%", "type": "number"},
    "move_7d":  {"format": "0.00%", "type": "number"},
    "tracking": {"format": "0.00%", "type": "number"}
  }
}
```

## Idempotency

`datawrapper-publish.py` is idempotent: re-running with the same CSV
is a no-op as long as the chart id and CSV hash match. If the CSV
hash changes, push the new content and republish.

## Failure modes

- 401 on chart publish: `DATAWRAPPER_API_KEY` invalid. Hard fail.
- 422 on metadata update: title or column format invalid. Report and
  retry after manual fix.
- Network timeout: queue the request. `datawrapper-create.py --retry 3`
  handles this with exponential backoff.
