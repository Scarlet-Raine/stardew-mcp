# Stardew MCP Bridge

A hybrid AI-controlled game bridge that lets AI agents play **Stardew Valley** through a clean
tool interface. It has two parts:

- A **C# SMAPI mod** that runs inside the game: it serializes live game state, executes
  commands (movement, tools, cheats), and serves a WebSocket endpoint.
- A **Python bridge** that connects to the game, exposes every game action as typed tools, and
  surfaces them to your AI pipeline over **MCP** or **OpenAI-compatible function calling**.

You can drive it from any agent stack (Anthropic, OpenAI, xAI, Gemini, local models, etc.)
without touching the game or the mod.

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│ STARDEW VALLEY (Game)                                   │
│   SMAPI Mod (C# .NET 6)                                 │
│     ModEntry → GameStateSerializer (mod-aware state)    │
│              → CommandExecutor (w/ Pathfinder)          │
│              → WebSocketServer (System.Net.WebSockets)  │
└─────────────────────────────────────────────────────────┘
              ↕ ws://localhost:8765/game
┌─────────────────────────────────────────────────────────┐
│ Python Bridge (stardew_bridge)                          │
│   GameClient (WebSocket, state, response correlation)   │
│   Tool Registry: 12 standard + ~50 cheat tools          │
│   Brain: targeting, walkability, context formatting     │
│   ┌─────────────── adapters ──────────────────────────┐ │
│   │ MCP server (MCP) • HTTP/OpenAI-style tools        │ │
│   │ optional autonomous loop (any LLM provider)       │ │
│   └───────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────┘
              ↕ MCP or OpenAI-compatible tool calling
┌─────────────────────────────────────────────────────────┐
│ Your AI pipeline / agent (MCP client or tool-calling)   │
│   Anthropic / OpenAI / xAI / Gemini, etc.               │
└─────────────────────────────────────────────────────────┘
```

## Requirements

### C# Mod
- Stardew Valley 1.6 with **SMAPI** installed (launch the game via `StardewModdingAPI.exe`).
- A .NET SDK that can target `net6.0` (a .NET 8 SDK is recommended — the ModBuildConfig
  analyzer needs a recent compiler).
- Microsoft Build Tools / `dotnet` CLI.

### Python Bridge
- Python 3.11+
- Optional: the `mcp` package (for the MCP server), and any provider's OpenAI-compatible endpoint.

## Build & Install

### 1. Build the C# mod

```bash
dotnet build D:\dev\stardew-mcp\mod\StardewMCP\StardewMCP.csproj
```

The `<GamePath>` in `StardewMCP.csproj` points ModBuildConfig at your Stardew Valley install.
The build **auto-deploys** the mod to `<GamePath>\Mods\StardewMCP\` and writes a release zip.

### 2. Install & launch the mod in-game

- Install SMAPI into the game if you haven't (it must be present in `<GamePath>\StardewModdingAPI.exe`).
- Launch the game with `StardewModdingAPI.exe` (not the base game exe), and load a save.
- The mod logs `WebSocket server started on ws://localhost:8765/game` and serves state
  once a world is loaded.

### 3. Install the Python bridge

```bash
cd bridge
python -m venv .venv
.venv/Scripts/pip install -e ".[mcp,tests]"     # mac/linux: .venv/bin/pip
```

This installs the `stardew-bridge` package and CLI.

## Using the Python bridge

```bash
cd bridge

# Print all OpenAI-compatible tool schemas (no game needed)
.venv/Scripts/python -m stardew_bridge.cli --mode tools

# Connect and run the autonomous agent loop (configure LLM below)
.venv/Scripts/python -m stardew_bridge.cli --mode agent --goal "Clear the farm and plant parsnips"

# Expose tools as an MCP server (stdio)
.venv/Scripts/python -m stardew_bridge.cli --mode mcp

# Expose tools as HTTP endpoints (OpenAI-style schemas) on :8801
.venv/Scripts/python -m stardew_bridge.cli --mode http

# Connect without starting an agent
.venv/Scripts/python -m stardew_bridge.cli --mode http --no-auto
```

LLM configuration for the autonomous loop (any OpenAI-compatible endpoint):

| Env var | Purpose |
|---|---|
| `STARDEW_LLM_BASE_URL` | OpenAI-compatible base URL (OpenAI, xAI, Gemini, Anthropic compat mode) |
| `STARDEW_LLM_API_KEY` / `OPENAI_API_KEY` | API key for the endpoint |
| `STARDEW_MODEL` | Model name to use |
| `STARDEW_WS_URL` | Game WebSocket URL (default `ws://localhost:8765/game`) |

Equivalents are available as CLI flags (`--model`, `--llm-base-url`, `--llm-api-key`, `--ws-url`).

### Python bridge design

Each game action is defined **once** as a typed tool and surfaced through multiple interfaces
(MCP, OpenAI-compatible JSON, or direct calls). Targeting and walkability use **structured
passability flags** plus the live ASCII **map legend**, and the mod reports the **loaded mod
list** — so agents stay robust even when the game has extra mods installed.

## WebSocket Protocol

**Request** (from bridge to mod):

```json
{"id": "uuid", "type": "command", "action": "move_to", "params": {"x": 10, "y": 20}}
```

**State / response** (from mod to bridge):

```json
{"id": "uuid", "type": "state", "success": true, "data": {...}}
{"id": "uuid", "type": "response", "success": true, "message": "...", "data": {...}}
```

The mod also broadcasts a `state` message every second and answers `ping` with `pong`.

## Cheat Mode

Cheat mode provides instant god-mode capabilities. Call `cheat_mode_enable` before using any
cheat command.

**Categories**
- **Mode control**: `cheat_mode_enable`, `cheat_mode_disable`, `cheat_time_freeze`, `cheat_infinite_energy`
- **Teleportation**: `cheat_warp`, `cheat_mine_warp`
- **Farming**: `cheat_hoe_all`, `cheat_water_all`, `cheat_grow_crops`, `cheat_harvest_all`, `cheat_plant_seeds`, `cheat_fertilize_all`
- **Land clearing**: `cheat_clear_debris`, `cheat_cut_trees`, `cheat_mine_rocks`, `cheat_dig_artifacts`
- **Pattern drawing**: `cheat_hoe_tiles`, `cheat_clear_tiles`, `cheat_hoe_custom_pattern`
- **Resources**: `cheat_set_money`, `cheat_add_item`, `cheat_spawn_ores`
- **Social**: `cheat_set_friendship`, `cheat_max_all_friendships`, `cheat_give_gift`
- **Upgrades**: `cheat_upgrade_backpack`, `cheat_upgrade_tool`, `cheat_upgrade_all_tools`, `cheat_unlock_all`

## Mod-aware state & extra mods

The mod emits two extra fields so agents can adapt to modded games:

- `activeMods` — the list of installed SMAPI mods/content packs (queried from the mod registry).
- `legend` — a live map of ASCII map characters to their meanings.

Agents read structured `isPassable` flags and the legend instead of assuming a hardcoded
tileset, fall back to generic tools/interact on unknown items, and see the mod list in their
prompt — enabling play with 100+ mods installed.

## Notes

- The mod's WebSocket server uses .NET's built-in `System.Net.WebSockets` (served over
  `HttpListener`), not WebSocketSharp. It is thread-safe and keeps connections stable across
  many commands.
- The legacy Go server was fully replaced by the Python bridge and removed from this repo.