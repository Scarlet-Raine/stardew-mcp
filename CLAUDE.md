# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Stardew Valley MCP Bridge - A hybrid AI-controlled game mod that bridges Stardew Valley with AI pipelines. Enables autonomous AI agents to control and play Stardew Valley through:
- A C# SMAPI mod running inside the game (serialiizes state, executes commands, hosts WebSocket via System.Net.WebSockets)
- A Python bridge (`stardew_bridge`) that exposes game actions as typed tools over MCP or OpenAI-compatible function calling
- WebSocket-based real-time game state synchronization

## Build Commands

### C# Mod (SMAPI)
Build with a .NET SDK that targets `net6.0` (a .NET 8 SDK is recommended for the ModBuildConfig analyzer). `<GamePath>` in `StardewMCP.csproj` points at the game install; build auto-deploys to `Mods\StardewMCP\`.
```bash
dotnet build mod/StardewMCP/StardewMCP.csproj
```
Launch the game via `StardewModdingAPI.exe` (not the base game exe) to load SMAPI + mods; the mod binds `ws://localhost:8765/game`.

### Python Bridge
```bash
cd bridge
python -m venv .venv
.venv/Scripts/pip install -e ".[mcp,tests]"     # mac/linux: .venv/bin/pip
.venv/Scripts/python -m stardew_bridge.cli --mode tools        # print OpenAI tool schemas
.venv/Scripts/python -m stardew_bridge.cli --mode agent --goal "..."  # autonomous loop
.venv/Scripts/python -m stardew_bridge.cli --mode mcp           # MCP server
.venv/Scripts/python -m stardew_bridge.cli --mode http          # HTTP/OpenAI-style tool server
```
Configure the LLM via `STARDEW_LLM_BASE_URL`/`STARDEW_LLM_API_KEY`/`STARDEW_MODEL` (any OpenAI-compatible endpoint).

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
│   adapters: MCP server • HTTP/OpenAI tools • agent loop │
└─────────────────────────────────────────────────────────┘
              ↕ MCP or OpenAI-compatible tool calling (any provider)
```

### C# Mod Components (`mod/StardewMCP/`)

- **ModEntry.cs**: SMAPI entry point. Initializes WebSocket server, wires components, registers game loop events (Update, OneSecond, SaveLoaded). Broadcasts game state every 1 second, processes commands each frame.

- **CommandExecutor.cs**: Executes game commands (move_to, use_tool, select_item, etc.). Contains A* pathfinding integration, continuous movement processing, tool cooldown tracking (30 ticks between swings). Queue-based command processing - one command per game tick.

- **GameStateSerializer.cs**: Captures complete game state: Player, Time, World, Surroundings. Generates 61x61 ASCII map vision (30-tile scan radius). Serializes NPCs, items, terrain, quests, relationships, skills.

- **WebSocketServer.cs**: Server on `ws://localhost:8765/game` using `System.Net.WebSockets` over an `HttpListener`. Message types: "command", "get_state", "ping". Response types: "state", "response", "error", "pong". Thread-safe, serialized sends.

- **Pathfinder.cs**: A* algorithm for navigation. 4-directional movement, 50,000 iteration limit, Manhattan distance heuristic. Checks walkability across tiles, objects, terrain features, buildings, furniture, water.

### Python Bridge Components (`bridge/`)

- **ws_client.py**: Async `GameClient` — connect/reconnect, 15s keepalive, per-command responses correlated by `id` (15s timeout), waits for the first state snapshot.
- **models.py**: Pydantic models mirroring the game's camelCase state (player, surroundings, tile in front, activeMods, legend).
- **tools/**: Single declarative typed tool registry (12 standard + ~50 cheat tools). Each tool defined once, surfaced as MCP and OpenAI functions.
- **brain.py**: Targeting, structured walkability, blocking `move_to`, `clear_target`, LLM context formatting.
- **knowledge.py**: Embedded game knowledge (legend, seed IDs, survival rules) + dynamic prompt builder (injects legend + active mods).
- **mcp.py / http_adapter.py**: MCP server (lazy `mcp` import) and HTTP adapter (`/v1/tools`, `/v1/tool`) from the shared registry.
- **llm.py / agent.py**: Provider-agnostic client (any OpenAI-compatible endpoint) + optional autonomous loop.

## WebSocket Protocol

**Request**:
```json
{"id": "uuid", "type": "command", "action": "move_to", "params": {"x": 10, "y": 20}}
```

**Response**:
```json
{"id": "uuid", "type": "response", "success": true, "message": "...", "data": {...}}
```

## Key Design Patterns

- **Queue-based command execution**: One command per game frame prevents desync
- **Async state broadcasting**: Game state sent every 1 second, separate from command processing
- **Path recalculation**: Up to 5 attempts if initial pathfinding fails
- **Tool cooldown**: 30-tick gaps between tool swings (0.5s at 60fps)
- **Mutex-protected tool execution**: Prevents concurrent tool usage in agent
- **Embedded knowledge base**: Game mechanics, seed IDs, and survival rules baked into the bridge's knowledge.py
- **Mod-aware state**: The mod emits `activeMods` + a live ASCII `legend`, and agents read structured passability flags, so play works with extra mods installed.

## Cheat Mode

Cheat mode provides instant god-mode capabilities. Must call `cheat_mode_enable` before using any cheat commands.

**Categories:**
- **Mode Control**: cheat_mode_enable, cheat_mode_disable, cheat_time_freeze, cheat_infinite_energy
- **Teleportation**: cheat_warp (location), cheat_mine_warp (level)
- **Farming Automation**: cheat_hoe_all, cheat_water_all, cheat_grow_crops, cheat_harvest_all, cheat_plant_seeds, cheat_fertilize_all
- **Land Clearing**: cheat_clear_debris, cheat_cut_trees, cheat_mine_rocks, cheat_dig_artifacts
- **Pattern Drawing**: cheat_hoe_tiles, cheat_clear_tiles, cheat_hoe_custom_pattern (ASCII grid input)
- **Resources**: cheat_set_money, cheat_add_item (by item ID), cheat_spawn_ores
- **Social**: cheat_set_friendship, cheat_max_all_friendships, cheat_give_gift
- **Upgrades**: cheat_upgrade_backpack, cheat_upgrade_tool, cheat_upgrade_all_tools, cheat_unlock_all
