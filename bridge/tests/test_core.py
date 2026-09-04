"""Unit tests for parsing, walkability, targeting, and schema generation."""
from __future__ import annotations

from stardew_bridge.brain import Brain, _normalize_target_type
from stardew_bridge.models import WebSocketResponse, game_state_from_dict
from stardew_bridge.tools import build_registry
from conftest import make_map_state_dict


class _Commander:
    def __init__(self):
        self.calls = []

    def execute_parts(self, action, params=None):
        self.calls.append((action, params))
        return None

    async def execute_parts(self, action, params=None):
        return self.execute_parts(action, params)

    async def execute(self, action, **params):
        self.calls.append((action, params))
        return f"{action} ok"


class _Client:
    def __init__(self, state):
        self._state = state
        self.config = type("Cfg", (), {"move_timeout": 5.0})()

    def state(self):
        return self._state


def _brain(state):
    client = _Client(state)
    comm = _Commander()
    return Brain(client, comm), comm


def test_parse_state_camel_and_snake():
    d = make_map_state_dict()
    # camelCase input
    st = game_state_from_dict(d)
    assert st.player.name == "TestFarmer"
    assert st.player.location == "Farm"
    assert st.surroundings.nearby_objects[0].required_tool == "Pickaxe"
    assert st.active_mods == ["SomeCoolContentPack"]
    # snake_case construction works via populate_by_name alias
    st2 = game_state_from_dict({"player": {"name": "X", "location": "Town"}})
    assert st2.player.name == "X"


def test_walkability_from_ascii():
    st = game_state_from_dict(make_map_state_dict())
    brain, _ = _brain(st)
    assert brain.is_tile_walkable(st, 5, 5) is True            # @ self
    assert brain.is_tile_walkable(st, 6, 5) is True            # '.' ground
    assert brain.is_tile_walkable(st, 7, 5) is False           # 'O' stone
    assert brain.is_tile_walkable(st, 5, 8) is False           # '~' water (also nearbyTiles)
    assert brain.is_tile_walkable(st, 3, 6) is False           # 'T' tree
    assert brain.is_tile_walkable(st, 5, 36) is False          # out of radius (dy=31)


def test_normalize_target_type():
    assert _normalize_target_type("rocks") == "debris"
    assert _normalize_target_type("trees") == "tree"
    assert _normalize_target_type("crops") == "crop"
    assert _normalize_target_type("villager") == "npc"
    assert _normalize_target_type("all") == "any"


def test_find_best_target_info_approach():
    st = game_state_from_dict(make_map_state_dict())
    brain, _ = _brain(st)
    info = brain.find_best_target_info(st, "stone")
    assert info is not None
    # Target is the stone at (7,5); an approach tile west (6,5) is walkable -> face "right" (east) at it.
    assert (info.x, info.y) == (7, 5)
    assert info.required_tool == "Pickaxe"
    assert info.hits_required == 1
    assert info.approach_x == 6 and info.approach_y == 5
    assert info.face_direction == "right"


def test_find_best_target_string_instructs_steps():
    st = game_state_from_dict(make_map_state_dict())
    brain, _ = _brain(st)
    out = brain.find_best_target(st, "debris")
    assert "select_item" in out
    assert "Pickaxe" in out
    assert "move_to x=6 y=5" in out


def test_format_context_includes_mods_and_legend():
    st = game_state_from_dict(make_map_state_dict())
    brain, _ = _brain(st)
    ctx = brain.format_context(st)
    assert "Equipped Tool: Axe" in ctx
    assert "ACTIVE MODS" in ctx and "SomeCoolContentPack" in ctx
    assert "Salad" in ctx  # food inventory


def test_registry_has_all_tools():
    reg = build_registry()
    names = set(reg.names())
    for expected in ("move_to", "get_surroundings", "interact", "use_tool", "use_tool_repeat",
                     "face_direction", "select_item", "switch_tool", "eat_item", "enter_door",
                     "find_best_target", "clear_target", "cheat_mode_enable", "cheat_warp"):
        assert expected in names


def test_openai_schema_format():
    reg = build_registry()
    funcs = reg.openai_functions()
    by_name = {f["function"]["name"]: f["function"] for f in funcs}
    move = by_name["move_to"]
    assert move["parameters"]["type"] == "object"
    assert "x" in move["parameters"]["properties"]
    assert "y" in move["parameters"]["required"]
    # aliased camelCase params surface correctly (e.g. cheat_add_item uses itemId)
    add = by_name["cheat_add_item"]
    assert "itemId" in add["parameters"]["properties"]


def test_response_parsing():
    raw = {"id": "abc", "type": "response", "success": True, "message": "done", "data": {"x": 1}}
    resp = WebSocketResponse.model_validate(raw)
    assert resp.success is True and resp.id == "abc"