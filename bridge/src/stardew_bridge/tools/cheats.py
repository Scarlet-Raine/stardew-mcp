"""Cheat-mode tools (god-mode capabilities). Must enable cheat mode first."""
from __future__ import annotations

from .base import ToolSpec, ToolContext
from .params import (
    CheatAddExperienceParams, CheatAddItemParams, CheatClearTilesParams,
    CheatCompleteQuestParams, CheatCutTreesParams, CheatFertilizeAllParams,
    CheatGiveGiftParams, CheatHoeAllParams, CheatHoeCustomPatternParams,
    CheatHoeTilesParams, CheatMineWarpParams, CheatPlantSeedsParams,
    CheatSetFriendshipParams, CheatSetMoneyParams, CheatSetSeasonParams,
    CheatSpawnOresParams, CheatTimeSetParams, CheatUpgradeAllToolsParams,
    CheatUpgradeBackpackParams, CheatUpgradeToolParams, CheatWarpParams,
    NoParams,
)


def registry():
    tools: list[ToolSpec] = []

    def reg(name, desc, params, handler):
        tools.append(ToolSpec(name=name, description=desc, params=params, handler=handler))

    def cmdaction(name, desc):
        async def handler(ctx: ToolContext, p: NoParams) -> str:
            return await ctx.commander.execute(name)
        reg(name, desc, NoParams, handler)

    # Mode control
    cmdaction("cheat_mode_enable", "Enable cheat mode. Required before using other cheat commands.")
    cmdaction("cheat_mode_disable", "Disable cheat mode and its persistent effects.")
    cmdaction("cheat_time_freeze", "Toggle time freeze on/off.")
    cmdaction("cheat_infinite_energy", "Toggle infinite stamina on/off.")
    cmdaction("cheat_set_energy", "Restore stamina to maximum.")
    cmdaction("cheat_set_health", "Restore health to maximum.")

    # Parameterless farming/cheat actions
    for name, desc in [
        ("cheat_harvest_all", "Instantly harvest all ready crops in the current location."),
        ("cheat_water_all", "Instantly water all tilled soil in the current location."),
        ("cheat_grow_crops", "Instantly grow all crops to harvest-ready."),
        ("cheat_clear_debris", "Remove all weeds, stones, twigs, grass in the current location."),
        ("cheat_mine_rocks", "Instantly mine all rocks/stones/boulders, collect ores."),
        ("cheat_dig_artifacts", "Instantly dig up all artifact spots."),
        ("cheat_collect_all_forage", "Instantly collect all forage items in the current location."),
        ("cheat_instant_mine", "Mine ALL ore nodes in the current mine level instantly."),
        ("cheat_max_all_friendships", "Max out friendship with ALL NPCs at once."),
        ("cheat_pet_all_animals", "Pet all farm animals instantly."),
        ("cheat_unlock_recipes", "Unlock ALL crafting and cooking recipes."),
        ("cheat_unlock_all", "UNLOCK EVERYTHING: backpack, tools, recipes, skills, special items."),
    ]:
        cmdaction(name, desc)

    # Warp / teleport
    async def warp(ctx: ToolContext, p: CheatWarpParams) -> str:
        params: dict = {"location": p.location}
        if p.x is not None:
            params["x"] = p.x
        if p.y is not None:
            params["y"] = p.y
        return await ctx.commander.execute("cheat_warp", **params)

    async def mine_warp(ctx: ToolContext, p: CheatMineWarpParams) -> str:
        return await ctx.commander.execute("cheat_mine_warp", level=p.level)

    reg("cheat_warp", "Instantly teleport to any location.", CheatWarpParams, warp)
    reg("cheat_mine_warp",
        "Warp directly to a mine level (1-120 Mines, 121+ Skull Cavern).",
        CheatMineWarpParams, mine_warp)

    # Resources / items
    async def set_money(ctx: ToolContext, p: CheatSetMoneyParams) -> str:
        return await ctx.commander.execute("cheat_set_money", amount=p.amount)

    async def add_item(ctx: ToolContext, p: CheatAddItemParams) -> str:
        params: dict = {"itemId": p.item_id}
        if p.count is not None:
            params["count"] = p.count
        if p.quality is not None:
            params["quality"] = p.quality
        return await ctx.commander.execute("cheat_add_item", **params)

    async def spawn_ores(ctx: ToolContext, p: CheatSpawnOresParams) -> str:
        params: dict = {"oreType": p.ore_type}
        if p.count is not None:
            params["count"] = p.count
        return await ctx.commander.execute("cheat_spawn_ores", **params)

    reg("cheat_set_money", "Set the player's gold amount.", CheatSetMoneyParams, set_money)
    reg("cheat_add_item", "Add any item to inventory by ID.", CheatAddItemParams, add_item)
    reg("cheat_spawn_ores", "Add ores directly (copper, iron, gold, iridium, coal).",
        CheatSpawnOresParams, spawn_ores)

    # Social
    async def set_friendship(ctx: ToolContext, p: CheatSetFriendshipParams) -> str:
        params: dict = {"npcName": p.npc_name}
        if p.hearts is not None:
            params["hearts"] = p.hearts
        elif p.points is not None:
            params["points"] = p.points
        else:
            params["hearts"] = 10
        return await ctx.commander.execute("cheat_set_friendship", **params)

    async def give_gift(ctx: ToolContext, p: CheatGiveGiftParams) -> str:
        return await ctx.commander.execute("cheat_give_gift", npcName=p.npc_name, itemId=p.item_id)

    async def complete_quest(ctx: ToolContext, p: CheatCompleteQuestParams) -> str:
        params: dict = {}
        if p.quest_id:
            params["questId"] = p.quest_id
        return await ctx.commander.execute("cheat_complete_quest", **params)

    reg("cheat_set_friendship", "Set friendship with an NPC (hearts or points).",
        CheatSetFriendshipParams, set_friendship)
    reg("cheat_give_gift", "Give a gift to an NPC instantly.", CheatGiveGiftParams, give_gift)
    reg("cheat_complete_quest", "Complete active quests.", CheatCompleteQuestParams, complete_quest)

    # Time
    async def time_set(ctx: ToolContext, p: CheatTimeSetParams) -> str:
        return await ctx.commander.execute("cheat_time_set", time=p.time)

    reg("cheat_time_set",
        "Set the game time (600=6AM, 1200=noon, 1800=6PM, 2400=midnight).",
        CheatTimeSetParams, time_set)

    # Farming
    async def hoe_all(ctx: ToolContext, p: CheatHoeAllParams) -> str:
        params: dict = {}
        if p.radius is not None:
            params["radius"] = p.radius
        return await ctx.commander.execute("cheat_hoe_all", **params)

    async def cut_trees(ctx: ToolContext, p: CheatCutTreesParams) -> str:
        params: dict = {}
        if p.include_stumps is False:
            params["includeStumps"] = "false"
        return await ctx.commander.execute("cheat_cut_trees", **params)

    async def plant_seeds(ctx: ToolContext, p: CheatPlantSeedsParams) -> str:
        return await ctx.commander.execute("cheat_plant_seeds", seedId=p.seed_id)

    async def fertilize_all(ctx: ToolContext, p: CheatFertilizeAllParams) -> str:
        params: dict = {}
        if p.fertilizer_id:
            params["fertilizerId"] = p.fertilizer_id
        return await ctx.commander.execute("cheat_fertilize_all", **params)

    reg("cheat_hoe_all", "Instantly hoe/till all diggable tiles.", CheatHoeAllParams, hoe_all)
    reg("cheat_cut_trees", "Instantly cut/chop all trees, collect wood.", CheatCutTreesParams, cut_trees)
    reg("cheat_plant_seeds", "Instantly plant seeds on all empty hoed tiles.",
        CheatPlantSeedsParams, plant_seeds)
    reg("cheat_fertilize_all", "Apply fertilizer to all hoed tiles.",
        CheatFertilizeAllParams, fertilize_all)

    # Upgrades
    async def upgrade_backpack(ctx: ToolContext, p: CheatUpgradeBackpackParams) -> str:
        params: dict = {}
        if p.size is not None:
            params["size"] = p.size
        return await ctx.commander.execute("cheat_upgrade_backpack", **params)

    async def upgrade_tool(ctx: ToolContext, p: CheatUpgradeToolParams) -> str:
        params: dict = {"tool": p.tool}
        if p.level is not None:
            params["level"] = p.level
        return await ctx.commander.execute("cheat_upgrade_tool", **params)

    async def upgrade_all_tools(ctx: ToolContext, p: CheatUpgradeAllToolsParams) -> str:
        params: dict = {}
        if p.level is not None:
            params["level"] = p.level
        return await ctx.commander.execute("cheat_upgrade_all_tools", **params)

    reg("cheat_upgrade_backpack", "Upgrade backpack to 12, 24, or 36 slots.",
        CheatUpgradeBackpackParams, upgrade_backpack)
    reg("cheat_upgrade_tool", "Upgrade a specific tool (0=Basic..4=Iridium).",
        CheatUpgradeToolParams, upgrade_tool)
    reg("cheat_upgrade_all_tools", "Upgrade ALL tools to a level.",
        CheatUpgradeAllToolsParams, upgrade_all_tools)

    # Targeted/selective cheats
    async def hoe_tiles(ctx: ToolContext, p: CheatHoeTilesParams) -> str:
        params: dict = {}
        if p.tiles:
            params["tiles"] = p.tiles
        if p.x is not None or p.y is not None:
            params["x"] = p.x or 0
            params["y"] = p.y or 0
        return await ctx.commander.execute("cheat_hoe_tiles", **params)

    async def clear_tiles(ctx: ToolContext, p: CheatClearTilesParams) -> str:
        params: dict = {}
        if p.tiles:
            params["tiles"] = p.tiles
        if p.x is not None or p.y is not None:
            params["x"] = p.x or 0
            params["y"] = p.y or 0
        if p.clear_objects is False:
            params["clearObjects"] = "false"
        if p.clear_features is False:
            params["clearFeatures"] = "false"
        if p.clear_dirt is False:
            params["clearDirt"] = "false"
        return await ctx.commander.execute("cheat_clear_tiles", **params)

    async def hoe_custom_pattern(ctx: ToolContext, p: CheatHoeCustomPatternParams) -> str:
        params: dict = {}
        if p.grid:
            params["grid"] = p.grid
        if p.x is not None:
            params["x"] = p.x
        if p.y is not None:
            params["y"] = p.y
        if p.offset_string:
            params["offsetString"] = p.offset_string
        if p.clear_area is False:
            params["clearArea"] = "false"
        if p.clear_radius is not None:
            params["clearRadius"] = p.clear_radius
        return await ctx.commander.execute("cheat_hoe_custom_pattern", **params)

    reg("cheat_hoe_tiles", "Hoe SPECIFIC tiles by coordinates ('x,y;x,y' or x/y).",
        CheatHoeTilesParams, hoe_tiles)
    reg("cheat_clear_tiles", "Clear SPECIFIC tiles (objects, terrain, hoed dirt).",
        CheatClearTilesParams, clear_tiles)
    reg("cheat_hoe_custom_pattern",
        "Draw ANY shape by hoeing tiles from an ASCII grid ('#' or 'X' = hoe, '\\n' = row).",
        CheatHoeCustomPatternParams, hoe_custom_pattern)

    # Misc
    async def set_season(ctx: ToolContext, p: CheatSetSeasonParams) -> str:
        return await ctx.commander.execute("cheat_set_season", season=p.season)

    async def add_experience(ctx: ToolContext, p: CheatAddExperienceParams) -> str:
        return await ctx.commander.execute("cheat_add_experience", skill=p.skill, amount=p.amount)

    reg("cheat_set_season", "Set the current season.", CheatSetSeasonParams, set_season)
    reg("cheat_add_experience", "Add experience points to a skill.",
        CheatAddExperienceParams, add_experience)

    return tools