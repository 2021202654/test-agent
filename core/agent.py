"""
Agent 顶层入口 —— 把 Role + LLM + Orchestrator 组装成可用的 Agent

这是用户唯一需要直接接触的类。

用法：
    agent = AeroThermalAgent(config)
    agent.equip(SearchAction(...))
    agent.equip(ComputeAction())

    reply = await agent.run("比较 SiO₂ 和 SiC 在 2000K 下的催化复合系数")
    print(reply.content)
"""

from __future__ import annotations

from .action import ActionRegistry
from .llm import LLMConfig, LLMInterface
from .memory import Memory, Message
from .orchestrator import ReActOrchestrator, PlanExecuteOrchestrator
from .role import Role


class Agent:
    """气固热导 AI Agent。

    组成：
    - role:     身份/目标/约束/工具
    - llm:      大模型接口
    - memory:   记忆系统
    - orchestrator: 运行模式（ReAct / Plan-Execute）
    """

    def __init__(
        self,
        llm_config: LLMConfig | None = None,
        name: str = "AeroThermalExpert",
        profile: str = "",
        goal: str = "",
        constraints: list[str] | None = None,
        mode: str = "react",  # "react" | "plan_execute"
        verbose: bool = False,
    ):
        self.llm = LLMInterface(llm_config or LLMConfig())
        self.role = Role(
            name=name,
            profile=profile,
            goal=goal,
            constraints=constraints,
        )
        self.memory = self.role.memory  # 快捷引用

        self.mode = mode
        self.verbose = verbose
        self._react = ReActOrchestrator(self.llm)
        self._react.verbose = verbose
        self._plan_execute = PlanExecuteOrchestrator(self.llm)
        self._plan_execute.verbose = verbose

    # ── 工具管理 ────────────────────────────────────

    def equip(self, action) -> "Agent":
        """装配一个工具。"""
        self.role.equip(action)
        return self

    def equip_many(self, actions: list) -> "Agent":
        self.role.equip_many(actions)
        return self

    @property
    def registry(self) -> ActionRegistry:
        return self.role.registry

    # ── 运行 ────────────────────────────────────────

    async def run(self, task: str) -> Message:
        """运行 Agent，处理一个任务。

        Args:
            task: 用户的问题或指令

        Returns:
            Message: Agent 的最终回答
        """
        # 准备上下文
        role_context = self.role.build_system_prompt()

        # 选择运行模式
        if self.mode == "plan_execute":
            return await self._plan_execute.run(
                task=task,
                role_context=role_context,
                memory=self.memory,
                registry=self.role.registry,
            )
        else:
            return await self._react.run(
                task=task,
                role_context=role_context,
                memory=self.memory,
                registry=self.role.registry,
            )

    def run_sync(self, task: str) -> Message:
        """同步封装，方便在非 async 环境调用。"""
        import asyncio

        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            # 已经在事件循环中，无法同步调用
            raise RuntimeError(
                "检测到运行中的事件循环，请使用 `await agent.run(task)` 而非 `agent.run_sync(task)`"
            )
        return asyncio.run(self.run(task))

    # ── 查询 ────────────────────────────────────────

    def describe(self) -> str:
        tools = self.role.registry.list_names()
        return (
            f"{self.role.describe()}\n"
            f"Mode: {self.mode}\n"
            f"LLM: {self.llm.config.model} @ {self.llm.config.base_url}\n"
            f"Tools ({len(tools)}): {', '.join(tools)}"
        )

    async def close(self):
        await self.llm.close()

    def __repr__(self) -> str:
        return f"Agent({self.role.name}, mode={self.mode}, tools={len(self.role.registry)})"
