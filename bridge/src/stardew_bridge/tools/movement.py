"""Movement tools."""
from __future__ import annotations

from .base import ToolSpec, ToolContext
from .params import DirectionParams, MoveToParams, NoParams


def registry():
    async def move_to(ctx: ToolContext, p: MoveToParams) -> str:
        return await ctx.brain.move_to_blocking(p.x, p.y)

    async def stop(ctx: ToolContext, p: NoParams) -> str:
        return await ctx.commander.execute("stop")

    async def face_direction(ctx: ToolContext, p: DirectionParams) -> str:
        return await ctx.commander.execute("face_direction", direction=p.direction)

    return [
        ToolSpec(name="move_to",
                 description="Move to a WALKABLE tile. This tool BLOCKS until arrival.",
                 params=MoveToParams, handler=move_to),
        ToolSpec(name="stop",
                 description="Stop the player's current movement.",
                 params=NoParams, handler=stop),
        ToolSpec(name="face_direction",
                 description="Turn the character to face a direction.",
                 params=DirectionParams, handler=face_direction),
    ]