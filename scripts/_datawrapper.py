"""Shared Datawrapper API helpers."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any
from urllib import request
from urllib.error import HTTPError

from adjacent_chart_style import FONTS, PALETTE, SERIES


BASE_URL = "https://api.datawrapper.de"


def read_csv(path: str | None) -> bytes:
    if path:
        return Path(path).read_bytes()
    if not sys.stdin.isatty():
        return sys.stdin.buffer.read()
    raise ValueError("no CSV input")


def _request(
    api_key: str,
    path: str,
    *,
    method: str,
    body: dict[str, Any] | None = None,
    raw: bytes | None = None,
    content_type: str = "application/json",
) -> dict[str, Any]:
    data = raw if raw is not None else json.dumps(body).encode("utf-8") if body else None
    req = request.Request(
        BASE_URL + path,
        method=method,
        data=data,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": content_type,
            "User-Agent": "adjacent-plugin/0.2",
        },
    )
    try:
        with request.urlopen(req, timeout=20) as response:
            text = response.read().decode("utf-8")
    except HTTPError as exc:
        return {
            "error": exc.code,
            "body": exc.read().decode("utf-8", errors="replace"),
        }
    try:
        return json.loads(text) if text else {"ok": True}
    except json.JSONDecodeError:
        return {"raw": text}


def post(
    api_key: str,
    path: str,
    *,
    body: dict[str, Any] | None = None,
    raw: bytes | None = None,
    content_type: str = "application/json",
) -> dict[str, Any]:
    return _request(
        api_key,
        path,
        method="POST",
        body=body,
        raw=raw,
        content_type=content_type,
    )


def patch(
    api_key: str,
    path: str,
    body: dict[str, Any],
) -> dict[str, Any]:
    """PATCH chart metadata using the same authenticated API contract."""
    return _request(api_key, path, method="PATCH", body=body)


def adjacent_metadata(
    *,
    title: str,
    intro: str,
    columns: dict[str, dict[str, str]] | None = None,
) -> dict[str, Any]:
    """Return the required Adjacent metadata for every Datawrapper chart."""
    metadata: dict[str, Any] = {
        "describe": {
            "intro": intro,
            "source-name": "Adjacent",
        },
        "visualize": {
            "base-color": PALETTE["ink"],
            "background": PALETTE["canvas"],
            "plot-background": PALETTE["canvas"],
            "grid-color": PALETTE["grid"],
            "color-range": SERIES,
            "font-family": ", ".join(FONTS["main"]),
        },
    }
    if columns:
        metadata["data"] = {"columns": columns}
    return {"title": title, "metadata": metadata}


def brand_chart(
    api_key: str,
    chart_id: str,
    *,
    title: str,
    intro: str,
    columns: dict[str, dict[str, str]] | None = None,
) -> dict[str, Any]:
    """Apply Adjacent metadata and fail closed if styling is rejected."""
    result = patch(
        api_key,
        f"/v3/charts/{chart_id}",
        adjacent_metadata(title=title, intro=intro, columns=columns),
    )
    if "error" in result:
        return {"error": result["error"], "body": result.get("body", "")}
    return {"ok": True}
