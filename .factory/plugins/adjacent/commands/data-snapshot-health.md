---
description: Grade Adjacent public snapshots fresh, stale, or error against a max age.
argument-hint: "--input <snapshots.json> [--live]"
---

# Snapshot health

The `/public/*` snapshot surfaces are live and need no API key. Supply a
descriptor JSON, then grade freshness:

```bash
python3 scripts/snapshot-health.py $ARGUMENTS
```

Each descriptor row is `{name, as_of, max_age_minutes}` (default max age
60 minutes). Add `--live` to GET each row's `url` first (HTTPS Adjacent
hosts only); an HTTP failure marks that row error. Exit code is non-zero
when any snapshot is not fresh.
