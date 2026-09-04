"""Command-line entrypoint: connect to the game and run a mode.

Modes:
  agent  - autonomous agent loop calling the LLM through tools (default)
  mcp    - expose tools as an MCP server (stdio by default)
  http   - expose tools as HTTP endpoints (OpenAI-style schemas)
  tools  - print the OpenAI tool schemas and exit (no connection required)
"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys

from . import __version__
from .agent import Agent
from .config import build_config
from .llm import LLMClient
from .tools import build_registry
from .ws_client import GameClient


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(prog="stardew-bridge", description="Stardew <-> AI bridge")
    p.add_argument("--version", action="version", version=__version__)
    p.add_argument("--ws-url", help="WebSocket URL of the Stardew mod (default ws://localhost:8765/game)")
    p.add_argument("--mode", choices=["agent", "mcp", "http", "tools"], default="agent",
                   help="run mode (default: agent)")
    p.add_argument("--no-auto", action="store_true", help="disable the autonomous agent")
    p.add_argument("--goal", help="autonomous agent goal")
    p.add_argument("--model", help="LLM model name")
    p.add_argument("--llm-base-url", help="OpenAI-compatible base URL")
    p.add_argument("--llm-api-key", help="API key for the LLM endpoint")
    p.add_argument("--mcp-transport", choices=["stdio", "http"], default="stdio")
    p.add_argument("--http-host", default=None)
    p.add_argument("--http-port", type=int, default=None)
    p.add_argument("-v", "--verbose", action="store_true")
    return p.parse_args(argv)


def _setup_logging(verbose: bool) -> None:
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )


async def _amain(args: argparse.Namespace) -> int:
    auto = not args.no_auto
    cfg = build_config(ws_url=args.ws_url, auto=auto, goal=args.goal, model=args.model)
    if args.llm_base_url:
        cfg.llm_base_url = args.llm_base_url
    if args.llm_api_key:
        cfg.llm_api_key = args.llm_api_key
    if args.http_host:
        cfg.openai_host = args.http_host
    if args.http_port:
        cfg.openai_port = args.http_port
    cfg.mcp_transport = args.mcp_transport

    registry = build_registry()

    # `tools` mode needs no game connection.
    if args.mode == "tools":
        print(json.dumps(registry.openai_functions(), indent=2))
        return 0

    client = GameClient(cfg)
    run_task = asyncio.create_task(client.run())
    # wait for first successful connection
    try:
        while not client.is_connected:
            await asyncio.sleep(0.2)
    except asyncio.CancelledError:
        run_task.cancel()
        raise

    from .http_adapter import HttpAdapter
    from .mcp import McpAdapter

    if args.mode == "http":
        HttpAdapter(client, registry, cfg).start_sync()
        while True:
            await asyncio.sleep(3600)

    if args.mode == "mcp":
        mcp_adapter = McpAdapter(client, registry, cfg)
        await mcp_adapter.run(transport=cfg.mcp_transport)
        return 0

    # agent mode
    if not cfg.auto:
        logging.getLogger("stardew_bridge").info("Connected. Autonomous agent disabled (-auto=false).")
        while True:
            await asyncio.sleep(3600)

    llm = LLMClient(cfg.llm_base_url, cfg.llm_api_key, cfg.model)
    agent = Agent(client, registry, llm, cfg)
    await agent.run(cfg.goal)
    return 0


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    _setup_logging(args.verbose)
    try:
        return asyncio.run(_amain(args))
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    sys.exit(main())