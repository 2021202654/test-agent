"""
LLM 接口层 —— 统一封装 OpenAI 兼容 API
支持：vLLM / Ollama / 阿里云百炼 / 任何 OpenAI-compatible endpoint
"""

from __future__ import annotations

import json
from typing import Any

import httpx
from pydantic import BaseModel, Field

from .message import Message


class LLMConfig(BaseModel):
    """LLM 连接配置。"""

    base_url: str = "http://localhost:8000/v1"
    api_key: str = "not-needed"
    model: str = "aero-thermal-expert"
    temperature: float = 0.3
    max_tokens: int = 2048
    timeout: float = 120.0


class LLMInterface:
    """OpenAI 兼容的 LLM 调用接口。

    用法：
        llm = LLMInterface(LLMConfig(base_url="...", model="..."))
        reply = await llm.chat(messages)
        reply_with_tools = await llm.chat_with_tools(messages, tools)
    """

    def __init__(self, config: LLMConfig | None = None):
        self.config = config or LLMConfig()
        self._client = httpx.AsyncClient(timeout=self.config.timeout)

    # ── 底层 API 调用 ──────────────────────────────

    async def _call_api(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        tool_choice: str | None = None,
    ) -> dict[str, Any]:
        """发送请求到 OpenAI 兼容 API。"""
        url = f"{self.config.base_url.rstrip('/')}/chat/completions"

        body: dict[str, Any] = {
            "model": self.config.model,
            "messages": messages,
            "temperature": self.config.temperature,
            "max_tokens": self.config.max_tokens,
        }
        if tools:
            body["tools"] = tools
            body["tool_choice"] = tool_choice or "auto"

        headers = {
            "Authorization": f"Bearer {self.config.api_key}",
            "Content-Type": "application/json",
        }

        response = await self._client.post(url, json=body, headers=headers)
        response.raise_for_status()
        return response.json()

    # ── 高层接口 ───────────────────────────────────

    async def chat(self, messages: list[Message]) -> Message:
        """纯文本对话，不带工具。"""
        openai_msgs = [m.to_openai() for m in messages]
        result = await self._call_api(openai_msgs)
        choice = result["choices"][0]["message"]
        return Message.agent(
            content=choice.get("content", ""),
            usage=result.get("usage", {}),
        )

    async def chat_with_tools(
        self,
        messages: list[Message],
        tools: list[dict[str, Any]],
    ) -> Message:
        """工具增强对话 —— 返回的 Message 可能包含 tool_calls。"""
        openai_msgs = [m.to_openai() for m in messages]
        result = await self._call_api(openai_msgs, tools=tools)

        choice = result["choices"][0]["message"]
        msg = Message(
            role="assistant",
            content=choice.get("content") or "",
            tool_calls=choice.get("tool_calls"),
            metadata={"usage": result.get("usage", {})},
        )
        return msg

    async def close(self):
        await self._client.aclose()
