"""Targeting tools: find/clear the nearest appropriate target."""
from __future__ import annotations

from .base import ToolSpec, ToolContext
from .params import TargetTypeParams


def registry():
    async def find_best_target(ctx: ToolContext, p: TargetTypeParams) -> str:
        state = ctx.brain.state()
        if state is None:
            return "Game disconnected"
        return ctx.brain.find_best_target(state, p.target_type)

    async def clear_target(ctx: ToolContext, p: TargetTypeParams) -> str:
        return await ctx.brain.clear_target(p.target_type)

    return [
        ToolSpec(name="find_best_target",
                 description="Find the nearest target of a type with a walkable approach tile.",
                 params=TargetTypeParams, handler=find_best_target),
        ToolSpec(name="clear_target",
                 description="Find and clear the nearest target automatically (select_item + move_to + face_direction + use_tool).",
                 params=TargetTypeParams, handler=clear_target),
    ]