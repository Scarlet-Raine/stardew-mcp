"""Inventory / item tools."""
from __future__ import annotations

from .base import ToolSpec, ToolContext
from .params import NameParams, SlotParams, NoParams


def registry():
    async def select_item(ctx: ToolContext, p: NameParams) -> str:
        return await ctx.commander.execute("select_item", name=p.name)

    async def switch_tool(ctx: ToolContext, p: SlotParams) -> str:
        return await ctx.commander.execute("switch_tool", slot=p.slot)

    async def eat_item(ctx: ToolContext, p: SlotParams) -> str:
        return await ctx.commander.execute("eat_item", slot=p.slot)

    async def place_item(ctx: ToolContext, p: NoParams) -> str:
        return await ctx.commander.execute("place_item")

    async def trash_item(ctx: ToolContext, p: SlotParams) -> str:
        return await ctx.commander.execute("trash_item", slot=p.slot)

    async def ship_item(ctx: ToolContext, p: SlotParams) -> str:
        return await ctx.commander.execute("ship_item", slot=p.slot)

    return [
        ToolSpec(name="select_item",
                 description="Find and equip an item by name (case-insensitive, partial match).",
                 params=NameParams, handler=select_item),
        ToolSpec(name="switch_tool", description="Equip an inventory slot.",
                 params=SlotParams, handler=switch_tool),
        ToolSpec(name="eat_item", description="Eat food from an inventory slot for energy.",
                 params=SlotParams, handler=eat_item),
        ToolSpec(name="place_item", description="Place the currently selected item in front of the player.",
                 params=NoParams, handler=place_item),
        ToolSpec(name="trash_item", description="Trash the item in an inventory slot.",
                 params=SlotParams, handler=trash_item),
        ToolSpec(name="ship_item", description="Ship the item in an inventory slot.",
                 params=SlotParams, handler=ship_item),
    ]