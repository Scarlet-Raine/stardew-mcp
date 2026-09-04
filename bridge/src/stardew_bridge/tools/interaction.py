"""Interaction / tool-use tools."""
from __future__ import annotations

from .base import ToolSpec, ToolContext
from .params import CountParams, HoldToolParams, NoParams


def registry():
    async def interact(ctx: ToolContext, p: NoParams) -> str:
        return await ctx.commander.execute("interact")

    async def use_tool(ctx: ToolContext, p: NoParams) -> str:
        return await ctx.commander.execute("use_tool")

    async def use_tool_repeat(ctx: ToolContext, p: CountParams) -> str:
        return await ctx.commander.execute("use_tool_repeat", count=p.count)

    async def hold_tool(ctx: ToolContext, p: HoldToolParams) -> str:
        return await ctx.commander.execute("hold_tool", ticks=p.ticks)

    async def enter_door(ctx: ToolContext, p: NoParams) -> str:
        return await ctx.commander.execute("enter_door")

    async def get_surroundings(ctx: ToolContext, p: NoParams) -> str:
        state = ctx.brain.state()
        if state is None:
            return "Disconnected"
        return ctx.brain.format_context(state)

    return [
        ToolSpec(name="interact", description="Interact with the tile in front.",
                 params=NoParams, handler=interact),
        ToolSpec(name="use_tool", description="Use the currently equipped tool once.",
                 params=NoParams, handler=use_tool),
        ToolSpec(name="use_tool_repeat", description="Execute the current tool multiple times.",
                 params=CountParams, handler=use_tool_repeat),
        ToolSpec(name="hold_tool", description="Hold (charge) the current tool for a number of ticks.",
                 params=HoldToolParams, handler=hold_tool),
        ToolSpec(name="enter_door", description="Enter the door/warp point in front of the player.",
                 params=NoParams, handler=enter_door),
        ToolSpec(name="get_surroundings",
                 description="Refresh vision to see the 61x61 area, tile in front, and inventory.",
                 params=NoParams, handler=get_surroundings),
    ]