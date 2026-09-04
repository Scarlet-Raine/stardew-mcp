"""MCP (Model Context Protocol) adapter.

Exposes every registered game tool through the official ``mcp`` Python SDK via
FastMCP. The ``mcp`` dependency is optional; import it lazily so the core package
works without it.
"""
from __future__ import annotations

import logging
from typing import Any

from .agent import make_tool_context
from .config import Config
from .tools.base import ToolRegistry, ToolContext
from .ws_client import GameClient

logger = logging.getLogger("stardew_bridge.mcp")


def _require_mcp():
    try:
        from mcp.server.fastmcp import FastMCP  # noqa: F401
        return FastMCP
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError(
            "The 'mcp' package is required for the MCP server. "
            "Install it with: pip install stardew-bridge[mcp]"
        ) from exc


class McpAdapter:
    """Builds and runs an MCP server backed by the tool registry."""

    def __init__(self, client: GameClient, registry: ToolRegistry, config: Config) -> None:
        self.client = client
        self.registry = registry
        self.config = config
        self.ctx = make_tool_context(client, registry, config)
        self._server = None

    def build(self):
        FastMCP = _require_mcp()
        server = FastMCP("stardew-bridge")
        self._server = server
        for tool in self.registry.all():
            server.add_tool(_bind(self.ctx, self.registry, tool),
                            name=tool.name, description=tool.description)
        return server

    async def run(self, transport: str = "stdio") -> None:
        server = self.build()
        logger.info("Starting MCP server (transport=%s)", transport)
        await server.run(transport=transport)


def _typing_repr(ann: Any) -> str:
    """Render a (simple) type annotation as a source-safe string using short names."""
    import typing

    if ann is None or ann is type(None):
        return "None"
    origin = typing.get_origin(ann)
    if origin is not None:
        args = ", ".join(_typing_repr(a) for a in typing.get_args(ann))
        name = getattr(origin, "__name__", None) or str(origin).split(".")[-1]
        return f"{name}[{args}]"
    name = getattr(ann, "__name__", None)
    if name:
        return name
    return str(ann).replace("typing.", "").replace(" ", "")


def _bind(ctx: ToolContext, registry: ToolRegistry, tool):
    """Return an async handler with flat, typed params.

    Flattening the Pydantic model into individual annotated arguments makes the
    MCP tool schema match the OpenAI function schema exactly.
    """
    import typing

    fields = tool.params.model_fields
    entries = []
    for n, fi in fields.items():
        alias = fi.alias or n
        entries.append((n, alias, fi.annotation))
    sig = ", ".join(f"{alias}: {_typing_repr(ann) if ann is not None else 'Any'}"
                    for _n, alias, ann in entries)
    # Pass python field names into the registry; expose camelCase aliases on the wire.
    kwargs_str = ", ".join(f'"{n}": {alias}' for n, alias, _a in entries)

    g = {
        "registry": registry,
        "ctx": ctx,
        "int": int, "str": str, "float": float, "bool": bool,
        "Any": Any, "Optional": typing.Optional, "Union": typing.Union,
        "List": typing.List, "Dict": typing.Dict, "None": type(None),
    }
    l = {}
    src = f"async def handler({sig}):\n    return await registry.call({tool.name!r}, {{{kwargs_str}}}, ctx)\n"
    exec(src, g, l)  # noqa: S102 - local ns only
    handler = l["handler"]
    handler.__name__ = tool.name
    return handler