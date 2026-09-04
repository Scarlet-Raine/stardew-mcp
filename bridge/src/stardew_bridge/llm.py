"""Provider-agnostic LLM client speaking the OpenAI-compatible chat/completions API.

Works with OpenAI, xAI, Google Gemini (OpenAI-compat endpoint), and Anthropic's
OpenAI-compatible mode by pointing ``base_url`` and ``model`` at the desired provider.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Optional

import httpx

logger = logging.getLogger("stardew_bridge.llm")


@dataclass
class ToolCall:
    id: str
    name: str
    arguments: dict[str, Any]


@dataclass
class ChatResult:
    content: Optional[str] = None
    tool_calls: list[ToolCall] = field(default_factory=list)


class LLMClient:
    """Thin async client for chat completions with tool calling."""

    def __init__(
        self,
        base_url: Optional[str],
        api_key: Optional[str],
        model: str,
        timeout: float = 120.0,
    ) -> None:
        self.base_url = (base_url or "https://api.openai.com/v1").rstrip("/")
        self.api_key = api_key
        self.model = model
        self.timeout = timeout
        self._client = httpx.AsyncClient(timeout=timeout)

    async def aclose(self) -> None:
        await self._client.aclose()

    def _headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    async def chat(
        self,
        messages: list[dict[str, Any]],
        tools: Optional[list[dict[str, Any]]] = None,
        tool_choice: Optional[Any] = "auto",
    ) -> ChatResult:
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
        }
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = tool_choice
        logger.info("[LLM] Sending request (%d messages, %d tools)", len(messages), len(tools or []))
        resp = await self._client.post(
            f"{self.base_url}/chat/completions", headers=self._headers(), json=payload
        )
        resp.raise_for_status()
        data = resp.json()

        choice = data["choices"][0]["message"]
        content = choice.get("content")
        tool_calls: list[ToolCall] = []
        for tc in choice.get("tool_calls") or []:
            try:
                import json

                args = json.loads(tc.get("function", {}).get("arguments") or "{}")
            except Exception:  # noqa: BLE001
                args = {}
            tool_calls.append(
                ToolCall(id=tc.get("id", ""), name=tc.get("function", {}).get("name", ""), arguments=args)
            )
        return ChatResult(content=content, tool_calls=tool_calls)