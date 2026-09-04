"""Tool registry: collects all standard + cheat tools."""
from __future__ import annotations

from .base import ToolRegistry
from . import cheats, interaction, inventory, movement, targeting


def build_registry() -> ToolRegistry:
    registry = ToolRegistry()
    for module in (movement, interaction, inventory, targeting, cheats):
        for tool in module.registry():
            registry.add(tool)
    return registry