"""HTTP adapter exposing the tool registry for OpenAI-style / generic pipelines.

Endpoints:
- GET  /v1/tools  -> list of OpenAI-compatible function schemas
- POST /v1/tool   -> {"name": "...", "arguments": {...}} -> result string

Runs as an asyncio web server using stdlib http.server (no extra deps) or can be
queried directly via the Python API.
"""
from __future__ import annotations

import asyncio
import json
import logging
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread
from typing import Any

from .agent import make_tool_context
from .config import Config
from .tools.base import ToolRegistry, ToolContext
from .ws_client import GameClient

logger = logging.getLogger("stardew_bridge.http")


class _Handler(BaseHTTPRequestHandler):
    registry: ToolRegistry = None
    ctx: ToolContext = None

    def log_message(self, fmt, *args):  # silence default logging
        logger.debug(fmt, *args)

    def _json(self, code: int, payload: Any) -> None:
        body = json.dumps(payload).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):  # noqa: N802
        if self.path.split("?")[0].rstrip("/") == "/v1/tools":
            self._json(200, {"object": "list", "data": self.registry.openai_functions()})
        else:
            self._json(404, {"error": "not found"})

    def do_POST(self):  # noqa: N802
        if self.path.split("?")[0].rstrip("/") != "/v1/tool":
            self._json(404, {"error": "not found"})
            return
        length = int(self.headers.get("Content-Length") or 0)
        try:
            payload = json.loads(self.rfile.read(length) or b"{}")
            name = payload.get("name")
            args = payload.get("arguments") or {}
        except Exception as exc:  # noqa: BLE001
            self._json(400, {"error": f"bad request: {exc}"})
            return
        if not name:
            self._json(400, {"error": "missing 'name'"})
            return
        result = asyncio.run(self.registry.call(name, args, self.ctx))
        self._json(200, {"name": name, "result": result})


class HttpAdapter:
    def __init__(self, client: GameClient, registry: ToolRegistry, config: Config) -> None:
        self.client = client
        self.registry = registry
        self.config = config
        self.ctx = make_tool_context(client, registry, config)
        self._server: ThreadingHTTPServer | None = None

    def start_sync(self, host: str | None = None, port: int | None = None) -> ThreadingHTTPServer:
        host = host or self.config.openai_host
        port = port or self.config.openai_port
        _Handler.registry = self.registry
        _Handler.ctx = self.ctx
        srv = ThreadingHTTPServer((host, port), _Handler)
        self._server = srv
        thread = Thread(target=srv.serve_forever, daemon=True, name="stardew-http")
        thread.start()
        logger.info("HTTP adapter listening on http://%s:%d (GET /v1/tools, POST /v1/tool)",
                    host, port)
        return srv

    def stop(self) -> None:
        if self._server is not None:
            self._server.shutdown()
            self._server.server_close()


async def serve(
    client: GameClient,
    registry: ToolRegistry,
    config: Config,
    host: str | None = None,
    port: int | None = None,
) -> None:
    adapter = HttpAdapter(client, registry, config)
    adapter.start_sync(host, port)
    # keep the (async) process alive
    try:
        while True:
            await asyncio.sleep(3600)
    except asyncio.CancelledError:
        adapter.stop()
        raise