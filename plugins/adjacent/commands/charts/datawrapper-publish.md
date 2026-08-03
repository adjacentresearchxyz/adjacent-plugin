---
name: datawrapper-publish
description: Publish a CSV to Datawrapper. Thin wrapper around the datawrapper-tables skill.
allowed-tools:
  - Bash
  - adjacent-markets/list
  - adjacent-markets/price
argument-hint: "<existing-chart-id> <path-to-csv> | --new <title> <path-to-csv>"
---

# Datawrapper publish

Resolve `$ARGUMENTS` and dispatch:

- `--new <title> <csv-path>` -> run
  `scripts/datawrapper-create.py --title <title> --csv <csv-path>`
- `<existing-chart-id> <csv-path>` -> run
  `scripts/datawrapper-publish.py <chart-id> --csv <csv-path>`

If a CSV path is `-`, read from stdin instead of a file.

The canonical workflow lives in the `datawrapper-tables` skill; load
it and follow it. Print 3 final lines per the `briefings` skill:

- `chart: https://datawrapper.de/chart/<id>`
- `csv-length: <rows>`
- `published-at: <YYYY-MM-DD HH:MM ET>` (omit when `--no-publish` is in
  `$ARGUMENTS`)

If `DATAWRAPPER_API_KEY` is unset:
- Print: `error: DATAWRAPPER_API_KEY unset`
- Print: `Preferred route: publish via Datawrapper. Please add your API key to do so.`
- As a fallback, build and save the chart locally using Seaborn (Python),
  branded as Adjacent. Load the `adjacent-chart-style` skill and use the
  helper so the output matches the design system:
  `import adjacent_chart_style as adj; fig, ax = adj.figure(headline=...,
  deck=...); ... adj.save(fig, path)`. The headline states the finding;
  the identifier goes in the deck. Use `adj.SERIES` / `adj.UP` /
  `adj.DOWN`, never a library-default palette. The `chart-style` hook
  blocks divergent colors.