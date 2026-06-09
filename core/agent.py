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
        max_react_steps: int = 12,
        max_plan_steps: int = 6,
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
        self._react = ReActOrchestrator(self.llm, max_steps=max_react_steps)
        self._react.verbose = verbose
        self._plan_execute = PlanExecuteOrchestrator(self.llm, max_react_steps=max_react_steps, max_plan_steps=max_plan_steps)
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
            result = await self._plan_execute.run(
                task=task,
                role_context=role_context,
                memory=self.memory,
                registry=self.role.registry,
            )
        else:
            result = await self._react.run(
                task=task,
                role_context=role_context,
                memory=self.memory,
                registry=self.role.registry,
            )

        # ── 自动存档兜底 ──
        # 如果 Agent 的最终回复较长（有实质内容），自动保存为报告
        if result.content and len(result.content) > 200:
            self._auto_save_report(task, result)

        return result

    def _auto_save_report(self, task: str, result: Message):
        """将 Agent 最终回复自动保存为 Markdown 报告（兜底机制）。"""
        from datetime import datetime
        from pathlib import Path

        reports_dir = Path(__file__).parent.parent / "reports"
        reports_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        # 用任务前40个字符做短标题
        safe_title = task[:40].replace("?", "").replace(":", "：").replace("/", "_").replace("\\", "_")
        filename = f"{timestamp}_{safe_title}.md"
        filepath = reports_dir / filename

        content = f"# Auto-saved Report\n\n"
        content += f"**生成时间**：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        content += f"**原始任务**：{task}\n"
        content += f"**模式**：{self.mode} | **步数**：{result.metadata.get('steps', '?')}\n\n"
        content += "---\n\n"
        content += result.content
        content += "\n\n---\n*本报告由 Agent 自动存档生成。*\n"

        try:
            filepath.write_text(content, encoding="utf-8")
        except Exception:
            pass  # 静默失败，存档不是关键路径

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
