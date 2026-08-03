---
name: capabilities
description: Show which Adjacent data surfaces are live, guided, offline-only, or unavailable.
allowed-tools:
  - Bash
argument-hint: ""
---

# Capabilities

Run `python3 scripts/capability-status.py`. Treat
`data/capabilities.json` as the source of truth.

Do not call an endpoint whose `api_status` is `unavailable`.
