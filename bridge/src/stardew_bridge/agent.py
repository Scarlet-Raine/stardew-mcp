"""Autonomous agent loop.

Port of Go `copilot_agent.go` runAutonomousLoop, driven through the registry + a
provider-agnostic LLM client instead of the GitHub Copilot SDK.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Optional

from .brain import Brain
from .commands import GameCommander
from .config import Config
from .knowledge import build_decision_prompt, build_system_prompt, urgency_for
from .llm import LLMClient
from .models import GameState
from .tools.base import ToolRegistry, ToolContext
from .ws_client import GameClient

logger = logging.getLogger("stardew_bridge.agent")

_COMPLETE_MARKERS = (
    "GOAL COMPLETE", "GOAL COMPLETED", "ALL TASKS COMPLETE", "MISSION ACCOMPLISHED",
)


def make_tool_context(client: GameClient, registry: ToolRegistry, config: Config) -> ToolContext:
    commander = GameCommander(client)
    brain = Brain(client, commander)
    return ToolContext(client=client, commander=commander, brain=brain, config=config)


class Agent:
    def __init__(
        self,
        client: GameClient,
        registry: ToolRegistry,
        llm: Optional[LLMClient],
        config: Config,
    ) -> None:
        self.client = client
        self.registry = registry
        self.llm = llm
        self.config = config
        self.ctx = make_tool_context(client, registry, config)
        self._history: list[dict] = []
        self.goal_complete = False

    async def run(self, goal: str) -> None:
        consecutive_errors = 0
        iteration = 0
        while True:
            iteration += 1
            state = self.client.state()
            if state is None:
                await asyncio.sleep(2)
                consecutive_errors += 1
                continue
            consecutive_errors = 0

            urgency = urgency_for(state)
            if state.player.is_moving or not state.player.can_move:
                await asyncio.sleep(0.1)
                continue

            logger.info("[AGENT LOOP] %d: %s at (%d,%d) energy=%.0f",
                        iteration, state.player.location, state.player.x, state.player.y,
                        state.player.energy)

            include_context = "cheat" not in goal.lower()
            context = self.ctx.brain.format_context(state) if include_context else ""
            prompt = build_decision_prompt(state, goal, urgency, context)

            # Conversation: keep it short to bound token usage.
            messages = [{"role": "system", "content": build_system_prompt(state)}]
            if self._history:
                messages.append({"role": "user", "content": self._history[-1]})
            else:
                messages.append({"role": "user", "content": prompt})
            if len(self._history) > 2:  # reset stray assistant turns
                self._history = [self._history[-1]]
            self._history.append(prompt)

            await self._step(messages)
            if self.goal_complete:
                logger.info("[AGENT LOOP] Goal completed! Pausing.")
                self.goal_complete = False
                await asyncio.sleep(30)
            else:
                await asyncio.sleep(0.1 if urgency else 0.25)

    async def _step(self, messages: list[dict]) -> None:
        if self.llm is None:
            logger.warning("No LLM configured; not driving the agent.")
            return
        tools = self.registry.openai_functions()
        for _guard in range(20):  # bound tool-calling turns per step
            result = await self.llm.chat(messages, tools=tools)
            # Record assistant turn
            msgs_state = result.content or ""
            if msgs_state:
                logger.info("[AGENT THOUGHT] %s", msgs_state)
            if msgs_state and any(m in msgs_state.upper() for m in _COMPLETE_MARKERS):
                self.goal_complete = True
                return
            if msgs_state:
                self._history.append(msgs_state)

            if not result.tool_calls:
                return
            for tc in result.tool_calls:
                out = await self.registry.call(tc.name, tc.arguments, self.ctx)
                messages.append({"role": "assistant", "content": msgs_state or "",
                                 "tool_calls": [{
                                     "id": tc.id, "type": "function",
                                     "function": {"name": tc.name, "arguments": str(tc.arguments)}}]})
                messages.append({"role": "tool", "tool_call_id": tc.id, "content": out})
        logger.warning("Agent hit tool-call turn limit for a single step.")