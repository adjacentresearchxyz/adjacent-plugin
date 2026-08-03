# Adjacent integration roadmap

Product ideas from agent testing, tracked separately from shipped plugin
features.

## Shipped in-plugin

- Live news-to-price ranking (`/data/news-latest` + `/data/news-correlation`).
- Candles-backed chart data (`/data/candles-chart`).
- Similar-market hedge discovery (`/data/similar-hedges`).
- Zero-config public snapshot health checks (`/data/snapshot-health`).
- Export cookbook (`/data/export`) over `/export/*`.
- Self-serve docs Q&A (`/data/docs-ask`) backed by `/docs.zip`.

## Public products

- Index Explorer with constituents, prices, correlations, and CSV export.
- Live rate-limit and quota page.
- Public correlation heatmap when the correlation endpoint is live.
- Related-markets widgets backed by similar-market data.
- Standalone guided repository for building a direct index.

## Builder experience

- Starter kits generated from `llms.txt` and `llms-full.txt`.
- Host-specific and data-library quickstarts.

## Waiting on the platform

- Correlation regime-shift alerts when `indices/{id}/correlation` is live.
- Real sub-agent delegation where the host supports it.
