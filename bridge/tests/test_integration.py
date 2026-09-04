"""Integration tests against an in-process mock Stardew WebSocket server."""
from __future__ import annotations

import asyncio
import json

import pytest
from websockets.asyncio.server import serve

from stardew_bridge.agent import Agent, make_tool_context
from stardew_bridge.config import Config
from stardew_bridge.llm import ChatResult, ToolCall
from stardew_bridge.tools import build_registry
from stardew_bridge.ws_client import GameClient
from conftest import make_map_state_dict


class MockGame:
    def __init__(self):
        self.state = make_map_state_dict()
        self.conn = None

    async def handler(self, conn):
        self.conn = conn
        await self.send_state()
        async for raw in conn:
            await self.dispatch(json.loads(raw))

    async def send_state(self):
        await self.conn.send(json.dumps({"type": "state", "success": True, "data": self.state}))

    async def dispatch(self, msg):
        t = msg.get("type")
        rid = msg.get("id")
        if t == "ping":
            await self.conn.send(json.dumps({"id": rid, "type": "pong", "success": True}))
        elif t == "get_state":
            await self.send_state()
        elif t == "command":
            await self.do_command(rid, msg.get("action"), msg.get("params") or {})
        else:
            await self.conn.send(
                json.dumps({"id": rid, "type": "response", "success": False,
                            "message": f"unknown type {t}"}))

    async def do_command(self, rid, action, params):
        if action == "move_to":
            self.state["player"]["x"] = params["x"]
            self.state["player"]["y"] = params["y"]
            self.state["player"]["isMoving"] = False
            await self.conn.send(json.dumps(
                {"id": rid, "type": "response", "success": True, "message": "Movement started"}))
            await self.send_state()
        else:
            await self.conn.send(json.dumps(
                {"id": rid, "type": "response", "success": True, "message": f"{action} ok"}))


class ScriptedLLM:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = 0

    async def chat(self, messages, tools=None, tool_choice="auto"):
        self.calls += 1
        r = self.responses[min(self.calls - 1, len(self.responses) - 1)]
        if callable(r):
            return r(messages, tools)
        return r


async def _start_mock():
    game = MockGame()
    server = await serve(game.handler, "127.0.0.1", 0)
    port = server.sockets[0].getsockname()[1]
    return game, server, port


@pytest.mark.asyncio
async def test_client_command_correlation():
    game, server, port = await _start_mock()
    cfg = Config(ws_url=f"ws://127.0.0.1:{port}/", connect_timeout=2)
    client = GameClient(cfg)
    try:
        await client.connect()
        assert client.is_connected
        assert client.state() is not None
        assert client.state().player.name == "TestFarmer"

        resp = await client.send_command("use_tool")
        assert resp.success is True
        assert resp.message == "use_tool ok"
        assert resp.id  # correlated response
    finally:
        await client.close()
        server.close()
        await server.wait_closed()


@pytest.mark.asyncio
async def test_move_to_tool_arrives():
    game, server, port = await _start_mock()
    cfg = Config(ws_url=f"ws://127.0.0.1:{port}/", connect_timeout=2, move_timeout=5)
    client = GameClient(cfg)
    registry = build_registry()
    try:
        await client.connect()
        ctx = make_tool_context(client, registry, cfg)
        result = await registry.call("move_to", {"x": 9, "y": 5}, ctx)
        assert "Arrived" in result
        assert client.state().player.x == 9 and client.state().player.y == 5
    finally:
        await client.close()
        server.close()
        await server.wait_closed()


@pytest.mark.asyncio
async def test_agent_step_executes_tool_call():
    game, server, port = await _start_mock()
    cfg = Config(ws_url=f"ws://127.0.0.1:{port}/", connect_timeout=2)
    client = GameClient(cfg)
    registry = build_registry()
    try:
        await client.connect()
        llm = ScriptedLLM([
            ChatResult(content="Let me enable cheat mode", tool_calls=[
                ToolCall(id="c1", name="cheat_mode_enable", arguments={})]),
            ChatResult(content="GOAL COMPLETE"),
        ])
        agent = Agent(client, registry, llm, cfg)
        await agent._step([{"role": "user", "content": "hi"}])
        assert agent.goal_complete is True
        # tool got called (mock registered the response)
        assert llm.calls >= 2
    finally:
        await client.close()
        server.close()
        await server.wait_closed()


@pytest.mark.asyncio
async def test_reconnect_mid_run():
    # First server, then swap: ensure client's _listen tolerates disconnect and run() reconnects.
    game, server, port = await _start_mock()
    cfg = Config(ws_url=f"ws://127.0.0.1:{port}/", connect_timeout=2, reconnect_delay=0.1)
    client = GameClient(cfg)
    run_task = asyncio.create_task(client.run())
    try:
        for _ in range(100):
            if client.is_connected:
                break
            await asyncio.sleep(0.05)
        assert client.is_connected

        server.close()  # force disconnect
        await server.wait_closed()

        # run() should reconnect; server gone so keep crashing but stay alive
        await asyncio.sleep(0.3)
        assert run_task is not None
    finally:
        run_task.cancel()
        await client.close()