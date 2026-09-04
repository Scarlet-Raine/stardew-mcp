"""Pydantic models mirroring the game state JSON emitted by the C# SMAPI mod.

Field names in Python are snake_case; they serialize/parse to/from the camelCase
wire format used by the mod over WebSocket. `populate_by_name` allows construction
from either casing.
"""
from __future__ import annotations

import re
from typing import Dict, List, Optional

from pydantic import BaseModel, ConfigDict

_FC_RE = re.compile(r"_([a-z])")


def _camel(name: str) -> str:
    return _FC_RE.sub(lambda m: m.group(1).upper(), name)


class _Base(BaseModel):
    model_config = ConfigDict(
        populate_by_name=True,
        alias_generator=_camel,
        # Accept unknown/modded fields rather than failing.
        extra="ignore",
    )


# --------------------------------------------------------------------------- #
# Entities
# --------------------------------------------------------------------------- #
class InventoryItem(_Base):
    slot: int = 0
    name: str = ""
    display_name: str = ""
    stack: int = 0
    category: str = ""
    is_tool: bool = False
    is_weapon: bool = False


class PlayerState(_Base):
    name: str = ""
    x: int = 0
    y: int = 0
    location: str = ""
    energy: float = 0.0
    max_energy: int = 0
    health: int = 0
    max_health: int = 0
    money: int = 0
    current_tool: str = ""
    current_tool_index: int = 0
    facing_direction: int = 0
    facing_direction_name: str = ""
    is_moving: bool = False
    can_move: bool = False
    is_pathfinding: bool = False
    pathfinding_target_x: Optional[int] = None
    pathfinding_target_y: Optional[int] = None
    path_progress: Optional[int] = None
    path_length: Optional[int] = None
    inventory: List[InventoryItem] = []


class TimeState(_Base):
    time_of_day: int = 0
    time_string: str = ""
    day: int = 0
    season: str = ""
    year: int = 0
    day_of_week: str = ""
    is_night: bool = False
    minutes_until_morning: int = 0


class WorldState(_Base):
    weather: str = ""
    is_outdoors: bool = False
    is_farm: bool = False
    is_greenhouse: bool = False
    is_buildable_location: bool = False
    location_type: str = ""


class MapInfo(_Base):
    name: str = ""
    display_name: str = ""
    width: int = 0
    height: int = 0
    is_mine_level: bool = False
    mine_level: int = 0
    unique_id: str = ""


class TileInfo(_Base):
    x: int = 0
    y: int = 0
    is_passable: bool = False
    is_water: bool = False
    is_tillable: bool = False
    has_object: bool = False
    has_terrain_feature: bool = False
    tile_type: str = ""


class NearbyObject(_Base):
    x: int = 0
    y: int = 0
    name: str = ""
    display_name: str = ""
    type: str = ""
    is_passable: bool = False
    can_be_picked_up: bool = False
    is_ready_for_harvest: bool = False
    minutes_until_ready: int = 0
    held_item_name: Optional[str] = None
    required_tool: Optional[str] = None
    hits_required: int = 0


class NearbyTerrainFeature(_Base):
    x: int = 0
    y: int = 0
    type: str = ""
    is_passable: bool = False
    growth_stage: int = 0
    is_fully_grown: bool = False
    has_seed: bool = False
    can_be_chopped: bool = False
    fruit_count: int = 0
    is_watered: bool = False
    has_crop: bool = False
    crop_name: Optional[str] = None
    crop_phase: int = 0
    days_until_harvest: int = 0
    is_ready_for_harvest: bool = False
    is_dead: bool = False
    grass_type: int = 0
    required_tool: Optional[str] = None
    hits_required: int = 0


class NearbyNPC(_Base):
    x: int = 0
    y: int = 0
    name: str = ""
    display_name: str = ""
    is_facing_player: bool = False
    can_talk: bool = False
    friendship_level: int = 0
    is_moving: bool = False


class NearbyMonster(_Base):
    x: int = 0
    y: int = 0
    name: str = ""
    health: int = 0
    max_health: int = 0
    damage_to_farmer: int = 0
    is_glider: bool = False
    distance: int = 0


