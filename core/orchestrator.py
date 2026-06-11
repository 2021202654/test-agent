"""
编排引擎 —— Agent 的核心运行循环

两种模式（仿 MetaGPT REACT / PLAN_AND_ACT）：
1. ReAct: 推理 → 行动 → 观察 → 循环，适合开放式探索
2. Plan-Execute: 先制定计划，再逐步执行，适合结构化任务
"""

from __future__ import annotations

import json
from collections import OrderedDict
from typing import Any

from .action import ActionRegistry
from .llm import LLMInterface
from .memory import Memory, Message


# ── 有上限的工具调用缓存（防止内存耗尽）───────────────
_CALL_CACHE_MAX_SIZE = 100


class _BoundedCache:
    """带 LRU 淘汰的有界缓存。超出 max_size 后自动淘汰最旧条目。"""

    def __init__(self, maxsize: int = _CALL_CACHE_MAX_SIZE):
        self._data: OrderedDict[tuple, str] = OrderedDict()
        self._maxsize = maxsize

    def get(self, key: tuple) -> str | None:
        if key not in self._data:
            return None
        self._data.move_to_end(key)  # LRU: 访问过的移到末尾
        return self._data[key]

    def set(self, key: tuple, value: str) -> None:
        if key in self._data:
            self._data.move_to_end(key)
        elif len(self._data) >= self._maxsize:
            self._data.popitem(last=False)  # 淘汰最旧的
        self._data[key] = value


# ── ReAct 模式 ─────────────────────────────────────


class ReActOrchestrator:
    """ReAct（Reasoning + Acting）循环。

    流程：
        1. 将用户问题 + 可用工具 + 对话历史发给 LLM
        2. LLM 返回 text（最终回答）或 tool_call（需要使用工具）
        3. 如果是 tool_call → 执行工具 → 将结果加入历史 → 回到 step 1
        4. 如果是 text → 返回最终回答

    安全上限：最多执行 max_steps 步工具调用，防止无限循环。
    """

    def __init__(self, llm: LLMInterface, max_steps: int = 8):
        self.llm = llm
        self.max_steps = max_steps
        self.verbose = False  # 由 Agent 设置，开启后打印工具调用详情

    async def run(
        self,
        task: str,
        role_context: str,  # system prompt
        memory: Memory,
        registry: ActionRegistry,
    ) -> Message:
        """执行 ReAct 循环，返回最终回答。"""
        # 初始化消息列表
        messages: list[Message] = [
            Message.system(role_context),
            Message.user(task),
        ]
        tool_schemas = registry.to_openai_schemas() if registry else None

        steps = 0
        final_reply = ""
        _call_cache = _BoundedCache()  # 有界 LRU 缓存，上限 100 条

        while steps < self.max_steps:
            steps += 1

            # ── 调用 LLM ──
            if tool_schemas:
                response = await self.llm.chat_with_tools(messages, tool_schemas)
            else:
                response = await self.llm.chat(messages)

            # ── 情况 1：LLM 决定回复文本（任务完成）──
            if response.content and not response.tool_calls:
                final_reply = response.content
                break

            # ── 情况 2：LLM 请求调用工具 ──
            if response.tool_calls:
                # 把 LLM 的响应（含 tool_calls）加入历史
                messages.append(response)

                for tc in response.tool_calls:
                    func_name = tc["function"]["name"]
                    try:
                        func_args = json.loads(tc["function"]["arguments"])
                    except json.JSONDecodeError as e:
                        tool_result = (
                            f"[arguments parse error] Tool '{func_name}' received malformed JSON arguments: {e}. "
                            f"Raw arguments: {tc['function']['arguments'][:200]}. "
                            f"Please retry with properly formatted JSON arguments."
                        )
                        messages.append(
                            Message.tool_result(
                                content=tool_result,
                                tool_call_id=tc["id"],
                                tool_name=func_name,
                            )
                        )
                        continue

                    if self.verbose:
                        print(f"\n  [tool] {func_name}({json.dumps(func_args, ensure_ascii=False)})")

                    # ── 去重：相同工具+相同参数不重复执行（LRU 有界缓存）──
                    args_key = tuple(sorted(
                        (k, str(v)) for k, v in func_args.items()
                    ))
                    cache_key = (func_name, args_key)
                    cached = _call_cache.get(cache_key)
                    if cached is not None:
                        tool_result = (
                            f"[duplicate call skipped] Already called {func_name} with "
                            f"these args. Previous result summary:\n{cached}"
                        )
                        if self.verbose:
                            print(f"  [skip] duplicate call, using cached result")
                    else:
                        # 执行工具
                        action = registry.get(func_name)
                        if action is None:
                            tool_result = f"[error] Unknown tool: {func_name}"
                        else:
                            try:
                                tool_result = await action.run(**func_args)
                            except Exception as e:
                                tool_result = f"[tool error] {func_name}: {e}"
                        # 缓存（上限 100 条，LRU 淘汰）
                        _call_cache.set(cache_key, str(tool_result)[:300])

                    if self.verbose:
                        preview = str(tool_result)[:500]
                        print(f"  [result] ({len(str(tool_result))} chars): {preview}...")

                    # 工具结果加入历史
                    messages.append(
                        Message.tool_result(
                            content=str(tool_result),
                            tool_call_id=tc["id"],
                            tool_name=func_name,
                        )
                    )

                    # 记录到工作记忆
                    memory.working.append("tool_calls", {
                        "tool": func_name,
                        "args": func_args,
                        "result_preview": str(tool_result)[:300],
                    })

                continue

            # ── 情况 3：既无内容也无工具调用（异常）──
            final_reply = response.content or "（Agent 未生成有效响应）"
            break

        else:
            # 达到 max_steps —— 请求 LLM 做最终合成
            if messages:
                try:
                    force_prompt = Message.user(
                        "你已达到最大工具调用步数。请基于以上所有已获得的信息，"
                        "立即给出最终回答。不要请求更多工具，直接输出结论。"
                    )
                    messages.append(force_prompt)
                    final_resp = await self.llm.chat(messages)
                    final_reply = final_resp.content
                except Exception:
                    final_reply = f"（Agent 在 {self.max_steps} 步内未完成任务，已停止。）"
            else:
                final_reply = f"（Agent 在 {self.max_steps} 步内未完成任务，已停止。）"

        # 生成最终消息
        result = Message.agent(
            content=final_reply,
            steps=steps,
            tool_call_history=memory.working.get("tool_calls", []),
        )
        memory.add_message(result)
        return result


