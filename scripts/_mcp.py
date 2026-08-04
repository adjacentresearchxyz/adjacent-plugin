"""Shared Adjacent MCP client helpers.

A dependency-free JSON-RPC client for the Adjacent MCP streamable-HTTP
transport. Adjacent requires the MCP initialize handshake and returns
Server-Sent Events, so callers must:

1. Accept both ``application/json`` and ``text/event-stream``.
2. Send ``initialize``, capture ``mcp-session-id``, then
   ``notifications/initialized``.
3. Reuse that session for ``tools/call`` / ``tools/list``.
4. Parse SSE ``data:`` frames into JSON-RPC envelopes.

Auth is via the ``apiKey`` URL query param only. With a key the realtime
tier is used; without it the public 15-min-delayed tier.
"""

from __future__ import annotations

import http.client
import json
import ssl
from typing import Any
from urllib.parse import urlencode, urlparse


DEFAULT_HOST = "mcp.adjacent.markets"
DEV_HOST = "mcp.dev.adjacent.markets"
DEFAULT_PORT_TLS = 443
PROTOCOL_VERSION = "2024-11-05"
CLIENT_INFO = {"name": "adjacent-plugin", "version": "0.2"}
ACCEPT = "application/json, text/event-stream"


def build_url(host: str, api_key: str | None, endpoint: str = "/mcp") -> str:
    base = f"https://{host}{endpoint}"
    if api_key:
        sep = "&" if "?" in base else "?"
        base = f"{base}{sep}{urlencode({'apiKey': api_key})}"
    return base


def _parse_sse(body: str) -> list[dict[str, Any]]:
    """Extract JSON-RPC objects from an SSE body (or bare JSON)."""
    text = body.strip()
    if not text:
        return []
    if text.startswith("{") or text.startswith("["):
        try:
            payload = json.loads(text)
        except json.JSONDecodeError:
            payload = None
        if isinstance(payload, dict):
            return [payload]
        if isinstance(payload, list):
            return [item for item in payload if isinstance(item, dict)]

    objects: list[dict[str, Any]] = []
    for line in text.splitlines():
        if not line.startswith("data:"):
            continue
        data = line[5:].strip()
        if not data or data == "[DONE]":
            continue
        try:
            item = json.loads(data)
        except json.JSONDecodeError:
            continue
        if isinstance(item, dict):
            objects.append(item)
    return objects


def _request(
    conn: http.client.HTTPConnection | http.client.HTTPSConnection,
    path: str,
    body: dict[str, Any],
    session_id: str | None = None,
) -> tuple[int, dict[str, str | None], str]:
    headers = {
        "Content-Type": "application/json",
        "Accept": ACCEPT,
    }
    if session_id:
        headers["Mcp-Session-Id"] = session_id
    payload = json.dumps(body).encode("utf-8")
    conn.request("POST", path, body=payload, headers=headers)
    resp = conn.getresponse()
    raw = resp.read().decode("utf-8")
    response_headers = {key.lower(): value for key, value in resp.getheaders()}
    return resp.status, response_headers, raw


def _open_connection(parsed) -> http.client.HTTPConnection | http.client.HTTPSConnection:
    is_tls = parsed.scheme == "https"
    if is_tls:
        ctx = ssl.create_default_context()
        return http.client.HTTPSConnection(
            parsed.hostname,
            parsed.port or DEFAULT_PORT_TLS,
            context=ctx,
            timeout=20,
        )
    return http.client.HTTPConnection(parsed.hostname, parsed.port or 80, timeout=20)


class McpError(RuntimeError):
    """Raised when a tools/call envelope carries an error instead of data."""


def host_for_tier(tier: str) -> str:
    """Map a tier label to its MCP host. Anything but 'prod' means dev."""
    return DEFAULT_HOST if tier == "prod" else DEV_HOST


def content_json(envelope: dict) -> Any:
    """Unwrap a tools/call envelope into the payload the tool returned.

    MCP wraps tool output in ``result.content[]`` text frames that hold
    JSON. Callers want the data, not the transport, so this walks the
    frames and returns the first decodable payload. Text that is not JSON
    comes back as text; a transport or tool error raises.
    """
    if not isinstance(envelope, dict):
        raise McpError("MCP response was not an object")
    if "error" in envelope:
        error = envelope["error"]
        message = error.get("message") if isinstance(error, dict) else str(error)
        raise McpError(str(message or "MCP call failed"))

    result = envelope.get("result")
    if not isinstance(result, dict):
        raise McpError("MCP response carried no result")

    content = result.get("content")
    if isinstance(content, list):
        for item in content:
            if not isinstance(item, dict) or item.get("type") != "text":
                continue
            text = item.get("text", "")
            try:
                payload = json.loads(text)
            except (json.JSONDecodeError, TypeError):
                if result.get("isError"):
                    raise McpError(str(text)[:300])
                return text
            if result.get("isError"):
                raise McpError(str(payload)[:300])
            return payload

    if result.get("isError"):
        raise McpError(str(result)[:300])
    if "structuredContent" in result:
        return result["structuredContent"]
    return result


def fetch(
    tool: str,
    args: dict,
    tier: str = "dev",
    api_key: str | None = None,
    endpoint: str = "/mcp",
) -> Any:
    """Call one MCP tool on the given tier and return its unwrapped payload."""
    return content_json(call(host_for_tier(tier), api_key, endpoint, tool, args))


def call(
    host: str,
    api_key: str | None,
    endpoint: str,
    tool: str,
    args: dict,
) -> dict:
    """Call one Adjacent MCP tool with a full session handshake.

    Returns the JSON-RPC envelope for the tools/call response. On transport
    or protocol failure returns ``{"error": ...}`` so callers can keep a
    single shape.
    """
    url = build_url(host, api_key, endpoint)
    parsed = urlparse(url)
    path = parsed.path + ("?" + parsed.query if parsed.query else "")
    conn = _open_connection(parsed)
    try:
        status, headers, raw = _request(
            conn,
            path,
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": PROTOCOL_VERSION,
                    "capabilities": {},
                    "clientInfo": CLIENT_INFO,
                },
            },
        )
        if status >= 400:
            return {
                "error": {
                    "code": status,
                    "message": f"initialize HTTP {status}",
                    "data": raw[:500],
                }
            }
        session_id = headers.get("mcp-session-id")
        init_objects = _parse_sse(raw)
        if init_objects and "error" in init_objects[0]:
            return init_objects[0]

        # Required by streamable HTTP after a successful initialize.
        _request(
            conn,
            path,
            {"jsonrpc": "2.0", "method": "notifications/initialized"},
            session_id=session_id,
        )

        status, _headers, raw = _request(
            conn,
            path,
            {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/call",
                "params": {"name": tool, "arguments": args},
            },
            session_id=session_id,
        )
        if status >= 400:
            return {
                "error": {
                    "code": status,
                    "message": f"tools/call HTTP {status}",
                    "data": raw[:500],
                }
            }
        objects = _parse_sse(raw)
        if not objects:
            return {"error": {"message": "empty MCP response", "data": raw[:500]}}
        # Prefer the last frame that carries a result or error for our id.
        for obj in reversed(objects):
            if "result" in obj or "error" in obj:
                return obj
        return objects[-1]
    except Exception as exc:  # network / SSL / decode
        return {"error": {"message": str(exc)}}
    finally:
        try:
            conn.close()
        except Exception:
            pass
