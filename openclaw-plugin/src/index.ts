/**
 * Adjacent Markets - OpenClaw tool plugin.
 *
 * Every tool here executes real work through the bundled Python core and
 * returns structured results plus artifact paths. None of them return
 * instructions for the agent to carry out by hand.
 *
 * Safety: read-only. The rebalance path is absent rather than flag-gated,
 * so no tool in this package can place an exchange order. Scripts run from
 * an explicit allowlist with an argv array and no shell.
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
    "and chart artifacts. Executes read-only workflows and returns structured " +
    "results with artifact paths. Never places orders or invokes shells.",
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
    // -----------------------------------------------------------------------
    tool({
      name: "adjacent_chart",
      label: "Adjacent Chart",
      description:
        "Build a chart artifact end to end: fetch the mid-quote series, write the " +
        "CSV, optionally render an Adjacent-branded PNG and publish to Datawrapper. " +
        "Returns artifact paths. The candles source needs no local data.",
      parameters: Type.Object({
        id: Type.Optional(Type.String({ description: "Market or index id for the candles source." })),
        type: Type.Optional(
          Type.String({ description: "Entity type for the candles source.", enum: ["market", "index", "event", "rate"] }),
        ),
        timeframe: Type.Optional(Type.String({ description: "Candle timeframe (default 7d)." })),
        index: Type.Optional(
          Type.String({ description: "Index slug; uses local tracking data instead of candles." }),
        ),
        png: Type.Optional(Type.Boolean({ description: "Also render a branded PNG (needs matplotlib)." })),
        rebase: Type.Optional(Type.Boolean({ description: "Rebase closes to 100 at the first point." })),
        datawrapperChartId: Type.Optional(
          Type.String({ description: "Publish the CSV to this Datawrapper chart id." }),
        ),
      }),
      async execute({ id, type, timeframe, index, png, rebase, datawrapperChartId }, config) {
        applyKey(config);
        if (!id && !index) {
          return { ok: false, error: "pass id (candles source) or index (tracking source)" };
        }

        const args = [...tierFlag(config)];
        if (index) {
          args.push("--source", "tracking", "--index", index);
        } else {
          args.push("--source", "candles", "--id", String(id));
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
  ],
});
