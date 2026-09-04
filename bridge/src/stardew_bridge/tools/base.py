"""Declarative tool registry.

Each tool is defined once (name, description, Pydantic params model, async handler)
and can be surfaced through multiple interfaces (MCP, OpenAI function calling,
or direct calls from the autonomous agent).
"""
from __future__ import annotations

import inspect
import logging
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Optional

from pydantic import BaseModel, ValidationError

from ..brain import Brain
from ..commands import GameCommander
from ..config import Config
from ..ws_client import GameClient

logger = logging.getLogger("stardew_bridge.tools")


@dataclass
class ToolContext:
    """Everything handlers need to act on the game."""

    client: GameClient
    commander: GameCommander
    brain: Brain
    config: Config

    def state(self):
        return self.brain.state()


Handler = Callable[[ToolContext, BaseModel], Awaitable[str]]


@dataclass
class ToolSpec:
    name: str
    description: str
    params: type[BaseModel]
    handler: Handler

    def __post_init__(self) -> None:
        if not (inspect.iscoroutinefunction(self.handler)):
            raise TypeError(f"Handler for tool '{self.name}' must be an async function")


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, ToolSpec] = {}

    def add(self, tool: ToolSpec) -> None:
        if tool.name in self._tools:
            raise ValueError(f"Duplicate tool: {tool.name}")
        self._tools[tool.name] = tool

    def get(self, name: str) -> Optional[ToolSpec]:
        return self._tools.get(name)

    def names(self) -> list[str]:
        return sorted(self._tools)

    def all(self) -> list[ToolSpec]:
        return [self._tools[n] for n in self.names()]

    # ------------------------------------------------------------------ #
    # Execution
    # ------------------------------------------------------------------ #
    async def call(self, name: str, args: dict, ctx: ToolContext) -> str:
        tool = self.get(name)
        if tool is None:
            return f"Unknown tool: {name}"
        try:
            params = tool.params.model_validate(args)
        except ValidationError as exc:
            return f"Invalid arguments for {name}: {exc.errors()}"
        try:
            logger.info("[TOOL CALL] %s %s", name, args)
            result = await tool.handler(ctx, params)
            logger.info("[TOOL RESULT] %s -> %s", name, result)
            return result
        except Exception as exc:  # noqa: BLE001
            logger.exception("Tool %s raised", name)
            return f"Tool {name} failed: {exc}"

    # ------------------------------------------------------------------ #
    # OpenAI-compatible function schema
    # ------------------------------------------------------------------ #
    def openai_functions(self) -> list[dict[str, Any]]:
        return [_openai_function(t) for t in self.all()]


def _openai_function(tool: ToolSpec) -> dict[str, Any]:
    schema = tool.params.model_json_schema()
    properties = {k: v for k, v in schema.get("properties", {}).items() if k != "title"}
    return {
        "type": "function",
        "function": {
            "name": tool.name,
            "description": tool.description,
            "parameters": {
                "type": "object",
                "properties": properties,
                "required": schema.get("required", []),
            },
        },
    }