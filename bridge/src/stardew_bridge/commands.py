"""High-level command execution producing agent-facing result strings.

Port of the response-handling in Go `copilot_agent.go`: sends a game command and
interprets the response into a concise string an agent can act on.
"""
from __future__ import annotations

import logging
from typing import Any, Optional

from .ws_client import GameClient, NotConnectedError

logger = logging.getLogger("stardew_bridge.commands")


class GameCommander:
    """Wraps a GameClient and turns commands into result strings for agents."""

    def __init__(self, client: GameClient) -> None:
        self.client = client

    async def execute(self, action: str, **params: Any) -> str:
        try:
            resp = await self.client.send_command(action, params or None)
        except NotConnectedError:
            return "Game disconnected"
        except TimeoutError:
            return f"Command '{action}' timed out waiting for the game."
        except Exception as exc:  # noqa: BLE001
            logger.warning("Command %s failed: %s", action, exc)
            return f"Command '{action}' failed: {exc}"
        if resp is None:
            return f"Command '{action}' returned no response."
        message = resp.message or ""
        if resp.success:
            return message
        if message:
            return f"Rejected: {message}"
        return f"Command '{action}' was not successful."

    async def execute_parts(self, action: str, params: dict | None = None) -> "RespParts":
        try:
            resp = await self.client.send_command(action, params or None)
        except NotConnectedError:
            return RespParts(success=False, message="Game disconnected")
        except TimeoutError:
            return RespParts(success=False, message=f"Command '{action}' timed out.")
        resp = resp or RespParts(success=False, message="No response")
        return RespParts(
            success=bool(resp.success),
            message=resp.message or "",
            data=resp.data,
        )


class RespParts:
    """Structured view of a command response (message + success + data)."""

    __slots__ = ("success", "message", "data")

    def __init__(self, success: bool, message: str = "", data: Optional[Any] = None) -> None:
        self.success = success
        self.message = message
        self.data = data

    def __str__(self) -> str:
        return self.message