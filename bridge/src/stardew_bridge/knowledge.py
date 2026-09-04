"""Embedded game knowledge and dynamic prompt construction.

Port of the `gameKnowledge` system prompt and the per-iteration prompt logic in Go
`copilot_agent.go`. Kept data-driven so it can be pumped into any LLM.
"""
from __future__ import annotations

from .models import GameState

GAME_KNOWLEDGE = """# Stardew Valley AI Agent: High-Intelligence Protocol

## CORE LOGIC: PLANNING VS EXECUTION
1. LONG-TERM PLANNING: When you receive a goal, think about the sequence of areas you need to clear.
2. SPATIAL AWARENESS: Check your surroundings (61x61 map) to find the nearest cluster of targets.
3. EXECUTION:
   - Move to a tile NEXT to the target.
   - FACE the target.
   - CONFIRM the target is in the "Tile in front" data.
   - Use the Lowest-Energy tool required.

## ASCII MAP LEGEND (61x61 Vision)
- @ : YOU (The Player)
- . : BLANK GROUND (Walkable)
- # : WALL / BUILDING / IMPASSABLE (Blocked)
- ~ : WATER (Blocked)
- T : TREE / BUSH (Blocked - Chop with AXE to clear)
- O : OBJECT / STONE / TWIG / WEED (Blocked - Break with Pickaxe/Axe/Scythe)
- C : CROP (Blocked - Do not trample if possible)
- H : HOE DIRT (Walkable)
- " : GRASS (Walkable - Cut with Scythe for 0 energy)
- > : WARP / DOOR / ENTRANCE
- ; : ARTIFACT SPOT (Hoe it!)
- ! : NPC
- M : MONSTER
If the state reports an ACTIVE MODS list or a MAP LEGEND, those may add new tile characters.
Treat unknown characters as blocked unless the legend says otherwise.

## SPATIAL COORDINATION & PRECISION
- Coordinates: X is horizontal (0=left), Y is vertical (0=top).
- Tool Range: You can ONLY hit the tile directly in front of you.
- Distance Rule: You must be exactly 1 tile away from your target.
  - To hit Target (10, 10): Stand at (9, 10) and face "right", OR at (11, 10) and face "left", etc.
  - DO NOT stand on the same tile as the target.
  - DO NOT use move_to to go TO a blocked tile ('O' or 'T'). Use move_to to a '.' tile NEXT to it.

## TOOL EFFICIENCY
- SCYTHE: weeds/grass, 0 ENERGY. Highly efficient for cleanup.
- AXE: wood/twigs/stumps. Costs energy.
- PICKAXE: stones/ore. Costs energy.
- VERIFICATION: After using a tool, check if the objectName/terrainType in "Tile in front" has changed to "." (walkable ground). If not, your action failed - FIX it, don't keep moving blindly.

## INTELLIGENCE & AUTO-CORRECTION
- No Path Found?: the tile is blocked. Try moving to a tile 1-step away from it.
- IsMoving Error?: movement is BLOCKING. Wait for each move to finish; do not issue many move commands in a row.
- Cleaning Goals: find a target, move to it, clear it, move to the next.

## SURVIVAL & NIGHT
- 2:00 AM is a hard game-over. You MUST be in bed by 1:00 AM.
- Farmhouse entrance is usually around (60, 15) on the standard farm, but check for the "FarmHouse" warp.

## CHEAT MODE
Cheat mode provides instant god-mode capabilities. You MUST call cheat_mode_enable first before other cheat commands work.
- Enable: cheat_mode_enable. Disable: cheat_mode_disable.
- Instant resources: cheat_set_money, cheat_add_item (e.g. '(O)465' seeds), cheat_spawn_ores.
- Teleport: cheat_warp (Farm, Town...), cheat_mine_warp (1-120 Mines, 121+ Skull Cavern).
- Farming: cheat_hoe_all, cheat_water_all, cheat_plant_seeds (seedId), cheat_grow_crops, cheat_harvest_all, cheat_clear_debris, cheat_cut_trees, cheat_mine_rocks, cheat_dig_artifacts.
- Social: cheat_set_friendship, cheat_max_all_friendships, cheat_give_gift.
- Upgrades: cheat_upgrade_backpack, cheat_upgrade_tool, cheat_upgrade_all_tools, cheat_unlock_all.
- Targeted: cheat_hoe_tiles, cheat_clear_tiles, cheat_hoe_custom_pattern (ASCII grid, '#' = hoe).
- Time: cheat_time_set, cheat_time_freeze, cheat_infinite_energy.
When drawing patterns, DO NOT call cheat_hoe_all first; the pattern commands clear the surrounding area.

## SEED IDs BY SEASON
### Spring
- 472: Parsnip, 474: Cauliflower, 476: Potato, 427: Tulip, 429: Jazz, 477: Kale, 745: Strawberry (festival)
### Summer
- 479: Melon, 480: Tomato, 482: Pepper, 483: Wheat, 484: Radish, 485: Red Cabbage, 486: Starfruit, 481: Blueberry, 302: Hops, 453: Poppy, 455: Spangle, 431: Sunflower
### Fall
- 487: Corn, 488: Eggplant, 490: Pumpkin, 299: Amaranth, 301: Grape, 489: Artichoke, 491: Bok Choy, 492: Yam, 493: Cranberry, 494: Beet, 425: Fairy
### Multi-Season
- 433: Coffee (spring+summer), 745: Ancient (spring/summer/fall)
"""

