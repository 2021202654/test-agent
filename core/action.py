"""
Action 系统 —— 仿 MetaGPT Action，定义 Agent 可调用的原子能力

一个 Action = 一个工具：
    - name / description / parameters （OpenAI function-calling 格式）
    - run() 方法：执行工具逻辑，返回 Message.reply()
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from .message import Message


class Action(ABC):
    """工具基类。继承它，实现 run()，就是一个 Agent 可用的工具。"""

    name: str = ""
    description: str = ""
    parameters: dict[str, Any] = {}

    @abstractmethod
    async def run(self, **kwargs) -> str:
        """执行工具逻辑。接收 LLM 传入的参数，返回字符串结果。"""
        ...

    def to_openai_schema(self) -> dict[str, Any]:
        """导出为 OpenAI function-calling 格式。"""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }

    def __repr__(self) -> str:
        return f"Action({self.name})"


# ── 工具注册表 ─────────────────────────────────────


class ActionRegistry:
    """管理可用工具集合。

    用法：
        registry = ActionRegistry()
        registry.register(SearchAction())
        schemas = registry.to_openai_schemas()
    """

    def __init__(self):
        self._actions: dict[str, Action] = {}

    def register(self, action: Action) -> None:
        if not action.name:
            raise ValueError(f"Action {action} 缺少 name")
        self._actions[action.name] = action

    def register_many(self, actions: list[Action]) -> None:
        for a in actions:
            self.register(a)

    def get(self, name: str) -> Action | None:
        return self._actions.get(name)

    def list_names(self) -> list[str]:
        return list(self._actions.keys())

    def to_openai_schemas(self) -> list[dict[str, Any]]:
        return [a.to_openai_schema() for a in self._actions.values()]

    def __len__(self) -> int:
        return len(self._actions)

    def __repr__(self) -> str:
        return f"ActionRegistry({self.list_names()})"
