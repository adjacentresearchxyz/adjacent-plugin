#!/usr/bin/env python3
"""rebalance-index.py - place exchange orders from a compact plan, for any index.

Reads a compact plan via --plan <path> or stdin; the plan is always
supplied by the caller, never derived from the catalog. The plan shape
is documented in the adjacent-direct-index and <exchange>-direct-indexing
skills:

    {
      "index": "<slug>",
      "ts": "YYYY-MM-DDTHH:MM:SSZ",
      "sells": [{"market_id": "...", "size": <n>, "mid": <m>}, ...],
      "buys":  [{"market_id": "...", "size": <n>, "mid": <m>}, ...]
    }

Each order is dispatched to the exchange adapter in EXCHANGES. Today
only `kalshi` ships; the rest of the dispatcher is generic. Each
adapter returns `(results, missing_env_list)` - the missing list is the
source of truth for env-var probes.

Fail-closed safety: refuses to place orders unless
data/adjacent_direct_indices.json has _schema._placeholders.value:
false. Replace each placeholder via
scripts/portfolio-snapshot.py --index <slug> --json, then flip the flag.

Refuses to run on weekends (Sat / Sun UTC at placement time) unless
--allow-weekend is passed. --dry-run and --json bypass the weekend gate
so users can preview weekend plans.
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import urllib.error
import urllib.request

from _paths import data_dir

KALSHI_BASE = os.environ.get("KALSHI_BASE", "https://api.kalshi.com")
KALSHI_API_KEY = os.environ.get("KALSHI_API_KEY", "")
KALSHI_PASSPHRASE = os.environ.get("KALSHI_PASSPHRASE", "")
KALSHI_RSA_KEY_PATH = os.environ.get("KALSHI_RSA_KEY_PATH", "")


# ----- exchange: kalshi -----

def _kalshi_load_key():
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.backends import default_backend
    raw = Path(KALSHI_RSA_KEY_PATH).read_bytes()
    pw = KALSHI_PASSPHRASE.encode("utf-8") if KALSHI_PASSPHRASE else None
    return serialization.load_pem_private_key(raw, password=pw, backend=default_backend())


def _kalshi_sign(private_key, message: bytes) -> str:
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.asymmetric import padding
    sig = private_key.sign(
        message,
        padding.PSS(mgf=padding.MGF1(hashes.SHA256()), salt_length=padding.PSS.DIGEST_LENGTH),
        hashes.SHA256(),
    )
    return base64.b64encode(sig).decode("ascii")


def _kalshi_order(action: str, leg: dict[str, Any], index_slug: str) -> dict[str, Any]:
    market_id = leg["market_id"]
    if ":" in market_id:
        _, raw = market_id.split(":", 1)
    else:
        _, raw = "kalshi", market_id
    yes_price = max(1, min(99, round(leg["mid"] * 100)))
    return {
        "ticker": raw,
        "action": action,
        "side": "yes",
        "count": leg["size"],
        "type": "limit",
        "yes_price": yes_price if action == "buy" else max(1, yes_price - 1),
        "client_order_id": f"{index_slug}-{int(time.time())}-{raw}",
    }


def _kalshi_send(
    method: str,
    path: str,
    body: dict[str, Any],
    private_key,
) -> dict[str, Any]:
    ts = str(int(time.time() * 1000))
    body_bytes = json.dumps(body, separators=(",", ":")).encode("utf-8") if body else b""
    sig_msg = (ts + method + path).encode("utf-8") + body_bytes
    signature = _kalshi_sign(private_key, sig_msg)
    req = urllib.request.Request(
        KALSHI_BASE + path,
        data=body_bytes if body else None,
        method=method,
        headers={
            "Content-Type": "application/json",
            "KALSHI-ACCESS-KEY": KALSHI_API_KEY,
            "KALSHI-ACCESS-TIMESTAMP": ts,
            "KALSHI-ACCESS-SIGNATURE": signature,
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        return {"error": str(e), "status": e.code, "body": e.read().decode("utf-8", errors="replace")}


def kalshi_adapter(plan: dict[str, Any]) -> tuple[dict[str, list], list[str]]:
    missing: list[str] = []
    if not KALSHI_API_KEY:
        missing.append("KALSHI_API_KEY")
    if not KALSHI_RSA_KEY_PATH or not Path(KALSHI_RSA_KEY_PATH).exists():
        missing.append("KALSHI_RSA_KEY_PATH")
    if missing:
        return {"sells": [], "buys": [], "errors": [{"reason": f"missing env: {','.join(missing)}"}]}, missing
    out: dict[str, list] = {"sells": [], "buys": [], "errors": []}
    private_key = _kalshi_load_key()
    for leg in plan.get("sells", []):
        out["sells"].append(
            _kalshi_send(
                "POST",
                "/v2/portfolio/orders",
                _kalshi_order("sell", leg, plan["index"]),
                private_key,
            )
        )
    for leg in plan.get("buys", []):
        out["buys"].append(
            _kalshi_send(
                "POST",
                "/v2/portfolio/orders",
                _kalshi_order("buy", leg, plan["index"]),
                private_key,
            )
        )
    return out, []


# ----- registry -----

EXCHANGES = {
    "kalshi": kalshi_adapter,
    # future adapters plug in here with the (plan) -> (results, missing_env) shape
}


# ----- catalog and plan helpers -----

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--index", required=True, help="catalog index slug")
    p.add_argument("--exchange", default="kalshi", help="exchange adapter name")
    p.add_argument("--plan", help="path to a compact plan JSON")
    p.add_argument("--dry-run", action="store_true", help="print plan, place no orders")
    p.add_argument("--json", action="store_true", help="emit resolved plan as JSON only")
    p.add_argument("--allow-weekend", action="store_true", help="bypass the weekday-only default")
    return p.parse_args()


def is_weekend_utc() -> bool:
    return datetime.now(timezone.utc).weekday() >= 5  # 5 = Sat, 6 = Sun


def load_plan(args: argparse.Namespace) -> dict[str, Any]:
    if args.plan:
        return json.loads(Path(args.plan).read_text(encoding="utf-8"))
    if not sys.stdin.isatty():
        raw = sys.stdin.read()
        if raw.strip():
            return json.loads(raw)
    raise SystemExit("error: no plan provided; pass --plan <path> or pipe via stdin")


def catalog_check() -> tuple[bool, str]:
    p = data_dir() / "adjacent_direct_indices.json"
    safe = False
    try:
        doc = json.loads(p.read_text(encoding="utf-8"))
        if isinstance(doc, dict):
            schema = doc.get("_schema")
            if isinstance(schema, dict):
                placeholders = schema.get("_placeholders")
                if isinstance(placeholders, dict):
                    safe = placeholders.get("value") is False
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        safe = False
    return not safe, str(p.resolve())


def main() -> int:
    args = parse_args()
    if args.exchange not in EXCHANGES:
        raise SystemExit(f"error: unknown --exchange {args.exchange!r}; known: {','.join(sorted(EXCHANGES))}")
    placing = not (args.dry_run or args.json)
    if placing and not args.allow_weekend and is_weekend_utc():
        raise SystemExit(
            "refusing: today is a weekend (UTC); pass --allow-weekend to override "
            "or wait until Monday 16:00 ET"
        )
    plan = load_plan(args)
    if plan.get("index") != args.index:
        raise SystemExit(
            f"error: plan index {plan.get('index')!r} does not match --index {args.index!r}"
        )
    plan["_placed_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    if args.json or args.dry_run:
        json.dump(plan, sys.stdout, indent=2)
        sys.stdout.write("\n")
        return 0
    refuse, catalog_path = catalog_check()
    if refuse:
        raise SystemExit(
            "refusing: "
            f"{catalog_path} "
            "is not confirmed `_schema._placeholders.value == false`. "
            "Replace each `example:INDEX-*` market_id with one from "
            "`scripts/portfolio-snapshot.py --index <slug> --json`, then set "
            "`_schema._placeholders.value` to `false` and re-run."
        )
    results, missing = EXCHANGES[args.exchange](plan)
    if missing:
        raise SystemExit(f"error: missing exchange env vars for {args.exchange}: {','.join(missing)}")
    json.dump(results, sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
