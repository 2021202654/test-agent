"""
LLM Interface Layer — Unified OpenAI-compatible API wrapper
Supports: vLLM / Ollama / Alibaba Bailian / SiliconFlow / any OpenAI-compatible endpoint

Dual-API support:
- Chat Completions API (/chat/completions) — for general models (qwen-plus, DeepSeek-V3, etc.)
- Responses API (/responses) — for code models (qwen3.5-plus, qwen3.7-plus, etc.)
"""

from __future__ import annotations

import json
from typing import Any

import httpx
from pydantic import BaseModel, Field

from .message import Message


# ── Code models that require Responses API (not Chat Completions) ───────────────

_CODE_MODELS = {
    "qwen3.5-plus",
    "qwen3.7-plus",
    "qwen3.5-max",
    "qwen3.7-max",
    # Add future code models here
}


def _is_code_model(model: str) -> bool:
    """Return True if model requires Responses API instead of Chat Completions."""
    return model.lower() in _CODE_MODELS


class LLMConfig(BaseModel):
    """LLM connection configuration."""

    base_url: str = "http://localhost:8000/v1"
    api_key: str = "not-needed"
    model: str = "aero-thermal-expert"
    temperature: float = 0.3
    max_tokens: int = 4096
    timeout: float = 120.0
    preset_name: str = ""  # e.g. "bailian", "siliconflow" — set by AgentConfig factory


class LLMInterface:
    """OpenAI-compatible LLM caller with dual API support."""

    def __init__(self, config: LLMConfig | None = None):
        self.config = config or LLMConfig()
        self._client = httpx.AsyncClient(timeout=self.config.timeout)

    # ── Core API dispatch ───────────────────────────────────────────────────

    async def _call_api(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        tool_choice: str | None = None,
        *,
        response_id: str | None = None,  # For Responses API multi-turn
    ) -> dict[str, Any]:
        """Route to Chat Completions or Responses API based on model type."""
        if _is_code_model(self.config.model):
            return await self._call_responses_api(
                messages, tools=tools, response_id=response_id
            )
        else:
            return await self._call_chat_api(messages, tools=tools, tool_choice=tool_choice)

    # ── Chat Completions API ────────────────────────────────────────────────

    async def _call_chat_api(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        tool_choice: str | None = None,
    ) -> dict[str, Any]:
        """Standard OpenAI Chat Completions API."""
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
        if response.status_code == 400:
            try:
                err_body = response.json()
                err_msg = err_body.get("error", {}).get("message", response.text)
            except Exception:
                err_msg = response.text
            raise RuntimeError(
                f"API 400 Bad Request — {err_msg}\n"
                f"  URL: {url}\n"
                f"  Model: {self.config.model}\n"
                f"  Hint: Check API key validity, quota, and model name."
            )
        response.raise_for_status()
        return response.json()

    # ── Responses API ───────────────────────────────────────────────────────

    async def _call_responses_api(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        *,
        response_id: str | None = None,
    ) -> dict[str, Any]:
        """Alibaba qwen Responses API (required for code models like qwen3.5-plus).

        Differences from Chat Completions:
        - Endpoint: /responses (not /chat/completions)
        - Request: {"model", "input: {"messages": [...]}, "tools": [...], "previous_response_id": ...}
        - Response: {"id", "output": [{type, ...}]}
        """
        url = f"{self.config.base_url.rstrip('/')}/responses"

        # Build input.messages from conversation history
        input_messages = []
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            # Skip empty messages
            if not content and role != "system":
                continue
            input_messages.append({"role": role, "content": content})

        body: dict[str, Any] = {
            "model": self.config.model,
            "input": {"messages": input_messages},
            "temperature": self.config.temperature,
            "max_tokens": self.config.max_tokens,
        }
        if tools:
            body["tools"] = tools
        if response_id:
            body["previous_response_id"] = response_id

        headers = {
            "Authorization": f"Bearer {self.config.api_key}",
            "Content-Type": "application/json",
        }

        response = await self._client.post(url, json=body, headers=headers)
        if response.status_code == 400:
            try:
                err_body = response.json()
                err_msg = err_body.get("error", {}).get("message", response.text)
            except Exception:
                err_msg = response.text
            raise RuntimeError(
                f"API 400 Bad Request (Responses API) — {err_msg}\n"
                f"  URL: {url}\n"
                f"  Model: {self.config.model}\n"
                f"  Hint: qwen3.5-plus is a code model; it requires Responses API."
            )
        response.raise_for_status()
        return response.json()

    # ── Parse Responses API output ──────────────────────────────────────────

    def _parse_responses_output(self, result: dict[str, Any]) -> tuple[Message, str | None]:
        """Extract assistant Message from Responses API output.

        Returns:
            (Message, response_id) — response_id needed for multi-turn tool calls
        """
        response_id = result.get("id")
        output_items: list[dict[str, Any]] = result.get("output", [])

        content = ""
        tool_calls = []

        for item in output_items:
            item_type = item.get("type", "")

            if item_type == "message":
                # Text output
                for content_block in item.get("content", []):
                    if content_block.get("type") == "output_text":
                        content += content_block.get("text", "")

            elif item_type == "function_call":
                # Tool call from code model
                fc = item.get("function_call", {})
                name = fc.get("name", "")
                raw_args = fc.get("arguments", "{}")
                # arguments may be a dict or JSON string — always ensure string for orchestrator
                if isinstance(raw_args, dict):
                    raw_args = json.dumps(raw_args, ensure_ascii=False)
                elif not isinstance(raw_args, str):
                    raw_args = str(raw_args) if raw_args else "{}"

                tool_calls.append({
                    "id": item.get("call_id", f"call_{len(tool_calls)}"),
                    "type": "function",
                    "function": {
                        "name": name,
                        "arguments": raw_args,
                    }
                })

        return Message(
            role="assistant",
            content=content,
            tool_calls=tool_calls if tool_calls else None,
            metadata={"response_id": response_id, "usage": result.get("usage", {})},
        ), response_id

    # ── High-level interface ────────────────────────────────────────────────

    async def chat(self, messages: list[Message]) -> Message:
        """Plain text chat, no tools."""
        openai_msgs = [m.to_openai() for m in messages]
        result = await self._call_api(openai_msgs)

        if _is_code_model(self.config.model):
            msg, _ = self._parse_responses_output(result)
            return msg

        choice = result["choices"][0]["message"]
        return Message.agent(
            content=choice.get("content", ""),
            usage=result.get("usage", {}),
        )

    async def chat_with_tools(
        self,
        messages: list[Message],
        tools: list[dict[str, Any]],
        *,
        _response_id: str | None = None,
    ) -> Message:
        """Tool-augmented chat — returns Message possibly containing tool_calls."""
        openai_msgs = [m.to_openai() for m in messages]
        result = await self._call_api(openai_msgs, tools=tools, response_id=_response_id)

        if _is_code_model(self.config.model):
            return self._parse_responses_output(result)[0]

        choice = result["choices"][0]["message"]
        return Message(
            role="assistant",
            content=choice.get("content") or "",
            tool_calls=choice.get("tool_calls"),
            metadata={"usage": result.get("usage", {})},
        )

    async def close(self):
        await self._client.aclose()
