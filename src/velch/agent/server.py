"""MCP over stdio: the form an AI client actually talks to.

Two framings are accepted, because clients disagree about which one this transport uses:
newline-delimited JSON (one object per line) and LSP-style ``Content-Length`` headers.  Both
are read on the same stream, so the transport cannot be the reason a client fails to connect.

The server holds no state of its own: every call is a short read or a write-to-disk followed
by a detached child process, which is why it can start in 78 ms and never needs a restart.
"""

from __future__ import annotations

import io
import json
import sys
from typing import Any, TextIO

from velch import __version__
from .tools import call_tool, manifest

PROTOCOL_VERSION = "2024-11-05"


def _result(request_id: Any, payload: dict[str, Any]) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": request_id, "result": payload}


def _error(request_id: Any, code: int, message: str) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": request_id, "error": {"code": code, "message": message}}


def handle(request: dict[str, Any]) -> dict[str, Any] | None:
    """Answer one JSON-RPC request; return None for notifications."""
    method = request.get("method")
    request_id = request.get("id")
    params = request.get("params") or {}
    if method == "initialize":
        return _result(request_id, {
            "protocolVersion": PROTOCOL_VERSION,
            "capabilities": {"tools": {"listChanged": False}},
            "serverInfo": {"name": "velch", "version": __version__},
        })
    if method in {"notifications/initialized", "initialized"}:
        return None
    if method == "ping":
        return _result(request_id, {})
    if method == "tools/list":
        return _result(request_id, manifest())
    if method == "tools/call":
        name = params.get("name")
        envelope = call_tool(str(name), params.get("arguments") or {})
        is_error = not envelope.get("ok", False)
        return _result(request_id, {
            "content": [{"type": "text", "text": json.dumps(envelope, ensure_ascii=False)}],
            "isError": is_error,
        })
    if method == "resources/list":
        return _result(request_id, {"resources": []})
    if method == "prompts/list":
        return _result(request_id, {"prompts": []})
    if request_id is None:
        return None
    return _error(request_id, -32601, f"unsupported method: {method}")


def _read_message(stream: TextIO) -> dict[str, Any] | None:
    """Read one message, accepting both framings."""
    length: int | None = None
    while True:
        line = stream.readline()
        if not line:
            return None
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.lower().startswith("content-length:"):
            try:
                length = int(stripped.split(":", 1)[1].strip())
            except ValueError:
                return None
            continue
        if stripped.lower().startswith("content-type:"):
            continue
        if length is not None:
            body = stream.read(length)
            return json.loads(body) if body else None
        return json.loads(stripped)


def serve(stdin: TextIO | None = None, stdout: TextIO | None = None) -> int:
    source = stdin or io.TextIOWrapper(sys.stdin.buffer, encoding="utf-8", newline="\n")
    sink = stdout or io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", newline="\n")
    while True:
        try:
            request = _read_message(source)
        except json.JSONDecodeError:
            response = _error(None, -32700, "parse error")
            sink.write(json.dumps(response, ensure_ascii=False) + "\n")
            sink.flush()
            continue
        if request is None:
            return 0
        response = handle(request)
        if response is not None:
            sink.write(json.dumps(response, ensure_ascii=False) + "\n")
            sink.flush()


def main(argv: list[str] | None = None) -> int:
    return serve()


if __name__ == "__main__":
    raise SystemExit(main())
