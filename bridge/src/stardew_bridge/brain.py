"""Agent "brain": targeting, walkability, and context formatting.

Port of the logic in Go `copilot_agent.go` (findBestTargetInfo, findBestTarget,
isTileWalkable, formatGameStateContext) and the blocking move_to semantics.
"""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import Optional

from .commands import GameCommander
from .models import GameState
from .ws_client import GameClient

logger = logging.getLogger("stardew_bridge.brain")

# ASCII chars considered walkable (fallback when structured signals are absent).
WALKABLE_CHARS = {".", ">", "H", '"', ";", "@"}
SCAN_RADIUS = 30


@dataclass
class Target:
    x: int
    y: int
    name: str
    type: str
    required_tool: str = ""
    hits_required: int = 0
    distance: int = 0


@dataclass
class TargetInfo:
    x: int
    y: int
    name: str
    required_tool: str
    hits_required: int
    approach_x: int
    approach_y: int
    face_direction: str


def _normalize_target_type(raw: str) -> str:
    t = raw.strip().lower()
    if t in ("weed", "weeds", "grass", "stone", "stones", "rock", "rocks", "twig", "twigs",
             "stick", "sticks", "object", "objects"):
        return "debris"
    if t in ("trees", "wood", "log", "logs"):
        return "tree"
    if t in ("crops", "harvest", "vegetables", "fruit"):
        return "crop"
    if t in ("npcs", "villager", "villagers", "person", "people"):
        return "npc"
    if t in ("warps", "doors", "exit", "entrance", "portal"):
        return "warp"
    if t in ("all", "everything", "anything"):
        return "any"
    return t


