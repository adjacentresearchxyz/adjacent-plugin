"""Shared read-only HTTP GET helper for Adjacent surfaces.

Used by the public-snapshot, export, and docs workflows. Restricted to
HTTPS Adjacent hosts so an allowlisted script can never be pointed at an
arbitrary origin. Auth via the `apiKey` query param when a key is given.
"""

from __future__ import annotations

from urllib import request
from urllib.error import HTTPError
from urllib.parse import urlparse, urlencode


ALLOWED_HOST_SUFFIX = ".adjacent.markets"
ALLOWED_HOSTS = {"adjacent.markets"}


def _check_host(url: str) -> str:
    parsed = urlparse(url)
    if parsed.scheme != "https":
        raise ValueError("only https URLs are allowed")
    host = parsed.hostname or ""
    if host not in ALLOWED_HOSTS and not host.endswith(ALLOWED_HOST_SUFFIX):
        raise ValueError(f"host not allowed: {host}")
    return host


def get_with_headers(
    url: str, api_key: str | None = None, timeout: int = 20
) -> tuple[int, bytes, dict[str, str]]:
    """GET an Adjacent URL. Returns (status_code, body_bytes, headers).

    Raises ValueError for a disallowed host. HTTP error responses are
    returned as (code, body, headers) rather than raised. Header keys are
    lower-cased so callers can look up ``last-modified`` / ``date`` without
    case juggling.
    """
    _check_host(url)
    if api_key:
        sep = "&" if "?" in url else "?"
        url = f"{url}{sep}{urlencode({'apiKey': api_key})}"
    req = request.Request(
        url,
        method="GET",
        headers={"User-Agent": "adjacent-plugin/0.2", "Accept": "*/*"},
    )
    try:
        with request.urlopen(req, timeout=timeout) as response:
            headers = {key.lower(): value for key, value in response.headers.items()}
            return response.status, response.read(), headers
    except HTTPError as exc:
        headers = {key.lower(): value for key, value in exc.headers.items()} if exc.headers else {}
        return exc.code, exc.read(), headers


def get(url: str, api_key: str | None = None, timeout: int = 20) -> tuple[int, bytes]:
    """GET an Adjacent URL. Returns (status_code, body_bytes)."""
    status, body, _headers = get_with_headers(url, api_key, timeout)
    return status, body
