"""Shared Datawrapper API helpers."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any
from urllib import request
from urllib.error import HTTPError


BASE_URL = "https://api.datawrapper.de"


def read_csv(path: str | None) -> bytes:
    if path:
        return Path(path).read_bytes()
    if not sys.stdin.isatty():
        return sys.stdin.buffer.read()
    raise ValueError("no CSV input")


def post(
    api_key: str,
    path: str,
    *,
    body: dict[str, Any] | None = None,
    raw: bytes | None = None,
    content_type: str = "application/json",
) -> dict[str, Any]:
    data = raw if raw is not None else json.dumps(body).encode("utf-8") if body else None
    req = request.Request(
        BASE_URL + path,
        method="POST",
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
        return json.loads(text)
    except json.JSONDecodeError:
        return {"raw": text}
