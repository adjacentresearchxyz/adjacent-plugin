/**
 * Runtime plumbing: locate the shared Python core and run it safely.
 *
 * The package bundles the core at <package>/runtime/scripts (see
 * scripts/bundle-runtime.mjs), so a clean install works with no repo
 * checkout and no environment configuration. The env overrides stay
 * ahead of the bundle so a developer can point at a working tree.
 *
 * Every call goes through an explicit script allowlist and spawns with an
 * argv array and shell disabled. No tool builds a command string, and no
 * caller can reach a script that is not listed here.
 */

import { spawn } from "node:child_process";
import { existsSync, mkdirSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const MODULE_DIR = dirname(fileURLToPath(import.meta.url));

/** Scripts a tool may invoke. Anything absent can never run. */
export const ALLOWED_SCRIPTS = [
  "brief-daily.py",
  "market-snapshot.py",
  "chart-build.py",
  "capability-status.py",
  "news-latest.py",
  "similar-hedges.py",
  "snapshot-health.py",
  "candles-chart.py",
  "chart-index.py",
  "table-tracking.py",
  "tracking-index.py",
  "portfolio-snapshot.py",
  "news-correlation.py",
  "correlation-regime.py",
  "datawrapper-index.py",
  "mcp-cli.py",
] as const;

export type AllowedScript = (typeof ALLOWED_SCRIPTS)[number];

export interface ScriptResult {
  ok: boolean;
  script: string;
  returncode: number;
  stdout: string;
  stderr: string;
  error?: string;
}

/** Where the shared Python core lives, most specific source first. */
export function resolveScriptsDir(): string {
  const explicit = process.env.ADJACENT_PLUGIN_SCRIPTS;
  if (explicit) return resolve(explicit);

  const root = process.env.ADJACENT_PLUGIN_ROOT;
  if (root) return join(resolve(root), "scripts");

  // Bundled with the package: dist/ or src/ -> ../runtime/scripts
  const bundled = resolve(MODULE_DIR, "..", "runtime", "scripts");
  if (existsSync(bundled)) return bundled;

  // Developing inside the monorepo: package dir -> ../../scripts
  return resolve(MODULE_DIR, "..", "..", "scripts");
}

/** Writable directory for logs and chart output. Never inside node_modules. */
export function resolveStateDir(): string {
  const explicit = process.env.ADJACENT_STATE_DIR;
  const dir = explicit ? resolve(explicit) : join(process.cwd(), ".adjacent");
  mkdirSync(dir, { recursive: true });
  return dir;
}

export function resolvePython(): string {
  return process.env.ADJACENT_PYTHON || "python3";
}

export function scriptPath(script: AllowedScript): string {
  if (!ALLOWED_SCRIPTS.includes(script)) {
    throw new Error(`script is not allowlisted: ${script}`);
  }
  return join(resolveScriptsDir(), script);
}

/** True when the shared core is present and runnable. */
export function runtimeIsInstalled(): boolean {
  return existsSync(join(resolveScriptsDir(), "capability-status.py"));
}

export async function runScript(
  script: AllowedScript,
  args: string[],
  options: { timeoutMs?: number } = {},
): Promise<ScriptResult> {
  const timeoutMs = options.timeoutMs ?? 120_000;
  let path: string;
  try {
    path = scriptPath(script);
  } catch (err) {
    return {
      ok: false,
      script,
      returncode: -1,
      stdout: "",
      stderr: "",
      error: err instanceof Error ? err.message : String(err),
    };
  }

  if (!existsSync(path)) {
    return {
      ok: false,
      script,
      returncode: -1,
      stdout: "",
      stderr: "",
      error:
        `shared core not found at ${path}. Reinstall the plugin, or set ` +
        "ADJACENT_PLUGIN_ROOT to a checkout. Run adjacent_doctor for details.",
    };
  }

  return new Promise((resolveResult) => {
    const child = spawn(resolvePython(), [path, ...args], {
      shell: false,
      env: { ...process.env, ADJACENT_STATE_DIR: resolveStateDir() },
    });

    let stdout = "";
    let stderr = "";
    let settled = false;

    const timer = setTimeout(() => {
      child.kill("SIGKILL");
    }, timeoutMs);

    const finish = (result: ScriptResult) => {
      if (settled) return;
      settled = true;
      clearTimeout(timer);
      resolveResult(result);
    };

    child.stdout.on("data", (chunk) => (stdout += String(chunk)));
    child.stderr.on("data", (chunk) => (stderr += String(chunk)));

    child.on("error", (err) =>
      finish({ ok: false, script, returncode: -1, stdout, stderr, error: err.message }),
    );

    child.on("close", (code) =>
      finish({
        ok: code === 0,
        script,
        returncode: code ?? -1,
        stdout,
        stderr,
        ...(code === 0 ? {} : { error: stderr.trim().split("\n").pop() || `exit ${code}` }),
      }),
    );
  });
}

/** Run a script that emits JSON on stdout and return the parsed payload. */
export async function runJsonScript<T = unknown>(
  script: AllowedScript,
  args: string[],
  options: { timeoutMs?: number } = {},
): Promise<{ ok: boolean; data?: T; error?: string; stderr?: string }> {
  const result = await runScript(script, args, options);
  if (!result.ok) {
    return { ok: false, error: result.error, stderr: result.stderr };
  }
  try {
    return { ok: true, data: JSON.parse(result.stdout) as T };
  } catch {
    return {
      ok: false,
      error: `${script} did not emit JSON`,
      stderr: result.stdout.slice(0, 400),
    };
  }
}
