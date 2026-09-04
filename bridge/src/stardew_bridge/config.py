"""Runtime configuration for the Stardew bridge."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Optional

DEFAULT_WS_URL = "ws://localhost:8765/game"


@dataclass
class Config:
    """Bridge configuration. Values can come from env vars or CLI args."""

    # Game connection
    ws_url: str = field(default_factory=lambda: os.environ.get("STARDEW_WS_URL", DEFAULT_WS_URL))
    connect_timeout: float = 10.0
    reconnect_delay: float = 5.0
    command_timeout: float = 15.0
    keepalive_interval: float = 15.0
    move_timeout: float = 30.0

    # LLM / agent
    auto: bool = True
    goal: str = ""
    model: str = field(default_factory=lambda: os.environ.get("STARDEW_MODEL", "gpt-4.1"))
    llm_base_url: Optional[str] = field(
        default_factory=lambda: os.environ.get("STARDEW_LLM_BASE_URL")
    )
    llm_api_key: Optional[str] = field(
        default_factory=lambda: os.environ.get("STARDEW_LLM_API_KEY", os.environ.get("OPENAI_API_KEY"))
    )

    # Server adapters
    mcp_transport: str = "stdio"  # stdio | http
    mcp_host: str = "127.0.0.1"
    mcp_port: int = 8800
    openai_host: str = "127.0.0.1"
    openai_port: int = 8801


DEFAULT_GOAL = """USE CHEAT MODE to setup the farm:
1. cheat_mode_enable first
2. cheat_clear_debris, cheat_cut_trees, cheat_mine_rocks
3. cheat_hoe_all to till soil
4. cheat_plant_seeds season appropriate seeds
5. cheat_grow_crops then cheat_harvest_all"""


def build_config(
    ws_url: str | None = None,
    auto: bool | None = None,
    goal: str | None = None,
    model: str | None = None,
) -> Config:
    cfg = Config()
    if ws_url:
        cfg.ws_url = ws_url
    if auto is not None:
        cfg.auto = auto
    if goal:
        cfg.goal = goal
    else:
        cfg.goal = DEFAULT_GOAL
    if model:
        cfg.model = model
    return cfg