class NearbyResourceClump(_Base):
    x: int = 0
    y: int = 0
    width: int = 0
    height: int = 0
    type: str = ""
    health: float = 0.0
    required_tool: Optional[str] = None
    hits_required: int = 0


class NearbyDebris(_Base):
    x: int = 0
    y: int = 0
    name: str = ""
    type: str = ""
    can_be_picked_up: bool = False


class NearbyBuilding(_Base):
    x: int = 0
    y: int = 0
    width: int = 0
    height: int = 0
    type: str = ""
    door_x: int = 0
    door_y: int = 0
    has_animals: bool = False


class NearbyAnimal(_Base):
    x: int = 0
    y: int = 0
    name: str = ""
    type: str = ""
    age: int = 0
    happiness: int = 0
    can_be_pet: bool = False
    has_produce: bool = False


class WarpPoint(_Base):
    x: int = 0
    y: int = 0
    target_location: str = ""
    target_x: int = 0
    target_y: int = 0
    is_door: bool = False


class TileInFront(_Base):
    x: int = 0
    y: int = 0
    is_passable: bool = False
    is_water: bool = False
    is_tillable: bool = False
    object_name: Optional[str] = None
    object_type: Optional[str] = None
    terrain_type: Optional[str] = None
    npc_name: Optional[str] = None
    can_interact: bool = False
    required_tool: Optional[str] = None


class QuestInfo(_Base):
    id: str = ""
    name: str = ""
    description: str = ""
    objective: str = ""
    days_left: int = 0
    reward: int = 0
    is_complete: bool = False


class RelationshipInfo(_Base):
    npc_name: str = ""
    friendship_points: int = 0
    hearts: int = 0
    gifts_today: int = 0
    gifts_this_week: int = 0
    talked_to_today: bool = False
    status: str = ""


class SkillsInfo(_Base):
    farming: int = 0
    mining: int = 0
    foraging: int = 0
    fishing: int = 0
    combat: int = 0
    farming_xp: int = 0
    mining_xp: int = 0
    foraging_xp: int = 0
    fishing_xp: int = 0
    combat_xp: int = 0


class SurroundingsState(_Base):
    ascii_map: str = ""
    nearby_tiles: List[TileInfo] = []
    nearby_objects: List[NearbyObject] = []
    nearby_terrain_features: List[NearbyTerrainFeature] = []
    nearby_npcs: List[NearbyNPC] = []
    nearby_monsters: List[NearbyMonster] = []
    nearby_resource_clumps: List[NearbyResourceClump] = []
    nearby_debris: List[NearbyDebris] = []
    nearby_buildings: List[NearbyBuilding] = []
    nearby_animals: List[NearbyAnimal] = []
    warp_points: List[WarpPoint] = []
    tile_in_front: TileInFront = TileInFront()
    # Mod-robustness additions (optional; emitted by extended C# mod).
    legend: Dict[str, str] = {}


class GameState(_Base):
    player: PlayerState = PlayerState()
    time: TimeState = TimeState()
    world: WorldState = WorldState()
    surroundings: SurroundingsState = SurroundingsState()
    map: MapInfo = MapInfo()
    quests: List[QuestInfo] = []
    relationships: List[RelationshipInfo] = []
    skills: SkillsInfo = SkillsInfo()
    # Mod-robustness addition.
    active_mods: List[str] = []


# --------------------------------------------------------------------------- #
# Wire protocol messages
# --------------------------------------------------------------------------- #
class WebSocketMessage(_Base):
    id: Optional[str] = None
    type: str = ""
    action: Optional[str] = None
    params: Dict[str, object] = {}


class WebSocketResponse(_Base):
    id: Optional[str] = None
    type: str = ""
    success: bool = False
    message: Optional[str] = None
    data: object = None


def game_state_from_dict(data: object) -> GameState:
    """Parse a raw `state` response payload into a GameState."""
    if isinstance(data, GameState):
        return data
    if isinstance(data, dict):
        return GameState.model_validate(data)
    raise ValueError(f"Unexpected state payload type: {type(data)}")