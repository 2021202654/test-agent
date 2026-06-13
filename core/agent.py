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

from dataclasses import dataclass, field
from typing import Any

from .action import ActionRegistry
from .llm import LLMConfig, LLMInterface
from .memory import Memory, Message
from .orchestrator import ReActOrchestrator, PlanExecuteOrchestrator
from .role import Role


@dataclass
class FallbackSignal:
    """Returned by Agent.run() when a fallback event requires user confirmation."""
    triggered: bool = False
    original_preset: str = ""
    suggested_preset: str = ""
    reason: str = ""
    chain: list[str] = field(default_factory=list)  # full fallback chain
    last_error: str = ""


@dataclass
class AgentResult:
    """Wrapper around Message with additional Agent-level metadata."""
    message: Message
    fallback_signal: FallbackSignal = field(default_factory=FallbackSignal)
    complexity: str = ""           # "simple" / "moderate" / "complex"
    model_used: str = ""           # which preset was ultimately used
    fallback_history: list = field(default_factory=list)


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
        critique_rounds: int = 2,  # Self-critique iterations after ReAct loop
        self_consistency: int = 1,  # 1 = disabled; 3+ enables voting (great for 8B models)
        auto_route: bool = False,   # enable LLM-based complexity routing
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
        self.auto_route = auto_route
        self._react = ReActOrchestrator(self.llm, max_steps=max_react_steps, critique_rounds=critique_rounds, self_consistency=self_consistency)
        self._react.verbose = verbose
        self._plan_execute = PlanExecuteOrchestrator(self.llm, max_react_steps=max_react_steps, max_plan_steps=max_plan_steps)
        self._plan_execute.verbose = verbose

        # Policy routing
        self._complexity: str = ""
        self._fallback_signal = FallbackSignal()
        self._fallback_history: list = []

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

    async def run(self, task: str) -> AgentResult:
        """Run Agent, handling a task.

        Returns:
            AgentResult: wraps Message with fallback_signal, complexity, and model_used.
                         If fallback_signal.triggered is True, caller must confirm
                         via confirm_fallback() before retrying.
        """
        role_context = self.role.build_system_prompt()
        tool_schemas = self.role.registry.to_openai_schemas()

        # ── Complexity estimation + model routing ──
        model_used = self.llm.config.preset_name or "unknown"
        if self.auto_route:
            try:
                from .policy_router import PolicyRouter, FallbackManager
                router = PolicyRouter(self.llm)
                complexity = await router.estimate_complexity(task)
                self._complexity = complexity.value
                routing = router.route(complexity)
                model_used = routing.assigned_preset
                self._fallback_history = []
                if self.verbose:
                    print(f"\n  [router] complexity={complexity.value}, assigned={routing.assigned_preset}")
            except Exception as e:
                if self.verbose:
                    print(f"\n  [router] routing failed: {e}, using current config")
        else:
            self._complexity = ""

        # ── Orchestrator execution with fallback ──
        self._fallback_signal = FallbackSignal()
        result = None
        last_error: Exception | None = None

        try:
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
        except Exception as e:
            last_error = e

        # ── Fallback on error ──
        if last_error is not None and self.auto_route:
            from .policy_router import FallbackManager, _detect_fallback_reason
            router = PolicyRouter(self.llm)
            reason = _detect_fallback_reason(last_error)
            chain = router.get_fallback_chain(model_used)

            # Find next fallback preset
            try:
                next_preset_idx = chain.index(model_used) + 1
            except ValueError:
                next_preset_idx = 0

            if next_preset_idx < len(chain):
                next_preset = chain[next_preset_idx]
                self._fallback_signal = FallbackSignal(
                    triggered=True,
                    original_preset=model_used,
                    suggested_preset=next_preset,
                    reason=reason,
                    chain=chain,
                    last_error=str(last_error),
                )
                if self.verbose:
                    print(f"\n  [fallback] {reason} → suggesting {next_preset}")

        # ── Auto-save report ──
        if result and result.content and len(result.content) > 200:
            self._auto_save_report(task, result)

        return AgentResult(
            message=result or Message.agent(content=f"Error: {last_error}"),
            fallback_signal=self._fallback_signal,
            complexity=self._complexity,
            model_used=model_used,
            fallback_history=self._fallback_history,
        )

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

    def run_sync(self, task: str) -> AgentResult:
        """Synchronous wrapper for non-async environments. Returns AgentResult."""
        import asyncio
        return asyncio.run(self.run(task))

    async def confirm_fallback(self, preset: str) -> AgentResult:
        """Apply a fallback preset and retry the current task.

        Call this after run() returns an AgentResult where
        fallback_signal.triggered is True, after user confirmation.

        Args:
            preset: The fallback preset to switch to (e.g. "siliconflow")
        """
        if not self._fallback_signal.triggered:
            return AgentResult(
                message=Message.agent(content="No fallback pending"),
                fallback_signal=self._fallback_signal,
            )

        # Rebuild LLM config for the fallback preset
        from config import AgentConfig
        fallback_cfg = AgentConfig(llm=preset)
        self.llm.config = fallback_cfg.llm

        if self.verbose:
            print(f"\n  [fallback] Switched to {preset}, retrying...")

        # Retry — clear error state, reuse existing memory
        self._fallback_signal = FallbackSignal()

        role_context = self.role.build_system_prompt()
        result = None
        last_error: Exception | None = None

        try:
            if self.mode == "plan_execute":
                result = await self._plan_execute.run(
                    task="",  # reuse memory, just continue
                    role_context=role_context,
                    memory=self.memory,
                    registry=self.role.registry,
                )
            else:
                result = await self._react.run(
                    task="",  # reuse memory context, just continue
                    role_context=role_context,
                    memory=self.memory,
                    registry=self.role.registry,
                )
        except Exception as e:
            last_error = e

        return AgentResult(
            message=result or Message.agent(content=f"Error after fallback: {last_error}"),
            fallback_signal=self._fallback_signal,
            complexity=self._complexity,
            model_used=preset,
            fallback_history=self._fallback_history,
        )

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
