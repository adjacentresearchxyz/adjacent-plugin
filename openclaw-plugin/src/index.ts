/**
 * Adjacent Markets - OpenClaw tool plugin.
 *
 * Every tool here executes real work through the bundled Python core and
 * returns structured results plus artifact paths. None of them return
 * instructions for the agent to carry out by hand.
 *
 * Safety: read-only. The rebalance plan tool forces --dry-run so no
 * exchange order is ever submitted. Scripts run from an explicit
 * allowlist with an argv array and no shell.
 *
 * Chart rule: adjacent_chart is the ONLY way to produce chart images
 * through this plugin. Never generate chart code, HTML, SVG, or freehand
 * visualizations. Every chart must come from chart-build.py +
 * adjacent_chart_style (the branded helper) or Datawrapper with Adjacent
 * metadata. An unbranded chart is a bug, not a shortcut.
 *
 * Entry point: defineToolPlugin from openclaw/plugin-sdk/tool-plugin.
 * Manifest: openclaw.plugin.json (contracts.tools must match these names).
 */

import { existsSync } from "node:fs";
import { join } from "node:path";
import { Type } from "typebox";
import { defineToolPlugin } from "openclaw/plugin-sdk/tool-plugin";

import {
  resolvePython,
  resolveScriptsDir,
  resolveStateDir,
  runJsonScript,
  runScript,
  runtimeIsInstalled,
} from "./runtime.js";

/** Index-mover thresholds (mid-based), matching AGENTS.md. */
const MOVER_THRESHOLDS = [
  { horizon: "1D", absMovePct: 1.5 },
  { horizon: "7D", absMovePct: 4.0 },
  { horizon: "30D", absMovePct: 8.0 },
] as const;

type Tier = "dev" | "prod";

function tierFor(config: { apiKey?: string; tier?: string }): Tier {
  return config.tier === "prod" && config.apiKey ? "prod" : "dev";
}

/** Config apiKey feeds the scripts through the env the runner already copies. */
function applyKey(config: { apiKey?: string }): void {
  if (config.apiKey && !process.env.ADJACENT_API_KEY) {
    process.env.ADJACENT_API_KEY = config.apiKey;
  }
}

function tierFlag(config: { apiKey?: string; tier?: string }): string[] {
  return tierFor(config) === "prod" ? ["--prod"] : [];
}

