"""Pydantic parameter models for all tools (standard + cheat)."""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class _P(BaseModel):
    """Base for param models: ignore unknown fields."""

    model_config = {"extra": "ignore"}


class NoParams(_P):
    pass


class MoveToParams(_P):
    x: int = Field(description="Target tile X coordinate")
    y: int = Field(description="Target tile Y coordinate")


class CountParams(_P):
    count: int = Field(default=1, ge=1, le=100, description="Number of times to use the tool")


class DirectionParams(_P):
    direction: str = Field(description="Direction to face (up, down, left, right)")


class NameParams(_P):
    name: str = Field(description="Item name to find and select (case-insensitive, partial match)")


class SlotParams(_P):
    slot: int = Field(description="Inventory slot number")


class TargetTypeParams(_P):
    target_type: str = Field(description="Type of target (debris, tree, crop, npc, warp, any)")


class HoldToolParams(_P):
    ticks: int = Field(default=60, ge=30, le=180, description="Number of game ticks to hold the tool (30-180)")


class CheatSetSeasonParams(_P):
    season: str = Field(description="Season to set (spring, summer, fall, winter)")


class CheatAddExperienceParams(_P):
    skill: str = Field(description="Skill name (Farming, Mining, Foraging, Fishing, Combat)")
    amount: int = Field(description="Amount of XP to add")


class CheatWarpParams(_P):
    location: str = Field(description="Location name (Farm, Town, Mountain, Beach, Forest, Mine, etc.)")
    x: Optional[int] = Field(default=None, description="Optional X coordinate")
    y: Optional[int] = Field(default=None, description="Optional Y coordinate")


class CheatSetMoneyParams(_P):
    amount: int = Field(description="Amount of gold to set")


class CheatAddItemParams(_P):
    item_id: str = Field(alias="itemId", description="Item ID (e.g., '(O)465' for Parsnip Seeds, '(T)Pickaxe')")
    count: Optional[int] = Field(default=None, description="Number of items (default 1)")
    quality: Optional[int] = Field(default=None, description="Quality (0=normal, 1=silver, 2=gold, 4=iridium)")


class CheatSetFriendshipParams(_P):
    npc_name: str = Field(alias="npcName", description="NPC name (e.g., Abigail, Sebastian)")
    hearts: Optional[int] = Field(default=None, description="Friendship hearts (0-14, default 10)")
    points: Optional[int] = Field(default=None, description="Friendship points (250 per heart)")


class CheatMineWarpParams(_P):
    level: int = Field(description="Mine level (1-120 Mines, 121+ Skull Cavern)")


class CheatSpawnOresParams(_P):
    ore_type: str = Field(alias="oreType", description="Type of ore (copper, iron, gold, iridium, coal)")
    count: Optional[int] = Field(default=None, description="Number of ores (default 10)")


class CheatTimeSetParams(_P):
    time: int = Field(description="Time in 24-hour format (600=6AM, 1800=6PM, 2600=2AM)")


class CheatGiveGiftParams(_P):
    npc_name: str = Field(alias="npcName", description="NPC name to give gift to")
    item_id: str = Field(alias="itemId", description="Item ID to give as gift")


class CheatCompleteQuestParams(_P):
    quest_id: Optional[str] = Field(default=None, alias="questId",
                                    description="Quest ID or name to complete (omit to complete all)")


class CheatHoeAllParams(_P):
    radius: Optional[int] = Field(default=None, description="Radius around player to hoe (default 50)")


class CheatCutTreesParams(_P):
    include_stumps: Optional[bool] = Field(default=None, alias="includeStumps",
                                           description="Whether to include tree stumps (default true)")


class CheatPlantSeedsParams(_P):
    seed_id: str = Field(alias="seedId", description="Seed ID to plant (e.g., '(O)472' for Parsnip Seeds)")


class CheatFertilizeAllParams(_P):
    fertilizer_id: Optional[str] = Field(default=None, alias="fertilizerId",
                                         description="Fertilizer ID (default Quality Fertilizer)")


class CheatUpgradeBackpackParams(_P):
    size: Optional[int] = Field(default=None, description="Backpack size: 12, 24, or 36 (default 36)")


class CheatUpgradeToolParams(_P):
    tool: str = Field(description="Tool name: Hoe, Pickaxe, Axe, WateringCan, FishingRod, or Trash Can")
    level: Optional[int] = Field(default=None, description="Upgrade 0=Basic..4=Iridium (default 4)")


class CheatUpgradeAllToolsParams(_P):
    level: Optional[int] = Field(default=None, description="Upgrade 0=Basic..4=Iridium (default 4)")


class CheatHoeTilesParams(_P):
    tiles: Optional[str] = Field(default=None, description="Tile coords as 'x,y;x,y' format")
    x: Optional[int] = Field(default=None, description="Single tile X (use with y)")
    y: Optional[int] = Field(default=None, description="Single tile Y (use with x)")


class CheatClearTilesParams(_P):
    tiles: Optional[str] = Field(default=None, description="Tile coords as 'x,y;x,y' format")
    x: Optional[int] = Field(default=None, description="Single tile X")
    y: Optional[int] = Field(default=None, description="Single tile Y")
    clear_objects: Optional[bool] = Field(default=None, alias="clearObjects", description="Clear objects (default true)")
    clear_features: Optional[bool] = Field(default=None, alias="clearFeatures", description="Clear terrain (default true)")
    clear_dirt: Optional[bool] = Field(default=None, alias="clearDirt", description="Clear hoed dirt (default true)")


class CheatHoeCustomPatternParams(_P):
    grid: Optional[str] = Field(default=None, description="ASCII art grid (# or X = hoe). Use \\n for rows")
    x: Optional[int] = Field(default=None, description="Center X (default: player position)")
    y: Optional[int] = Field(default=None, description="Center Y (default: player position)")
    offset_string: Optional[str] = Field(default=None, alias="offsetString",
                                         description="Relative offsets 'dx,dy;dx,dy'")
    clear_area: Optional[bool] = Field(default=None, alias="clearArea",
                                       description="Clear surrounding hoed dirt (default true)")
    clear_radius: Optional[int] = Field(default=None, alias="clearRadius",
                                        description="Radius around pattern to clear")