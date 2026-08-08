/**
 * Copy the shared runtime into the package so a clean install is
 * self-sufficient: no repo checkout, no skill copying, no path env vars.
 *
 * The bundled layout mirrors the repo layout on purpose. scripts/_paths.py
 * resolves the plugin root as scripts/.. , so runtime/scripts + runtime/data
 * makes data_dir() land on the bundled catalogs with no configuration.
 *
 * Runs from prepack, so `npm pack` and `npm publish` always ship a current
 * copy and the sources stay single-homed in the repo root.
 */

import { cpSync, mkdirSync, rmSync, existsSync, writeFileSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const PACKAGE_DIR = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const REPO_ROOT = resolve(PACKAGE_DIR, "..");
const RUNTIME_DIR = join(PACKAGE_DIR, "runtime");

// Source of truth -> bundled destination. The skills path is the canonical
// skill set; the package validator treats it as the parity baseline.
// assets/fonts ships the OFL-licensed Inter and IBM Plex Mono static TTFs
// so chart output is deterministic in a clean install with no system fonts.
const SOURCES = [
  { from: join(REPO_ROOT, "scripts"), to: join(RUNTIME_DIR, "scripts") },
  { from: join(REPO_ROOT, "data"), to: join(RUNTIME_DIR, "data") },
  { from: join(REPO_ROOT, "plugins", "adjacent", "skills"), to: join(RUNTIME_DIR, "skills") },
  { from: join(REPO_ROOT, "assets", "fonts"), to: join(RUNTIME_DIR, "assets", "fonts") },
];

// tools.json is a build/test-time catalog (it lists every host, including
// foreign ones); it is never read at runtime, so it must not ship in a
// host package or it trips the foreign-platform-name guard.
const SKIP = new Set(["__pycache__", ".DS_Store", "validate-plugin-packages.py", "tools.json"]);

function main() {
  rmSync(RUNTIME_DIR, { recursive: true, force: true });
  mkdirSync(RUNTIME_DIR, { recursive: true });

  for (const { from, to } of SOURCES) {
    if (!existsSync(from)) {
      throw new Error(`bundle-runtime: missing source directory ${from}`);
    }
    cpSync(from, to, {
      recursive: true,
      filter: (src) => !SKIP.has(src.split("/").pop() ?? ""),
    });
  }

  // Marks the bundled tree so the resolver can tell a real bundle from a
  // stale directory, and records what produced it.
  writeFileSync(
    join(RUNTIME_DIR, "BUNDLE.json"),
    JSON.stringify({ bundled: SOURCES.map((s) => s.to.replace(RUNTIME_DIR + "/", "")) }, null, 2) + "\n",
    "utf8",
  );

  console.log(`bundle-runtime: wrote ${RUNTIME_DIR}`);
}

main();
