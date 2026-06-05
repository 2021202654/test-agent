"""
消息系统 —— Agent 内外部通信的基本单元
仿 MetaGPT Message，只保留核心字段
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class Message(BaseModel):
    """统一消息体。

    覆盖四种来源：
    - role="user"    用户输入
    - role="agent"   Agent 最终回复
    - role="system"  系统指令
    - role="tool"    工具调用结果
    """

    role: str = "user"
    content: str = ""
    # 工具调用相关（OpenAI function-calling 格式）
    tool_calls: list[dict[str, Any]] | None = None
    tool_call_id: str | None = None
    tool_name: str | None = None
    # 元数据
    metadata: dict[str, Any] = Field(default_factory=dict)
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())

    @classmethod
    def user(cls, content: str, **meta) -> "Message":
        return cls(role="user", content=content, metadata=meta)

    @classmethod
    def agent(cls, content: str, **meta) -> "Message":
        return cls(role="agent", content=content, metadata=meta)

    @classmethod
    def system(cls, content: str, **meta) -> "Message":
        return cls(role="system", content=content, metadata=meta)

    @classmethod
    def tool_result(cls, content: str, tool_call_id: str, tool_name: str) -> "Message":
        return cls(
            role="tool",
            content=content,
            tool_call_id=tool_call_id,
            tool_name=tool_name,
        )

    def to_openai(self) -> dict[str, Any]:
        """转为 OpenAI Chat Completions API 格式。"""
        msg: dict[str, Any] = {"role": self.role, "content": self.content}
        if self.tool_calls:
            msg["tool_calls"] = self.tool_calls
        if self.tool_call_id:
            msg["tool_call_id"] = self.tool_call_id
        return msg

    def __str__(self) -> str:
        return f"[{self.role}] {self.content[:120]}{'...' if len(self.content) > 120 else ''}"
