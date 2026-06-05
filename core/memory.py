"""
记忆系统 —— 仿 MetaGPT Memory，管理 Agent 的三种记忆

- 短期记忆：当前对话窗口（滑动窗口，自动截断）
- 工作记忆：当前研究任务上下文（检索词、已读论文、中间结果）
- 长期记忆：用户偏好 + 查询缓存（可选持久化到 JSON）
"""

from __future__ import annotations

from typing import Any

from .message import Message


class ShortTermMemory:
    """短期记忆 —— 滑动窗口消息队列。

    自动截断策略：
    - max_tokens 估算是字符数 / 2（保守，中文实际约 1.5 char/token）
    - 保留最近 N 轮完整对话
    - 始终保留 system message
    """

    def __init__(self, max_tokens: int = 8000):
        self.max_tokens = max_tokens
        self._messages: list[Message] = []

    def add(self, msg: Message) -> None:
        self._messages.append(msg)
        self._trim()

    def get_all(self) -> list[Message]:
        return list(self._messages)

    def get_recent(self, n: int = 10) -> list[Message]:
        """获取最近 n 条消息。"""
        return self._messages[-n:]

    def clear(self, keep_system: bool = True) -> None:
        if keep_system:
            self._messages = [m for m in self._messages if m.role == "system"]
        else:
            self._messages = []

    def _trim(self) -> None:
        """按估算 token 数截断。"""
        while self._estimated_tokens() > self.max_tokens:
            # 跳过 system message，从第二条开始删
            if len(self._messages) > 1 and self._messages[0].role == "system":
                self._messages.pop(1)
            elif self._messages:
                self._messages.pop(0)
            else:
                break

    def _estimated_tokens(self) -> int:
        return sum(len(m.content) for m in self._messages) // 2

    def __len__(self) -> int:
        return len(self._messages)


class WorkingMemory:
    """工作记忆 —— 当前研究任务上下文。

    存的是结构化状态，不是对话文本：
    - search_keywords: 本次任务已用的检索词
    - read_papers: 已阅读/引用的论文 DOI 列表
    - retrieved_snippets: 检索到的文本片段
    - intermediate_results: 多步推理的中间结果
    - task_state: 当前任务状态机
    """

    def __init__(self):
        self._store: dict[str, Any] = {}

    def set(self, key: str, value: Any) -> None:
        self._store[key] = value

    def get(self, key: str, default: Any = None) -> Any:
        return self._store.get(key, default)

    def append(self, key: str, value: Any) -> None:
        """追加到列表型字段。"""
        if key not in self._store:
            self._store[key] = []
        self._store[key].append(value)

    def snapshot(self) -> dict[str, Any]:
        """返回工作记忆摘要，用于注入 LLM 上下文。"""
        return {
            k: v
            for k, v in self._store.items()
            if k in ("search_keywords", "read_papers", "intermediate_results")
        }

    def clear(self) -> None:
        self._store.clear()

    def __repr__(self) -> str:
        keys = list(self._store.keys())
        return f"WorkingMemory({keys})"


class Memory:
    """统一记忆接口。

    用法：
        mem = Memory()
        mem.short.add(Message.user("你好"))
        mem.working.set("task_state", "searching")
    """

    def __init__(self, short_max_tokens: int = 8000):
        self.short = ShortTermMemory(max_tokens=short_max_tokens)
        self.working = WorkingMemory()

    def add_message(self, msg: Message) -> None:
        self.short.add(msg)

    def get_conversation(self) -> list[Message]:
        return self.short.get_all()

    def clear(self) -> None:
        self.short.clear()
        self.working.clear()