class Brain:
    """Deterministic agent logic layered over the game state + commander."""

    def __init__(self, client: GameClient, commander: GameCommander) -> None:
        self.client = client
        self.commander = commander

    def state(self) -> Optional[GameState]:
        return self.client.state()

    # ------------------------------------------------------------------ #
    # Walkability
    # ------------------------------------------------------------------ #
    def is_tile_walkable(self, state: GameState, x: int, y: int) -> bool:
        px, py = state.player.x, state.player.y
        rx, ry = x - px, y - py
        if ry < -SCAN_RADIUS or ry > SCAN_RADIUS or rx < -SCAN_RADIUS or rx > SCAN_RADIUS:
            return False

        # Structured signal first (emitted by the extended mod).
        map_info = state.map
        if map_info.width > 0 and (x < 0 or y < 0 or x >= map_info.width or y >= map_info.height):
            return False
        for tile in state.surroundings.nearby_tiles:
            if tile.x == x and tile.y == y:
                return bool(tile.is_passable) and not tile.is_water

        # ASCII map fallback.
        grid = state.surroundings.ascii_map
        if grid:
            lines = grid.split("\n")
            gy = SCAN_RADIUS + ry
            gx = SCAN_RADIUS + rx
            if 0 <= gy < len(lines):
                line = lines[gy]
                if 0 <= gx < len(line):
                    return line[gx] in WALKABLE_CHARS
        # Tile was requested but is unknown; treat ordinary ground as walkable.
        return True

    # ------------------------------------------------------------------ #
    # Target candidate gathering
    # ------------------------------------------------------------------ #
    def _targets(self, state: GameState, target_type: str) -> list[Target]:
        px, py = state.player.x, state.player.y
        tt = _normalize_target_type(target_type)
        targets: list[Target] = []

        def manhattan(a: int, b: int) -> int:
            return abs(a - px) + abs(b - py)

        if tt in ("debris", "any"):
            for obj in state.surroundings.nearby_objects:
                if not obj.is_passable:
                    hits = obj.hits_required or 1
                    dist = manhattan(obj.x, obj.y)
                    if obj.required_tool == "Scythe":
                        dist -= 100
                    targets.append(Target(obj.x, obj.y, obj.display_name or obj.name,
                                          "object", obj.required_tool or "", hits, dist))

        if tt in ("tree", "any"):
            for tf in state.surroundings.nearby_terrain_features:
                if not tf.is_passable and tf.type in ("tree", "fruit_tree"):
                    hits = tf.hits_required or 10
                    targets.append(Target(tf.x, tf.y, tf.type, "terrain",
                                          tf.required_tool or "", hits, manhattan(tf.x, tf.y)))

        if tt in ("crop", "any"):
            for tf in state.surroundings.nearby_terrain_features:
                if tf.has_crop and tf.is_ready_for_harvest:
                    targets.append(Target(tf.x, tf.y, tf.crop_name or "crop", "crop",
                                          "Scythe", 1, manhattan(tf.x, tf.y)))

        if tt == "npc" or tt == "any":
            for npc in state.surroundings.nearby_npcs:
                targets.append(Target(npc.x, npc.y, npc.display_name or npc.name, "npc",
                                      "", 0, manhattan(npc.x, npc.y)))

        if tt in ("warp", "door", "any"):
            for w in state.surroundings.warp_points:
                targets.append(Target(w.x, w.y, w.target_location or "warp", "warp",
                                      "", 0, manhattan(w.x, w.y)))
            for b in state.surroundings.nearby_buildings:
                if b.type in ("FarmHouse", "Cabin"):
                    targets.append(Target(b.door_x, b.door_y, f"{b.type} door", "door",
                                          "", 0, manhattan(b.door_x, b.door_y)))

        return targets

    def find_best_target_info(self, state: GameState, target_type: str) -> Optional[TargetInfo]:
        targets = sorted(self._targets(state, target_type), key=lambda t: t.distance)
        for target in targets:
            for ax, ay, face in (
                (target.x - 1, target.y, "right"),
                (target.x + 1, target.y, "left"),
                (target.x, target.y - 1, "down"),
                (target.x, target.y + 1, "up"),
            ):
                if self.is_tile_walkable(state, ax, ay):
                    return TargetInfo(
                        x=target.x, y=target.y, name=target.name,
                        required_tool=target.required_tool,
                        hits_required=target.hits_required,
                        approach_x=ax, approach_y=ay, face_direction=face,
                    )
        return None

    def find_best_target(self, state: GameState, target_type: str) -> str:
        targets = sorted(self._targets(state, target_type), key=lambda t: t.distance)
        if not targets:
            return f"No targets of type '{target_type}' found nearby."
        for target in targets:
            for ax, ay, face in (
                (target.x - 1, target.y, "right"),
                (target.x + 1, target.y, "left"),
                (target.x, target.y - 1, "down"),
                (target.x, target.y + 1, "up"),
            ):
                if self.is_tile_walkable(state, ax, ay):
                    if target.hits_required > 1:
                        final_action = f"use_tool_repeat with count={target.hits_required}"
                    elif target.hits_required == 0:
                        final_action = "interact"
                    else:
                        final_action = "use_tool"
                    tool = target.required_tool.lower() or "none"
                    return (
                        f"TARGET: {target.name} at ({target.x},{target.y}) - Tool: {target.required_tool} - Hits: {target.hits_required}\n\n"
                        "NOW DO THESE IN ORDER (do NOT call find_best_target again):\n"
                        f"Step 1: select_item name=\"{tool}\"\n"
                        f"Step 2: move_to x={ax} y={ay}\n"
                        f"Step 3: face_direction direction=\"{face}\"\n"
                        f"Step 4: {final_action}"
                    )
        return (f"Found {len(targets)} targets but none have accessible approach tiles. "
                "Try moving to a different area.")

    # ------------------------------------------------------------------ #
    # Blocking actions
    # ------------------------------------------------------------------ #
    async def move_to_blocking(self, x: int, y: int) -> str:
        state = self.state()
        if state is None:
            return "Game disconnected"
        if not state.player.can_move:
            return "Player is currently busy. Wait for animation to finish."
        if not self.is_tile_walkable(state, x, y):
            return f"Target ({x}, {y}) is blocked by an obstacle. Choose an adjacent '.' tile instead."

        resp = await self.commander.execute_parts("move_to", {"x": x, "y": y})
        if not resp.success:
            return f"Move rejected by game: {resp.message}"

        deadline = asyncio.get_event_loop().time() + self.client.config.move_timeout
        while True:
            now_state = self.state()
            if now_state is not None:
                if now_state.player.x == x and now_state.player.y == y:
                    return "Arrived at destination"
                if not now_state.player.is_moving:
                    return (f"Stopped at ({now_state.player.x}, {now_state.player.y}). "
                            "Check surroundings.")
            if asyncio.get_event_loop().time() >= deadline:
                return "Movement timed out."
            await asyncio.sleep(0.2)

    async def clear_target(self, target_type: str) -> str:
        state = self.state()
        if state is None:
            return "Game disconnected"
        info = self.find_best_target_info(state, target_type)
        if info is None:
            return f"No {target_type} targets found nearby."

        if info.required_tool:
            r = await self.commander.execute_parts("select_item", {"name": info.required_tool})
            if not r.success:
                return f"Failed to select {info.required_tool}: {r.message}"
            await asyncio.sleep(0.05)

        move_result = await self.move_to_blocking(info.approach_x, info.approach_y)
        if not move_result.startswith(("Arrived", "Stopped")):
            return f"Failed to reach approach tile: {move_result}"

        face = await self.commander.execute_parts("face_direction", {"direction": info.face_direction})
        if not face.success:
            return f"Failed to face {info.face_direction}: {face.message}"
        await asyncio.sleep(0.05)

        if info.hits_required > 1:
            result = await self.commander.execute("use_tool_repeat", count=info.hits_required)
        elif info.hits_required == 0:
            result = await self.commander.execute("interact")
        else:
            result = await self.commander.execute("use_tool")

        return f"Cleared {info.name} at ({info.x},{info.y}): {result}"

    # ------------------------------------------------------------------ #
    # Context formatting for the LLM
    # ------------------------------------------------------------------ #
    def format_context(self, state: GameState) -> str:
        lines: list[str] = []
        p = state.player
        lines.append(f"Equipped Tool: {p.current_tool} (slot {p.current_tool_index})")

        tif = state.surroundings.tile_in_front
        lines.append(f"\n--- TILE IN FRONT (facing {p.facing_direction_name}) ---")
        lines.append(f"Position: ({tif.x}, {tif.y})")
        if tif.object_name:
            tool = f" [Use: {tif.required_tool}]" if tif.required_tool else ""
            lines.append(f"Object: {tif.object_name}{tool}")
        if tif.terrain_type:
            tool = f" [Use: {tif.required_tool}]" if tif.required_tool else ""
            lines.append(f"Terrain: {tif.terrain_type}{tool}")
        if tif.npc_name:
            lines.append(f"NPC: {tif.npc_name}")
        lines.append("Status: WALKABLE" if tif.is_passable else "Status: BLOCKED")

        if state.surroundings.nearby_buildings:
            lines.append("\n--- BUILDINGS ---")
            for b in state.surroundings.nearby_buildings:
                lines.append(f"- {b.type}: Door at ({b.door_x}, {b.door_y})")

        if state.surroundings.warp_points:
            lines.append("\n--- WARPS/DOORS ---")
            for w in state.surroundings.warp_points:
                lines.append(f"- ({w.x}, {w.y}) -> {w.target_location}")

        debris = [o for o in state.surroundings.nearby_objects if not o.is_passable]
        scythe = sum(1 for o in debris if o.required_tool == "Scythe")
        trees = sum(1 for tf in state.surroundings.nearby_terrain_features
                    if tf.type in ("tree", "fruit_tree"))
        lines.append("\n--- TARGET SUMMARY ---")
        lines.append(f"Debris (stones/twigs/weeds): {len(debris)} ({scythe} use Scythe=0 energy)")
        lines.append(f"Trees: {trees}")
        lines.append(f"NPCs: {len(state.surroundings.nearby_npcs)}")

        lines.append("\n--- NEAREST TARGETS (use find_best_target for full list) ---")
        for obj in debris[:5]:
            tool = obj.required_tool or "unknown"
            lines.append(f"- {obj.display_name or obj.name} at ({obj.x}, {obj.y}) [{tool}]")

        lines.append("\n--- INVENTORY (food items) ---")
        foods = [
            it for it in p.inventory
            if it.category == "Cooking"
            or any(k in it.name.lower() for k in ("salad", "egg", "milk"))
        ]
        if foods:
            for it in foods:
                lines.append(f"- Slot {it.slot}: {it.display_name} (x{it.stack})")
        else:
            lines.append("No food items found.")

        grid = state.surroundings.ascii_map
        if grid:
            lines.append("\n--- ASCII MAP (center 21x21 of 61x61) ---")
            rows = grid.split("\n")
            for y in range(SCAN_RADIUS - 10, SCAN_RADIUS + 11):
                if 0 <= y < len(rows):
                    row = rows[y]
                    start, end = SCAN_RADIUS - 10, SCAN_RADIUS + 11
                    lines.append(row[start:end] if 0 <= start and end <= len(row) else row)

        if state.surroundings.legend:
            lines.append("\n--- MAP LEGEND ---")
            for char, meaning in state.surroundings.legend.items():
                lines.append(f"- '{char}': {meaning}")
        if state.active_mods:
            lines.append("\n--- ACTIVE MODS ---")
            lines.append(", ".join(state.active_mods))

        return "\n".join(lines)