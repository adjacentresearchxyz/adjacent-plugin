---
name: docs-ask
description: Answer an Adjacent builder question from the published docs archive, not from memory.
allowed-tools:
  - Bash
  - Read
argument-hint: "<question>"
---

# Docs Q&A

The `/docs.zip` archive is live. Ground answers in it instead of
inventing API behavior:

1. Download the archive:

```bash
python3 scripts/http-get.py --url https://<host>/docs.zip --output docs.zip
```

2. Unzip and grep the Markdown for the surface in `$ARGUMENTS`.
3. Quote the doc text in the answer. If the docs do not cover it, say so
   rather than guessing.
