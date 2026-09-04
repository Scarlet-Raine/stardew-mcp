"""Async WebSocket client that talks to the Stardew Valley mod.

Port of Go `mcp-server/main.go` GameClient: connection management, keepalive,
reconnection, and per-command response correlation over the JSON wire protocol.
"""
from __future__ import annotations

import asyncio
import logging
import uuid
from typing import Dict, Optional

from .config import Config
from .models import GameState, WebSocketMessage, WebSocketResponse, game_state_from_dict

logger = logging.getLogger("stardew_bridge.client")


class NotConnectedError(RuntimeError):
    """Raised when an action requires an active game connection."""


class GameClient:
    """Manages the WebSocket connection to the running Stardew Valley mod."""

    def __init__(self, config: Config | None = None) -> None:
        self.config = config or Config()
        self._conn = None
        self._connected = False
        self._state: Optional[GameState] = None
        self._pending: Dict[str, asyncio.Future] = {}
        self._write_lock = asyncio.Lock()
        self._tasks: list = []
        self._closed = False
        self._run_task: Optional[asyncio.Task] = None

    # ------------------------------------------------------------------ #
    # Connection lifecycle
    # ------------------------------------------------------------------ #
    async def connect(self) -> None:
        """Establish the connection (used by the auto-reconnect loop)."""
        try:
            from websockets.asyncio.client import connect
        except ImportError:  # older websockets
            from websockets import connect  # type: ignore

        conn = await connect(self.config.ws_url, open_timeout=self.config.connect_timeout)
        self._conn = conn
        self._connected = True
        logger.info("Connected to Stardew Valley at %s", self.config.ws_url)
        self._tasks.append(asyncio.create_task(self._listen()))
        self._tasks.append(asyncio.create_task(self._keepalive()))
        await self.request_state()
        # Wait for the first state snapshot so callers see fresh state immediately.
        deadline = asyncio.get_event_loop().time() + self.config.connect_timeout
        while self._state is None and asyncio.get_event_loop().time() < deadline:
            await asyncio.sleep(0.05)

    async def run(self) -> None:
        """Auto-reconnect loop. Blocks forever until stopped."""
        while not self._closed:
            try:
                await self.connect()
                await self._wait_until_disconnected()
            except asyncio.CancelledError:
                return
            except Exception as exc:  # noqa: BLE001
                logger.info("Connection failed (%s) — retrying in %ss", exc, self.config.reconnect_delay)
            if self._closed:
                return
            await asyncio.sleep(self.config.reconnect_delay)

    async def _wait_until_disconnected(self) -> None:
        while not self._closed and self._connected:
            await asyncio.sleep(0.5)

    async def close(self) -> None:
        self._closed = True
        self._connected = False
        if self._conn is not None:
            await self._conn.close()
        for fut in self._pending.values():
            if not fut.done():
                fut.set_exception(NotConnectedError("client closed"))
        self._pending.clear()
        for t in self._tasks:
            t.cancel()
        self._tasks.clear()

    # ------------------------------------------------------------------ #
    # Listener + keepalive
    # ------------------------------------------------------------------ #
    async def _listen(self) -> None:
        conn = self._conn
        try:
            async for raw in conn:
                self._handle_raw(raw)
        except Exception as exc:  # noqa: BLE001
            if not self._closed:
                logger.warning("WebSocket read error: %s", exc)
                await self._mark_disconnected()
        finally:
            if not self._closed:
                await self._mark_disconnected()

    async def _mark_disconnected(self) -> None:
        self._connected = False
        if self._conn is not None:
            try:
                await self._conn.close()
            except Exception:  # noqa: BLE001
                pass

    async def _keepalive(self) -> None:
        while not self._closed and self._connected:
            await asyncio.sleep(self.config.keepalive_interval)
            if self._connected:
                try:
                    await self.send_ping()
                except Exception as exc:  # noqa: BLE001
                    logger.warning("Ping failed: %s", exc)
                    await self._mark_disconnected()
                    break

    def _handle_raw(self, raw) -> None:
        try:
            import json

            data = json.loads(raw)
        except Exception:  # noqa: BLE001
            logger.warning("Failed to parse message: %r", raw)
            return
        resp = WebSocketResponse.model_validate(data)
        msg_type = (resp.type or "").lower()
        if msg_type == "state":
            self._state = game_state_from_dict(resp.data)
        elif msg_type == "response":
            self._complete_response(resp)
        elif msg_type == "pong":
            pass
        elif msg_type == "error":
            logger.warning("Error from game: %s", resp.message)
        else:
            logger.debug("Unknown message type: %s", resp.type)

    def _complete_response(self, resp: WebSocketResponse) -> None:
        if not resp.id:
            return
        fut = self._pending.pop(resp.id, None)
        if fut is not None and not fut.done():
            fut.set_result(resp)

    # ------------------------------------------------------------------ #
    # Sending
    # ------------------------------------------------------------------ #
    async def _send(self, message: WebSocketMessage) -> None:
        if self._conn is None or not self._connected:
            raise NotConnectedError("not connected to game")
        async with self._write_lock:
            await self._conn.send(message.model_dump_json(by_alias=True))

    async def send_ping(self) -> None:
        msg = WebSocketMessage(id=str(uuid.uuid4()), type="ping")
        await self._send(msg)

    async def request_state(self) -> Optional[GameState]:
        msg = WebSocketMessage(id=str(uuid.uuid4()), type="get_state")
        await self._send(msg)
        return self._state

    async def send_command(
        self,
        action: str,
        params: Optional[dict] = None,
        timeout: float | None = None,
    ) -> WebSocketResponse:
        timeout = timeout or self.config.command_timeout
        cmd_id = str(uuid.uuid4())
        msg = WebSocketMessage(id=cmd_id, type="command", action=action, params=params or {})
        fut: asyncio.Future = asyncio.get_event_loop().create_future()
        self._pending[cmd_id] = fut
        try:
            await self._send(msg)
        except Exception:
            self._pending.pop(cmd_id, None)
            raise
        try:
            return await asyncio.wait_for(fut, timeout=timeout)
        except asyncio.TimeoutError:
            self._pending.pop(cmd_id, None)
            raise TimeoutError(f"timeout waiting for response to '{action}'") from None

    # ------------------------------------------------------------------ #
    # State access
    # ------------------------------------------------------------------ #
    def state(self) -> Optional[GameState]:
        return self._state

    @property
    def is_connected(self) -> bool:
        return self._connected