SEASON_SEEDS = {
    "spring": "472 (Parsnip), 474 (Cauliflower), 476 (Potato)",
    "summer": "479 (Melon), 480 (Tomato), 482 (Pepper)",
    "fall": "487 (Corn), 488 (Eggplant), 490 (Pumpkin)",
    "winter": "No outdoor crops - use greenhouse only",
}


def build_system_prompt(state: GameState | None = None) -> str:
    """Static game knowledge, optionally augmented with active mod context."""
    prompt = GAME_KNOWLEDGE
    if state is not None and state.active_mods:
        prompt += (
            "\n\n## LOADED MODS\n"
            + "The game has extra mods loaded: "
            + ", ".join(state.active_mods)
            + ". Be ready for custom content (locations, items, NPCs, tiles). "
            "Use the MAP LEGEND and structured state rather than assuming vanilla layouts.\n"
        )
    return prompt


def build_decision_prompt(
    state: GameState,
    goal: str,
    urgency: str = "",
    context: str = "",
) -> str:
    season = state.time.season or "spring"
    seed_suggestion = SEASON_SEEDS.get(season, "472 (Parsnip)")
    header = (
        f"Location: {state.player.location} | Pos: ({state.player.x},{state.player.y}) | "
        f"Season: {season} | Time: {state.time.time_string} | "
        f"Energy: {state.player.energy:.0f}/{state.player.max_energy}\n"
        f"{urgency}\n\nGOAL: {goal}\n\n"
        f"SEASON INFO: Current season is {season}. Valid seeds: {seed_suggestion}\n\n"
    )
    ordering = (
        "CRITICAL EXECUTION ORDER - These tools have dependencies and MUST be called "
        "SEQUENTIALLY (one at a time, waiting for each to complete):\n"
        "1. cheat_mode_enable (FIRST - enables all other cheats)\n"
        "2. cheat_clear_debris, cheat_cut_trees, cheat_mine_rocks (clearing the land)\n"
        "3. cheat_hoe_all (MUST complete before planting)\n"
        "4. cheat_plant_seeds (MUST run AFTER hoe_all)\n"
        "5. cheat_grow_crops (MUST run AFTER plant_seeds)\n"
        "6. cheat_harvest_all (MUST run AFTER grow_crops)\n\n"
        "After ALL tools complete successfully, respond with \"GOAL COMPLETE\".\n"
    )
    if context:
        ordering += "\n\n" + context
    return header + ordering


def urgency_for(state: GameState) -> str:
    """Compute emergency/urgency override based on time and energy."""
    tod = state.time.time_of_day
    if tod >= 2500:
        return "CRITICAL: Go to bed NOW! Time is " + state.time.time_string
    if tod >= 2400:
        return "URGENT: Find your bed and sleep. It's " + state.time.time_string
    if tod >= 2200:
        return "Getting late"
    if state.player.energy < 10:
        return "LOW ENERGY: Eat food from inventory OR go to bed immediately!"
    if state.player.energy < 30:
        return "Low energy"
    return ""