"""
Role 类 —— 仿 MetaGPT Role，Agent 的身份与行为核心

每个 Role = 一个 Agent 身份，包含：
- 身份定义: name, profile, goal, constraints
- 能力: actions（可调用的工具）
- 记忆: memory（短期 + 工作 + 长期）
- 生命周期: _observe() → _think() → _act()

与 MetaGPT 的差异：
- 去掉了 publish_message / Environment 多 Agent 通信
- 去掉了 _watch 订阅机制
- react() 改为单次任务驱动的 run() 方法
"""

from __future__ import annotations

from .action import ActionRegistry
from .memory import Memory, Message


class Role:
    """Agent 角色基类。

    最简用法：
        role = Role(
            name="AeroThermalExpert",
            profile="高超声速气固界面耦合研究专家",
            goal="辅助研究者进行文献检索、多步推理、证据合成",
        )
        role.equip(SearchAction())
        role.equip(ComputeAction())
    """

    def __init__(
        self,
        name: str,
        profile: str = "",
        goal: str = "",
        constraints: list[str] | None = None,
    ):
        self.name = name
        self.profile = profile
        self.goal = goal
        self.constraints = constraints or []

        # 能力
        self.registry = ActionRegistry()

        # 记忆
        self.memory = Memory()

        # 状态
        self._initialized = False

    # ── 工具装配 ────────────────────────────────────

    def equip(self, action) -> "Role":
        """装备一个工具到 Agent。"""
        from .action import Action

        self.registry.register(action)
        return self

    def equip_many(self, actions: list) -> "Role":
        self.registry.register_many(actions)
        return self

    # ── System Prompt ───────────────────────────────

    def build_system_prompt(self) -> str:
        """根据身份信息构建 system prompt。"""
        lines = []
        if self.profile:
            lines.append(f"你是 {self.name}，{self.profile}。")
        if self.goal:
            lines.append(f"你的目标是：{self.goal}")
        if self.constraints:
            lines.append("你必须遵守以下约束：")
            for c in self.constraints:
                lines.append(f"- {c}")

        lines.append("\n你有可用的工具来完成你的任务。")
        lines.append("当需要检索文献时，使用文献检索工具。")
        lines.append("当需要数值计算时，使用气动热计算工具。")
        lines.append("仅在信息充足时才给出最终回答，不要编造数据。")

        return "\n".join(lines)

    def system_message(self) -> Message:
        return Message.system(self.build_system_prompt())

    # ── 描述信息 ─────────────────────────────────────

    def describe(self) -> str:
        return (
            f"Role: {self.name}\n"
            f"Profile: {self.profile}\n"
            f"Goal: {self.goal}\n"
            f"Actions: {self.registry.list_names()}\n"
            f"Constraints: {self.constraints}"
        )
