"""Shared fixtures: a realistic GameState dict and helpers."""
from __future__ import annotations

import pytest


def make_map_state_dict(player=(5, 5), facing=1) -> dict:
    """A 11x11 fake map centered on the player at (5,5)."""
    radius = 30
    size = radius * 2 + 1
    grid = [["." for _ in range(size)] for _ in range(size)]
    grid[radius][radius] = "@"
    # Place a stone object at (7,5) -> two tiles right of player.
    grid[radius][radius + 2] = "O"
    # Place water at (5,8) -> three tiles down.
    grid[radius + 3][radius] = "~"
    # Place a tree at (3,6).
    grid[radius + 1][radius - 2] = "T"
    ascii_map = "\n".join("".join(row) for row in grid)

    return {
        "player": {
            "name": "TestFarmer", "x": 5, "y": 5, "location": "Farm", "energy": 200.0,
            "maxEnergy": 270, "health": 100, "maxHealth": 100, "money": 500,
            "currentTool": "Axe", "currentToolIndex": 0, "facingDirection": facing,
            "facingDirectionName": _dir_name(facing), "isMoving": False, "canMove": True,
            "inventory": [
                {"slot": 0, "name": "Axe", "displayName": "Axe", "stack": 1,
                 "category": "Tools", "isTool": True, "isWeapon": False},
                {"slot": 1, "name": "Salad", "displayName": "Salad", "stack": 3,
                 "category": "Cooking", "isTool": False, "isWeapon": False},
            ],
        },
        "time": {"timeOfDay": 1200, "timeString": "12:00 PM", "day": 3, "season": "spring",
                 "year": 1, "dayOfWeek": "Wednesday", "isNight": False,
                 "minutesUntilMorning": 840},
        "world": {"weather": "sunny", "isOutdoors": True, "isFarm": True,
                  "isGreenhouse": False, "isBuildableLocation": True, "locationType": "farm"},
        "map": {"name": "Farm", "displayName": "Farm", "width": 100, "height": 100,
                "isMineLevel": False, "mineLevel": 0, "uniqueId": "Farm"},
        "surroundings": {
            "asciiMap": ascii_map,
            "nearbyTiles": [
                {"x": 7, "y": 5, "isPassable": False, "isWater": False, "isTillable": False,
                 "hasObject": True, "hasTerrainFeature": False, "tileType": "normal"},
                {"x": 5, "y": 8, "isPassable": False, "isWater": True, "isTillable": False,
                 "hasObject": False, "hasTerrainFeature": False, "tileType": "water"},
            ],
            "nearbyObjects": [
                {"x": 7, "y": 5, "name": "Stone", "displayName": "Stone", "type": "object",
                 "isPassable": False, "canBePickedUp": False, "isReadyForHarvest": False,
                 "minutesUntilReady": 0, "heldItemName": None, "requiredTool": "Pickaxe",
                 "hitsRequired": 1},
            ],
            "nearbyTerrainFeatures": [
                {"x": 3, "y": 6, "type": "tree", "isPassable": False, "growthStage": 5,
                 "isFullyGrown": True, "hasSeed": False, "canBeChopped": True,
                 "requiredTool": "Axe", "hitsRequired": 10},
            ],
            "nearbyNPCs": [],
            "nearbyMonsters": [],
            "nearbyResourceClumps": [],
            "nearbyDebris": [],
            "nearbyBuildings": [{"x": 10, "y": 10, "width": 6, "height": 4, "type": "FarmHouse",
                                 "doorX": 12, "doorY": 12, "hasAnimals": False}],
            "nearbyAnimals": [],
            "warpPoints": [{"x": 30, "y": 30, "targetLocation": "Town",
                            "targetX": 15, "targetY": 30, "isDoor": False}],
            "tileInFront": {"x": 6, "y": 5, "isPassable": True, "isWater": False,
                            "isTillable": False, "objectName": None, "objectType": None,
                            "terrainType": None, "npcName": None, "canInteract": False,
                            "requiredTool": None},
        },
        "quests": [],
        "relationships": [],
        "skills": {"farming": 0, "mining": 0, "foraging": 0, "fishing": 0, "combat": 0,
                   "farmingXp": 0, "miningXp": 0, "foragingXp": 0, "fishingXp": 0, "combatXp": 0},
        "activeMods": ["SomeCoolContentPack"],
    }


def _dir_name(d: int) -> str:
    return {0: "up", 1: "right", 2: "down", 3: "left"}.get(d, "unknown")


@pytest.fixture
def sample_state():
    from stardew_bridge.models import game_state_from_dict
    return game_state_from_dict(make_map_state_dict())