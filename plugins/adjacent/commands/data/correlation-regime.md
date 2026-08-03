---
name: correlation-regime
description: Flag 2-sigma shifts from supplied correlation observations. The live correlation endpoint is unavailable.
allowed-tools:
  - Bash
  - Read
argument-hint: "--input <correlations.json> [--sigma 2]"
---

# Correlation regime

The `indices/{id}/correlation` endpoint is unavailable. Never call it.

For supplied JSON, run:

```bash
python3 scripts/correlation-regime.py $ARGUMENTS
```

Each row must contain `ts`, `index`, `benchmark`, and `correlation`.