export default defineToolPlugin({
  id: "adjacent-markets",
  name: "Adjacent Markets",
  description:
    "Adjacent prediction-market workflows: daily briefs, tradable snapshots, " +
    "chart artifacts, topic briefs, news, tracking, and MCP queries. Executes " +
    "read-only workflows and returns structured results with artifact paths. " +
    "Never places orders or invokes shells. Charts must come from adjacent_chart " +
    "only - never freehand chart code.",
  configSchema: Type.Object({
    apiKey: Type.Optional(
      Type.String({ description: "Adjacent API key. Omit for the 15-min delayed tier." }),
    ),
    tier: Type.Optional(
      Type.String({
        description: "MCP tier: dev (adjacent-markets-dev) or prod (adjacent-markets). Defaults to dev.",
        enum: ["dev", "prod"],
      }),
    ),
  }),
  tools: (tool) => [
    // -----------------------------------------------------------------------
    // adjacent_doctor - is this install ready to work?
    // -----------------------------------------------------------------------
    tool({
      name: "adjacent_doctor",
      label: "Adjacent Doctor",
      description:
        "Check this install: Python runtime, bundled shared core, API key and " +
        "resulting data tier, Datawrapper config, and local index data. Reports " +
        "what works, what is degraded, and how to fix it. Never prints secrets.",
      parameters: Type.Object({}),
      async execute(_params, config) {
        applyKey(config);
        const scriptsDir = resolveScriptsDir();
        const checks: Array<{
          name: string;
          status: "ok" | "warn" | "fail";
          detail: string;
          remedy?: string;
        }> = [];

        const python = await runScript("capability-status.py", ["--json"], { timeoutMs: 20_000 });
        checks.push(
          python.ok
            ? { name: "python", status: "ok", detail: `${resolvePython()} ran the shared core` }
            : {
                name: "python",
                status: "fail",
                detail: python.error ?? "python3 could not run the shared core",
                remedy: "Install Python 3.11+ and ensure python3 is on PATH, or set ADJACENT_PYTHON.",
              },
        );

        checks.push(
          runtimeIsInstalled()
            ? { name: "shared_core", status: "ok", detail: `bundled at ${scriptsDir}` }
            : {
                name: "shared_core",
                status: "fail",
                detail: `no scripts found at ${scriptsDir}`,
                remedy: "Reinstall the plugin, or set ADJACENT_PLUGIN_ROOT to a checkout.",
              },
        );

        const tier = tierFor(config);
        checks.push({
          name: "data_tier",
          status: tier === "prod" ? "ok" : "warn",
          detail:
            tier === "prod"
              ? "realtime tier (API key configured)"
              : "public 15-min-delayed tier (no API key)",
          ...(tier === "prod"
            ? {}
            : { remedy: "Set the apiKey config value or ADJACENT_API_KEY for realtime data." }),
        });

        checks.push(
          process.env.DATAWRAPPER_API_KEY
            ? { name: "datawrapper", status: "ok", detail: "publishing available" }
            : {
                name: "datawrapper",
                status: "warn",
                detail: "no key; charts stay local as CSV and PNG",
                remedy: "Set DATAWRAPPER_API_KEY to publish charts.",
              },
        );

        const dataDir = join(scriptsDir, "..", "data");
        const hasLocalData = existsSync(join(dataDir, "watchlist.json"));
        checks.push({
          name: "local_data",
          status: hasLocalData ? "ok" : "warn",
          detail: hasLocalData ? `catalogs at ${dataDir}` : "no local index or position data",
          ...(hasLocalData
            ? {}
            : { remedy: "Optional. Briefs fall back to a live index list when the watchlist is empty." }),
        });

        const stateDir = resolveStateDir();
        checks.push({ name: "artifacts", status: "ok", detail: `writing to ${stateDir}` });

        const failed = checks.filter((c) => c.status === "fail");
        return {
          ok: failed.length === 0,
          ready: failed.length === 0,
          tier,
          scriptsDir,
          stateDir,
          checks,
          summary:
            failed.length === 0
              ? `Ready on the ${tier} tier. ${checks.filter((c) => c.status === "warn").length} optional item(s) unconfigured.`
              : `Not ready: ${failed.map((c) => c.name).join(", ")}.`,
        };
      },
    }),

    // -----------------------------------------------------------------------
    // adjacent_brief - the daily / index brief, end to end.
    // -----------------------------------------------------------------------
    tool({
      name: "adjacent_brief",
      label: "Adjacent Brief",
      description:
        "Run the Adjacent daily brief: resolve the watchlist, fetch mid-quote " +
        "moves, apply the 1D and 7D mover thresholds, and return both the " +
        "structured movers and the formatted brief text. Read-only.",
      parameters: Type.Object({
        slugs: Type.Optional(
          Type.String({ description: "Comma-separated index slugs. Omit to use the watchlist or a live list." }),
        ),
        withNews: Type.Optional(
          Type.Boolean({ description: "Attach live news headlines to flagged movers." }),
        ),
        limit: Type.Optional(Type.Number({ description: "Max slugs to scan (default 10)." })),
        save: Type.Optional(
          Type.Boolean({ description: "Also write the result as a JSON artifact." }),
        ),
      }),
      async execute({ slugs, withNews, limit, save }, config) {
        applyKey(config);
        const args = [...tierFlag(config)];
        if (slugs) args.push("--slugs", slugs);
        if (withNews) args.push("--with-news");
        if (typeof limit === "number") args.push("--limit", String(Math.trunc(limit)));
        if (save) args.push("--output", join(resolveStateDir(), "brief-latest.json"));

        const result = await runJsonScript<Record<string, unknown>>("brief-daily.py", args, {
          timeoutMs: 180_000,
        });
        if (!result.ok) {
          return { ok: false, error: result.error, detail: result.stderr };
        }
        return result.data;
      },
    }),

    // -----------------------------------------------------------------------
    // adjacent_snapshot - standardized tradable snapshot.
    // -----------------------------------------------------------------------
    tool({
      name: "adjacent_snapshot",
      label: "Adjacent Snapshot",
      description:
        "Build a normalized tradable market snapshot from a topic, an index, or " +
        "explicit ids. Every row carries mid, bid, ask, spread, 24h volume, and " +
        "the 1D move in the same units. Returns rows plus a CSV artifact path.",
      parameters: Type.Object({
        query: Type.Optional(Type.String({ description: "Free-text topic to resolve into markets." })),
        index: Type.Optional(Type.String({ description: "Index slug; snapshots its constituents." })),
        ids: Type.Optional(Type.String({ description: "Comma-separated ids in platform:raw form." })),
        limit: Type.Optional(Type.Number({ description: "Max rows (default 25)." })),
        timeframe: Type.Optional(Type.String({ description: "Quote timeframe (default 24h)." })),
        quotes: Type.Optional(
          Type.Boolean({
            description:
              "Fetch the bid/ask quote leg per row. Costs one request per market; " +
              "without it rows carry the price the index payload already reported.",
          }),
        ),
        csv: Type.Optional(Type.Boolean({ description: "Write the rows to a CSV artifact." })),
      }),
      async execute({ query, index, ids, limit, timeframe, quotes, csv }, config) {
        applyKey(config);
        const selectors = [query, index, ids].filter(Boolean);
        if (selectors.length !== 1) {
          return {
            ok: false,
            error: "pass exactly one of query, index, or ids",
          };
        }

        const args = [...tierFlag(config)];
        if (ids) args.push("--ids", ids);
        else if (index) args.push("--index", index);
        else if (query) args.push("--query", query);
        if (typeof limit === "number") args.push("--limit", String(Math.trunc(limit)));
        if (timeframe) args.push("--timeframe", timeframe);
        if (quotes) args.push("--quotes");
        if (csv) args.push("--csv", join(resolveStateDir(), "snapshot-latest.csv"));

        const result = await runJsonScript<Record<string, unknown>>("market-snapshot.py", args, {
          timeoutMs: 180_000,
        });
        if (!result.ok) {
          return { ok: false, error: result.error, detail: result.stderr };
        }
        return result.data;
      },
    }),

    // -----------------------------------------------------------------------
    // adjacent_chart - data to chart artifact in one call.
    // THE ONLY chart path. Never freehand chart code.
    // -----------------------------------------------------------------------
    tool({
      name: "adjacent_chart",
      label: "Adjacent Chart",
      description:
        "Build a chart artifact end to end: fetch the mid-quote series, write the " +
        "CSV, optionally render an Adjacent-branded PNG and publish to Datawrapper. " +
        "Returns artifact paths. The candles source needs no local data. " +
        "This is the ONLY way to produce chart images through this plugin: " +
        "never generate chart code, HTML, SVG, or freehand visualizations. " +
        "Always pass png: true when the user wants a chart image. " +
        "Every chart uses the Adjacent branded helper (deep green, beige canvas, " +
        "source line) - no library defaults.",
      parameters: Type.Object({
        id: Type.Optional(Type.String({ description: "Market or index id for the candles source." })),
        ids: Type.Optional(
          Type.String({ description: "Comma-separated market or index ids to overlay." }),
        ),
        type: Type.Optional(
          Type.String({ description: "Entity type for the candles source.", enum: ["market", "index", "event", "rate"] }),
        ),
        timeframe: Type.Optional(Type.String({ description: "Candle timeframe (default 7d)." })),
        index: Type.Optional(
          Type.String({ description: "Index slug; uses local tracking data instead of candles." }),
        ),
        png: Type.Optional(Type.Boolean({ description: "Also render a branded PNG (needs matplotlib). Pass true when the user wants an image." })),
        rebase: Type.Optional(Type.Boolean({ description: "Rebase closes to 100 at the first point." })),
        datawrapperChartId: Type.Optional(
          Type.String({ description: "Publish the CSV to this Datawrapper chart id." }),
        ),
      }),
      async execute({ id, ids, type, timeframe, index, png, rebase, datawrapperChartId }, config) {
        applyKey(config);
        if (!id && !ids && !index) {
          return { ok: false, error: "pass id/ids (candles source) or index (tracking source)" };
        }
        if (index && (id || ids)) {
          return { ok: false, error: "pass either index or id/ids, not both" };
        }

        const args = [...tierFlag(config)];
        if (index) {
          args.push("--source", "tracking", "--index", index);
        } else {
          args.push("--source", "candles");
          if (id) args.push("--id", id);
          if (ids) args.push("--ids", ids);
          if (type) args.push("--type", type);
          if (timeframe) args.push("--timeframe", timeframe);
        }
        if (rebase) args.push("--rebase");
        if (png) args.push("--png");
        if (datawrapperChartId) args.push("--datawrapper-chart-id", datawrapperChartId);

        const result = await runJsonScript<Record<string, unknown>>("chart-build.py", args, {
          timeoutMs: 180_000,
        });
        if (!result.ok) {
          return { ok: false, error: result.error, detail: result.stderr };
        }
        return result.data;
      },
    }),

    // -----------------------------------------------------------------------
    // adjacent_movers - the threshold scan on its own.
    // -----------------------------------------------------------------------
    tool({
      name: "adjacent_movers",
      label: "Adjacent Movers",
      description:
        "Scan indices for threshold-crossing mid-quote moves and return the sorted " +
        "movers with the thresholds applied. The brief without the prose.",
      parameters: Type.Object({
        slugs: Type.Optional(Type.String({ description: "Comma-separated index slugs to scan." })),
        limit: Type.Optional(Type.Number({ description: "Max slugs to scan (default 10)." })),
      }),
      async execute({ slugs, limit }, config) {
        applyKey(config);
        const args = [...tierFlag(config)];
        if (slugs) args.push("--slugs", slugs);
        if (typeof limit === "number") args.push("--limit", String(Math.trunc(limit)));

        const result = await runJsonScript<Record<string, unknown>>("brief-daily.py", args, {
          timeoutMs: 180_000,
        });
        if (!result.ok) {
          return { ok: false, error: result.error, detail: result.stderr };
        }
        const data = result.data ?? {};
        return {
          ok: true,
          as_of: data.as_of,
          tier: data.tier,
          basis: "mid-quote",
          unit: "%",
          thresholds: MOVER_THRESHOLDS,
          movers: data.movers,
          flagged_count: data.flagged_count,
          skipped: data.skipped,
        };
      },
    }),

    // -----------------------------------------------------------------------
    // adjacent_capabilities - which surfaces are live, from the shipped catalog.
    // -----------------------------------------------------------------------
    tool({
      name: "adjacent_capabilities",
      label: "Adjacent Capabilities",
      description:
        "Report which Adjacent data surfaces are live and which need supplied JSON, " +
        "read from the capability catalog that ships with this install.",
      parameters: Type.Object({}),
      async execute() {
        const result = await runJsonScript<{ capabilities?: Record<string, { api_status?: string; plugin_status?: string }> }>(
          "capability-status.py",
          ["--json"],
          { timeoutMs: 20_000 },
        );
        if (!result.ok) {
          return { ok: false, error: result.error, detail: result.stderr };
        }
        const capabilities = result.data?.capabilities ?? {};
        const live: string[] = [];
        const unavailable: string[] = [];
        for (const [name, entry] of Object.entries(capabilities)) {
          (entry.api_status === "live" ? live : unavailable).push(name);
        }
        return { ok: true, live, unavailable, capabilities };
      },
    }),

    // -----------------------------------------------------------------------
    // adjacent_mcp_query - read-only Adjacent MCP (list/find/get/price).
    // -----------------------------------------------------------------------
    tool({
      name: "adjacent_mcp_query",
      label: "Adjacent MCP Query",
      description:
        "Run a read-only Adjacent MCP query: list entities, find markets by topic, " +
        "get a single entity by id, or fetch the mid-quote price series for a " +
        "market, index, or rate. No API key required for the delayed tier. " +
        "get and price require type; find takes a query string. " +
        "Supports a read-only venue fallback (kalshi or polymarket) for price " +
        "when Adjacent MCP is unavailable.",
      parameters: Type.Object({
        tool: Type.String({
          description: "Adjacent MCP tool to invoke (read-only).",
          enum: ["list", "find", "get", "price"],
        }),
        type: Type.Optional(
          Type.String({
            description: "Entity kind. Required for get and price; optional for find/list.",
            enum: ["events", "event", "market", "markets", "index", "indices", "rate", "news"],
          }),
        ),
        query: Type.Optional(
          Type.String({ description: "Free-text query for the find tool." }),
        ),
        id: Type.Optional(
          Type.String({ description: "Entity id for get or price (slug or platform:raw form)." }),
        ),
        timeframe: Type.Optional(
          Type.String({ description: "Timeframe for price (e.g. 24h, 7d, 30d, 1d)." }),
        ),
        raw: Type.Optional(
          Type.Boolean({ description: "Return raw timeseries for price." }),
        ),
        fallbackVenue: Type.Optional(
          Type.String({
            description: "Read-only fallback for a market price when Adjacent MCP fails.",
            enum: ["kalshi", "polymarket"],
          }),
        ),
        side: Type.Optional(
          Type.String({
            description: "Outcome side for a Kalshi fallback quote (yes or no). Ignored for Polymarket.",
            enum: ["yes", "no"],
          }),
        ),
      }),
      async execute(params, config) {
        applyKey(config);
        const mcpTool = params.tool;
        const args: string[] = [mcpTool];

        if (mcpTool === "list") {
          args.push("--type", params.type ?? "event");
        } else if (mcpTool === "find") {
          const q = params.query;
          if (!q) {
            return { ok: false, error: "find requires a query string" };
          }
          args.push(q);
          if (params.type) args.push("--type", params.type);
        } else if (mcpTool === "get") {
          if (!params.id || !params.type) {
            return { ok: false, error: "get requires id and type" };
          }
          args.push(params.id, "--type", params.type);
        } else if (mcpTool === "price") {
          if (!params.id || !params.type || !params.timeframe) {
            return { ok: false, error: "price requires id, type, and timeframe" };
          }
          args.push(params.id, params.timeframe, "--type", params.type);
          if (params.raw) args.push("--raw");
          if (params.fallbackVenue) args.push("--fallback-venue", params.fallbackVenue);
          if (params.side) args.push("--side", params.side);
        }

        const result = await runJsonScript<Record<string, unknown>>("mcp-cli.py", args, {
          timeoutMs: 120_000,
        });
        if (!result.ok) {
          return { ok: false, error: result.error, detail: result.stderr };
        }
        return result.data;
      },
    }),

    // -----------------------------------------------------------------------
    // adjacent_topic_brief - news + markets + charts for a topic.
    // -----------------------------------------------------------------------
    tool({
      name: "adjacent_topic_brief",
      label: "Adjacent Topic Brief",
      description:
        "Topic update workflow for a free-text topic (e.g. washington football, " +
        "trump, elections). Fetches news bullets, a short take, related markets " +
        "with mid quotes, and optional branded chart CSVs/PNGs. Use when the user " +
        "asks about a person, topic, or event and wants news and prediction " +
        "markets. Always pass chart: true and png: true so the brief ships at " +
        "least one branded chart. Read-only; never places orders.",
      parameters: Type.Object({
        topic: Type.String({ description: "Free-text topic query." }),
        newsLimit: Type.Optional(Type.Number({ description: "Max news items (default 5)." })),
        marketLimit: Type.Optional(Type.Number({ description: "Max markets (default 5)." })),
        timeframe: Type.Optional(Type.String({ description: "Price and chart timeframe (default 7d)." })),
        chart: Type.Optional(Type.Boolean({ description: "Build candle CSVs for priced markets. Pass true." })),
        png: Type.Optional(Type.Boolean({ description: "Also render branded PNGs (implies chart). Pass true." })),
        outputDir: Type.Optional(Type.String({ description: "Directory for chart artifacts." })),
      }),
      async execute(params, config) {
        applyKey(config);
        const args: string[] = [params.topic];
        if (typeof params.newsLimit === "number") args.push("--news-limit", String(Math.trunc(params.newsLimit)));
        if (typeof params.marketLimit === "number") args.push("--market-limit", String(Math.trunc(params.marketLimit)));
        if (params.timeframe) args.push("--timeframe", params.timeframe);
        if (params.chart) args.push("--chart");
        if (params.png) args.push("--png");
        if (tierFor(config) === "prod") args.push("--prod");
        if (params.outputDir) args.push("--output-dir", params.outputDir);
        else args.push("--output-dir", resolveStateDir());

        const result = await runJsonScript<Record<string, unknown>>("topic-brief.py", args, {
          timeoutMs: 180_000,
        });
        if (!result.ok) {
          return { ok: false, error: result.error, detail: result.stderr };
        }
        return result.data;
      },
    }),

    // -----------------------------------------------------------------------
    // adjacent_news_latest - live news surface.
    // -----------------------------------------------------------------------
    tool({
      name: "adjacent_news_latest",
      label: "Adjacent News Latest",
      description:
        "Fetch the live Adjacent news/latest surface. Set normalize to true to " +
        "emit rows shaped for adjacent_news_correlation. Wraps " +
        "scripts/news-latest.py. Read-only.",
      parameters: Type.Object({
        normalize: Type.Optional(
          Type.Boolean({ description: "Emit rows shaped for news correlation analysis." }),
        ),
      }),
      async execute({ normalize }, config) {
        applyKey(config);
        const args: string[] = [];
        if (normalize) args.push("--normalize");

        const result = await runJsonScript<Record<string, unknown>>("news-latest.py", args, {
          timeoutMs: 120_000,
        });
        if (!result.ok) {
          return { ok: false, error: result.error, detail: result.stderr };
        }
        return result.data;
      },
    }),

    // -----------------------------------------------------------------------
    // adjacent_news_correlation - rank news by mid moves.
    // -----------------------------------------------------------------------
    tool({
      name: "adjacent_news_correlation",
      label: "Adjacent News Correlation",
      description:
        "Rank news events by minute-aligned mid moves. Accepts article JSON from " +
        "the live news/latest surface (see adjacent_news_latest) or supplied " +
        "files. Wraps scripts/news-correlation.py.",
      parameters: Type.Object({
        news: Type.String({ description: "Path to article JSON." }),
        prices: Type.String({ description: "Path to mid-price JSON." }),
        windowMinutes: Type.Optional(
          Type.Number({ description: "Correlation window in minutes (default 30)." }),
        ),
      }),
      async execute({ news, prices, windowMinutes }) {
        const args = ["--news", news, "--prices", prices];
        if (typeof windowMinutes === "number") args.push("--window-minutes", String(Math.trunc(windowMinutes)));

        const result = await runJsonScript<Record<string, unknown>>("news-correlation.py", args, {
          timeoutMs: 120_000,
        });
        if (!result.ok) {
          return { ok: false, error: result.error, detail: result.stderr };
        }
        return result.data;
      },
    }),

    // -----------------------------------------------------------------------
    // adjacent_correlation_regime - flag sigma-level shifts.
    // -----------------------------------------------------------------------
    tool({
      name: "adjacent_correlation_regime",
      label: "Adjacent Correlation Regime",
      description:
        "Flag sigma-level shifts from supplied correlation observations. " +
        "Offline analysis only; never calls the unavailable correlation endpoint. " +
        "Wraps scripts/correlation-regime.py.",
      parameters: Type.Object({
        input: Type.String({ description: "Path to correlation observation JSON." }),
        sigma: Type.Optional(
          Type.Number({ description: "Sigma threshold for regime shifts (default 2.0)." }),
        ),
      }),
      async execute({ input, sigma }) {
        const args = ["--input", input];
        if (typeof sigma === "number") args.push("--sigma", String(sigma));

        const result = await runJsonScript<Record<string, unknown>>("correlation-regime.py", args, {
          timeoutMs: 60_000,
        });
        if (!result.ok) {
          return { ok: false, error: result.error, detail: result.stderr };
        }
        return result.data;
      },
    }),

    // -----------------------------------------------------------------------
    // adjacent_portfolio_snapshot - portfolio status from cached positions.
    // -----------------------------------------------------------------------
    tool({
      name: "adjacent_portfolio_snapshot",
      label: "Adjacent Portfolio Snapshot",
      description:
        "Report portfolio status for one or all indices from cached position " +
        "documents. Read-only. Wraps scripts/portfolio-snapshot.py.",
      parameters: Type.Object({
        index: Type.Optional(Type.String({ description: "Index slug. Omit for all indices." })),
        includePnl: Type.Optional(
          Type.Boolean({ description: "Include per-position P&L lines." }),
        ),
      }),
      async execute({ index, includePnl }) {
        const args: string[] = ["--json"];
        if (index) args.push("--index", index);
        if (includePnl) args.push("--include-pnl");

        const result = await runJsonScript<Record<string, unknown>>("portfolio-snapshot.py", args, {
          timeoutMs: 60_000,
        });
        if (!result.ok) {
          return { ok: false, error: result.error, detail: result.stderr };
        }
        return result.data;
      },
    }),

    // -----------------------------------------------------------------------
    // adjacent_tracking - per-position mid-based tracking table.
    // -----------------------------------------------------------------------
    tool({
      name: "adjacent_tracking",
      label: "Adjacent Tracking",
      description:
        "Produce a per-position mid-based table for an index: size, mid, cost " +
        "basis, notional, %-weight, and return against cost basis. Wraps " +
        "scripts/tracking-index.py.",
      parameters: Type.Object({
        index: Type.String({ description: "Index slug." }),
      }),
      async execute({ index }) {
        const args = ["--index", index, "--json"];

        const result = await runJsonScript<Record<string, unknown>>("tracking-index.py", args, {
          timeoutMs: 60_000,
        });
        if (!result.ok) {
          return { ok: false, error: result.error, detail: result.stderr };
        }
        return result.data;
      },
    }),

    // -----------------------------------------------------------------------
    // adjacent_tracking_table - tracking table CSV.
    // -----------------------------------------------------------------------
    tool({
      name: "adjacent_tracking_table",
      label: "Adjacent Tracking Table",
      description:
        "Build a per-position table CSV for an index from a prior tracking run. " +
        "Wraps scripts/table-tracking.py.",
      parameters: Type.Object({
        index: Type.String({ description: "Index slug." }),
      }),
      async execute({ index }) {
        const args = ["--index", index, "--output", join(resolveStateDir(), `tracking-${index}.csv`)];

        const result = await runJsonScript<Record<string, unknown>>("table-tracking.py", args, {
          timeoutMs: 60_000,
        });
        if (!result.ok) {
          return { ok: false, error: result.error, detail: result.stderr };
        }
        return result.data;
      },
    }),

    // -----------------------------------------------------------------------
    // adjacent_chart_csv - per-index tracking chart CSV.
    // -----------------------------------------------------------------------
    tool({
      name: "adjacent_chart_csv",
      label: "Adjacent Chart CSV",
      description:
        "Build a per-index 24h %-return chart CSV (index vs portfolio, both " +
        "rebased to 100 at the last fill). Wraps scripts/chart-index.py. " +
        "For live candle charts use adjacent_chart instead.",
      parameters: Type.Object({
        index: Type.String({ description: "Index slug." }),
      }),
      async execute({ index }) {
        const args = ["--index", index, "--output", join(resolveStateDir(), `chart-${index}.csv`)];

        const result = await runJsonScript<Record<string, unknown>>("chart-index.py", args, {
          timeoutMs: 60_000,
        });
        if (!result.ok) {
          return { ok: false, error: result.error, detail: result.stderr };
        }
        return result.data;
      },
    }),

    // -----------------------------------------------------------------------
    // adjacent_candles_chart - mid-based candle chart CSV from local JSON.
    // -----------------------------------------------------------------------
    tool({
      name: "adjacent_candles_chart",
      label: "Adjacent Candles Chart",
      description:
        "Build a mid-based ts,close chart CSV from Adjacent market candle JSON. " +
        "Wraps scripts/candles-chart.py. For live charts use adjacent_chart.",
      parameters: Type.Object({
        input: Type.String({ description: "Path to candle JSON." }),
        rebase: Type.Optional(Type.Boolean({ description: "Rebase closes to 100 at the first point." })),
      }),
      async execute({ input, rebase }) {
        const args = ["--input", input];
        if (rebase) args.push("--rebase");

        const result = await runJsonScript<Record<string, unknown>>("candles-chart.py", args, {
          timeoutMs: 60_000,
        });
        if (!result.ok) {
          return { ok: false, error: result.error, detail: result.stderr };
        }
        return result.data;
      },
    }),

    // -----------------------------------------------------------------------
    // adjacent_similar_hedges - rank similar markets into hedges/proxies.
    // -----------------------------------------------------------------------
    tool({
      name: "adjacent_similar_hedges",
      label: "Adjacent Similar Hedges",
      description:
        "Rank similar markets into hedges (negative mid correlation) and proxies " +
        "(positive). Wraps scripts/similar-hedges.py.",
      parameters: Type.Object({
        input: Type.String({ description: "Path to similar-markets JSON with signed correlations." }),
        minAbsCorrelation: Type.Optional(
          Type.Number({ description: "Minimum absolute correlation threshold (default 0.3)." }),
        ),
      }),
      async execute({ input, minAbsCorrelation }) {
        const args = ["--input", input];
        if (typeof minAbsCorrelation === "number") args.push("--min-abs-correlation", String(minAbsCorrelation));

        const result = await runJsonScript<Record<string, unknown>>("similar-hedges.py", args, {
          timeoutMs: 60_000,
        });
        if (!result.ok) {
          return { ok: false, error: result.error, detail: result.stderr };
        }
        return result.data;
      },
    }),

    // -----------------------------------------------------------------------
    // adjacent_snapshot_health - grade public snapshot freshness.
    // -----------------------------------------------------------------------
    tool({
      name: "adjacent_snapshot_health",
      label: "Adjacent Snapshot Health",
      description:
        "Grade Adjacent public snapshots fresh, stale, or error against a max " +
        "age. Wraps scripts/snapshot-health.py.",
      parameters: Type.Object({
        input: Type.String({ description: "Path to snapshot descriptor JSON." }),
        live: Type.Optional(Type.Boolean({ description: "Check live endpoints instead of cached JSON." })),
      }),
      async execute({ input, live }) {
        const args = ["--input", input];
        if (live) args.push("--live");

        const result = await runJsonScript<Record<string, unknown>>("snapshot-health.py", args, {
          timeoutMs: 60_000,
        });
        if (!result.ok) {
          return { ok: false, error: result.error, detail: result.stderr };
        }
        return result.data;
      },
    }),

    // -----------------------------------------------------------------------
    // adjacent_datawrapper_index - rebuild a Datawrapper chart CSV.
    // -----------------------------------------------------------------------
    tool({
      name: "adjacent_datawrapper_index",
      label: "Adjacent Datawrapper Index",
      description:
        "Rebuild a per-index tracking chart CSV and optionally publish it to " +
        "Datawrapper with Adjacent branded metadata. Defaults to CSV-only " +
        "(no publish). Wraps scripts/datawrapper-index.py.",
      parameters: Type.Object({
        index: Type.String({ description: "Index slug." }),
        chartId: Type.String({ description: "Datawrapper chart id." }),
        publish: Type.Optional(
          Type.Boolean({ description: "Publish to Datawrapper (default false; CSV only)." }),
        ),
      }),
      async execute({ index, chartId, publish }) {
        const args = ["--index", index, "--chart-id", chartId];
        if (!publish) args.push("--no-publish");

        const result = await runJsonScript<Record<string, unknown>>("datawrapper-index.py", args, {
          timeoutMs: 120_000,
        });
        if (!result.ok) {
          return { ok: false, error: result.error, detail: result.stderr };
        }
        return result.data;
      },
    }),

    // -----------------------------------------------------------------------
    // adjacent_http_get - fetch a read-only Adjacent surface.
    // -----------------------------------------------------------------------
    tool({
      name: "adjacent_http_get",
      label: "Adjacent HTTP Get",
      description:
        "GET a read-only Adjacent surface (exports, docs archive, public data). " +
        "HTTPS Adjacent hosts only. Backs the export cookbook and docs Q&A. " +
        "Wraps scripts/http-get.py.",
      parameters: Type.Object({
        url: Type.String({ description: "HTTPS Adjacent URL to fetch." }),
        output: Type.Optional(
          Type.String({ description: "Write the response to this path instead of returning it." }),
        ),
      }),
      async execute({ url, output }, config) {
        applyKey(config);
        const args = ["--url", url];
        if (output) args.push("--output", output);

        const result = await runJsonScript<Record<string, unknown>>("http-get.py", args, {
          timeoutMs: 60_000,
        });
        if (!result.ok) {
          return { ok: false, error: result.error, detail: result.stderr };
        }
        return result.data;
      },
    }),

    // -----------------------------------------------------------------------
    // adjacent_rebalance_plan - dry-run rebalance PLAN only. Never places.
    // -----------------------------------------------------------------------
    tool({
      name: "adjacent_rebalance_plan",
      label: "Adjacent Rebalance Plan",
      description:
        "Compute a direct-index rebalance PLAN only. This tool is fail-closed " +
        "and never places orders: it forces --dry-run so no exchange credentials " +
        "are exercised and no order is submitted. Returns the proposed buys, " +
        "sells, and drift table. Wraps scripts/rebalance-index.py.",
      parameters: Type.Object({
        index: Type.String({ description: "Index slug." }),
        exchange: Type.Optional(
          Type.String({
            description: "Exchange adapter to target (default kalshi).",
            enum: ["kalshi"],
          }),
        ),
        plan: Type.String({ description: "Path to write the compact plan JSON." }),
      }),
      async execute({ index, exchange, plan }) {
        // --dry-run is hardcoded: this tool can never place an order.
        const args = [
          "--index", index,
          "--exchange", exchange ?? "kalshi",
          "--plan", plan,
          "--dry-run",
        ];

        const result = await runJsonScript<Record<string, unknown>>("rebalance-index.py", args, {
          timeoutMs: 120_000,
        });
        if (!result.ok) {
          return { ok: false, error: result.error, detail: result.stderr };
        }
        return { ...result.data, dry_run: true, orders_placed: false };
      },
    }),
  ],
});
