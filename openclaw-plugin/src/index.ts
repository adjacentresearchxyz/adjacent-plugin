/**
 * Adjacent Markets - OpenClaw tool plugin.
 *
 * Read-only prediction-market guidance for the Adjacent MCP. Exposes three
 * agent-callable tools that encode the Adjacent conventions (mid-quote
 * pricing, MCP tier routing, index-mover thresholds) without ever placing
 * an order, invoking a shell with user input, or mutating state.
 *
 * Entry point: defineToolPlugin from openclaw/plugin-sdk/tool-plugin.
 * Manifest: openclaw.plugin.json (contracts.tools must match the tool
 * names declared below).
 */

import { Type } from "typebox";
import { defineToolPlugin } from "openclaw/plugin-sdk/tool-plugin";

// ---------------------------------------------------------------------------
// Convention constants - the single source of truth for guidance tools.
// ---------------------------------------------------------------------------

/** MCP tier labels and their canonical server names. */
const MCP_TIERS = {
  dev: "adjacent-markets-dev",
  prod: "adjacent-markets",
} as const;

/** Index-mover thresholds (mid-based), matching AGENTS.md. */
const MOVER_THRESHOLDS = [
  { horizon: "1D", absMovePct: 1.5, action: "alert + append to movers log" },
  { horizon: "7D", absMovePct: 4.0, action: "alert + append to movers log" },
  { horizon: "30D", absMovePct: 8.0, action: "morning-briefing highlight" },
] as const;

/** Forbidden actions - the plugin never does these. */
const SAFETY = {
  noOrders: true,
  noShellExecution: true,
  midQuoteOnly: true,
  unitPercent: true,
  unitPercentPointsBanned: true,
} as const;

const CAPABILITIES = {
  live: [
    "docs_archive",
    "similar_markets",
    "market_candles",
    "public_snapshots",
    "exports",
    "news_latest",
  ],
  unavailable: ["index_correlation"],
} as const;

// ---------------------------------------------------------------------------
// Tools
// ---------------------------------------------------------------------------

export default defineToolPlugin({
  id: "adjacent-markets",
  name: "Adjacent Markets",
  description:
    "Read-only Adjacent prediction-market guidance: mid-quote conventions, " +
    "index discovery, and mover thresholds. Never places orders or invokes shells.",
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
    // adjacent_discover - how to discover Adjacent indices and markets.
    // -----------------------------------------------------------------------
    tool({
      name: "adjacent_discover",
      label: "Adjacent Discover",
      description:
        "Return read-only guidance for discovering Adjacent indices and markets " +
        "via the Adjacent MCP, including the correct MCP tier and list tool calls.",
      parameters: Type.Object({
        query: Type.Optional(
          Type.String({
            description: "Optional filter hint (index slug or topic keyword).",
          }),
        ),
      }),
      async execute({ query }, config) {
        const tier = (config.tier === "prod" ? "prod" : "dev") as "dev" | "prod";
        const mcpServer = MCP_TIERS[tier];
        const listTool = "mcp__" + mcpServer + "__list";
        const hasKey = Boolean(config.apiKey);
        const guidance =
          "Use the " + listTool + " tool to list indices (type=index) or markets. " +
          "Default to the " + mcpServer + " tier (15-min delayed) unless " +
          "ADJACENT_API_KEY is set, in which case the prod tier is safe for " +
          "rebalance and live alerts. Discover live slugs at runtime; do not " +
          "bake in hardcoded Adjacent slugs." +
          (hasKey ? " An API key is configured; the prod tier is available." : "");
        return {
          tier,
          mcpServer,
          listTool,
          query,
          guidance,
          safety: {
            noOrders: SAFETY.noOrders,
            midQuoteOnly: SAFETY.midQuoteOnly,
          },
        };
      },
    }),

    // -----------------------------------------------------------------------
    // adjacent_price - mid-quote convention and price-fetch guidance.
    // -----------------------------------------------------------------------
    tool({
      name: "adjacent_price",
      label: "Adjacent Price",
      description:
        "Return read-only guidance for fetching Adjacent mid-quote prices, " +
        "including why mid (not ask/bid) is used for tracking and rebalance math.",
      parameters: Type.Object({
        marketId: Type.Optional(
          Type.String({
            description: "Optional Adjacent market id in platform:raw form.",
          }),
        ),
      }),
      async execute({ marketId }, config) {
        const tier = (config.tier === "prod" ? "prod" : "dev") as "dev" | "prod";
        const mcpServer = MCP_TIERS[tier];
        const priceTool = "mcp__" + mcpServer + "__price";
        const guidance =
          "Call " + priceTool + " with required fields id and type " +
          "(index | rate | event | market), plus timeframe (e.g. 24h, 7d). " +
          "Use raw:false for compact summaries or raw:true for bid/ask/mid " +
          "timeseries. Always model at mid: (bid + ask) / 2. Modeling at ask " +
          "or bid overstates or understates slippage and produces misleading " +
          "tracking error. Tracking report = " +
          "(mid_portfolio_return - mid_index_return) in %.";
        return {
          convention: "mid-quote",
          formula: "mid = (bid + ask) / 2",
          unit: "%",
          bannedUnit: "pp",
          requiredArgs: ["id", "type", "timeframe"],
          priceTool,
          marketId,
          guidance,
        };
      },
    }),

    // -----------------------------------------------------------------------
    // adjacent_movers - index-mover threshold table (read-only).
    // -----------------------------------------------------------------------
    tool({
      name: "adjacent_movers",
      label: "Adjacent Movers",
      description:
        "Return the Adjacent index-mover threshold table (1D / 7D / 30D) and " +
        "the read-only scan guidance. All thresholds are mid-based.",
      parameters: Type.Object({}),
      async execute() {
        return {
          thresholds: MOVER_THRESHOLDS.map((t) => ({
            horizon: t.horizon,
            absMovePct: t.absMovePct,
            action: t.action,
          })),
          basis: "mid-quote",
          unit: "%",
          guidance:
            "Fire rebalance decisions on mid price moves, not on last-trade prints. " +
            "Flag a mover when |move| crosses the horizon threshold. Append flagged " +
            "movers to the movers log. The 30D highlight goes in the morning briefing. " +
            "This tool is read-only and never places orders.",
        };
      },
    }),

    tool({
      name: "adjacent_capabilities",
      label: "Adjacent Capabilities",
      description:
        "Report which Adjacent data surfaces are live and which require supplied JSON.",
      parameters: Type.Object({}),
      async execute() {
        return {
          live: [...CAPABILITIES.live],
          unavailable: [...CAPABILITIES.unavailable],
          guidance:
            "news_latest is live. Do not call index_correlation; use supplied " +
            "JSON for offline correlation analysis until it is live.",
        };
      },
    }),
  ],
});