# ── Plan-Execute 模式 ──────────────────────────────


class PlanExecuteOrchestrator:
    """Plan-Execute 模式。

    流程：
        1. Plan:  LLM 将用户任务分解为步骤列表
        2. Execute: 依次执行每个步骤（每步内部是一个 mini ReAct 循环）
        3. Synthesize: 汇总所有步骤结果，生成最终回答
    """

    def __init__(self, llm: LLMInterface, max_plan_steps: int = 6, max_react_steps: int = 4):
        self.llm = llm
        self.max_plan_steps = max_plan_steps
        self.max_react_steps = max_react_steps
        self.verbose = False

    async def run(
        self,
        task: str,
        role_context: str,
        memory: Memory,
        registry: ActionRegistry,
    ) -> Message:
        # ── Phase 1: 制定计划 ──
        plan = await self._make_plan(task, role_context, memory)
        memory.working.set("plan", plan)

        # ── Phase 2: 逐步执行 ──
        step_results: list[dict[str, Any]] = []
        for i, step in enumerate(plan):
            step_result = await self._execute_step(
                step=step,
                step_index=i + 1,
                total_steps=len(plan),
                original_task=task,
                role_context=role_context,
                memory=memory,
                registry=registry,
            )
            step_results.append({"step": step, "result": step_result})
            memory.working.set(f"step_{i+1}_result", step_result)

        # ── Phase 3: 合成最终回答 ──
        synthesis = await self._synthesize(task, step_results, role_context)
        result = Message.agent(
            content=synthesis,
            plan=plan,
            step_results=step_results,
        )
        memory.add_message(result)
        return result

    async def _make_plan(
        self, task: str, role_context: str, memory: Memory
    ) -> list[str]:
        """让 LLM 生成执行计划。"""
        prompt = f"""你是一个研究助手。请将以下任务分解为 {self.max_plan_steps} 步以内的执行计划。

任务：{task}

返回格式（每行一个步骤，不要编号）：
步骤描述1
步骤描述2
...

只返回步骤列表，不要其他内容。"""

        plan_msg = await self.llm.chat([
            Message.system(role_context),
            Message.user(prompt),
        ])

        # 解析步骤列表
        lines = [l.strip() for l in plan_msg.content.split("\n") if l.strip()]
        lines = [l.lstrip("0123456789.-) ").strip() for l in lines]
        return lines[: self.max_plan_steps]

    async def _execute_step(
        self,
        step: str,
        step_index: int,
        total_steps: int,
        original_task: str,
        role_context: str,
        memory: Memory,
        registry: ActionRegistry,
    ) -> str:
        """执行单个步骤（mini ReAct）。"""
        step_task = (
            f"原始任务：{original_task}\n"
            f"当前步骤（{step_index}/{total_steps}）：{step}\n"
            f"请完成此步骤。只有在此步骤确实需要时，才调用工具。"
        )

        reactor = ReActOrchestrator(self.llm, max_steps=self.max_react_steps)
        result = await reactor.run(
            task=step_task,
            role_context=role_context,
            memory=memory,
            registry=registry,
        )
        return result.content

    async def _synthesize(
        self,
        task: str,
        step_results: list[dict[str, Any]],
        role_context: str,
    ) -> str:
        """汇总所有步骤，生成最终回答。"""
        steps_text = "\n\n".join(
            f"步骤 {i+1}) {r['step']}\n结果：{r['result']}"
            for i, r in enumerate(step_results)
        )

        prompt = f"""原始问题：{task}

以下是各步骤的执行结果：

{steps_text}

请基于以上信息，给出一个完整的、结构化的最终回答。遵循原始角色约束。"""

        result = await self.llm.chat([
            Message.system(role_context),
            Message.user(prompt),
        ])
        return result.content
