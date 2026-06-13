"""
Orchestration Engine — Core Agent Execution Loop

Two modes (MetaGPT REACT / PLAN_AND_ACT inspired):
1. ReAct: Reason → Act → Observe → Loop, for open-ended exploration
2. Plan-Execute: Plan first, then execute step-by-step, for structured tasks
"""

from __future__ import annotations

import json
from collections import OrderedDict
from typing import Any

from .action import ActionRegistry
from .llm import LLMInterface
from .memory import Memory, Message


# ── Bounded tool call cache (prevents OOM) ──────────
_CALL_CACHE_MAX_SIZE = 100


class _BoundedCache:
    """LRU-eviction bounded cache. Evicts oldest entry when max_size is exceeded."""

    def __init__(self, maxsize: int = _CALL_CACHE_MAX_SIZE):
        self._data: OrderedDict[tuple, str] = OrderedDict()
        self._maxsize = maxsize

    def get(self, key: tuple) -> str | None:
        if key not in self._data:
            return None
        self._data.move_to_end(key)  # LRU: move accessed item to end
        return self._data[key]

    def set(self, key: tuple, value: str) -> None:
        if key in self._data:
            self._data.move_to_end(key)
        elif len(self._data) >= self._maxsize:
            self._data.popitem(last=False)  # Evict oldest
        self._data[key] = value


# ── ReAct Mode ─────────────────────────────────────


class ReActOrchestrator:
    """ReAct (Reasoning + Acting) loop.

    Flow:
        1. Send user query + available tools + conversation history to LLM
        2. LLM returns text (final answer) or tool_call (needs tool usage)
        3. If tool_call → execute tool → add result to history → back to step 1
        4. If text → self-critique loop (N rounds) → return final answer

    Safety: max_steps caps tool calls to prevent infinite loops.
    Self-critique rounds improve answer quality through iterative refinement.
    """

    def __init__(
        self,
        llm: LLMInterface,
        max_steps: int = 8,
        critique_rounds: int = 2,
        self_consistency: int = 1,  # Number of consistency samples (1 = disabled)
    ):
        self.llm = llm
        self.max_steps = max_steps
        self.critique_rounds = critique_rounds  # Number of self-critique rounds after main loop
        self.self_consistency = self_consistency  # Number of consistency samples (1 = disabled, 3+ enables voting)
        self.verbose = False  # Set by Agent to print tool call details

    async def run(
        self,
        task: str,
        role_context: str,  # system prompt
        memory: Memory,
        registry: ActionRegistry,
    ) -> Message:
        """Execute ReAct loop, return final answer."""
        # Initialize message list
        messages: list[Message] = [
            Message.system(role_context),
            Message.user(task),
        ]
        tool_schemas = registry.to_openai_schemas() if registry else None

        steps = 0
        final_reply = ""
        _call_cache = _BoundedCache()  # Bounded LRU cache, max 100 entries
        # Responses API: track response_id for multi-turn continuity
        _response_id: str | None = None

        while steps < self.max_steps:
            steps += 1

            # ── Call LLM ──
            if tool_schemas:
                response = await self.llm.chat_with_tools(messages, tool_schemas, _response_id=_response_id)
            else:
                response = await self.llm.chat(messages)

            # Update response_id for Responses API multi-turn continuity
            _response_id = response.metadata.get("response_id") or _response_id

            # ── Case 1: LLM returns text with NO tool calls (task done) ──
            if response.content and not response.tool_calls:
                final_reply = response.content
                break

            # ── Case 1b: LLM returns text WITH tool calls — don't break, execute tools then loop ──
            # The text (if any) is partial; wait for all tools to finish before treating any text as final
            if response.content and response.tool_calls:
                # content is a partial plan/thinking — append to messages but do NOT break
                if self.verbose:
                    preview = response.content[:200]
                    print(f"\n  [partial] LLM thinking (will be superseded after tool execution): {preview}...")

            # ── Case 2: LLM requests tool call ──
            if response.tool_calls:
                # Append LLM response (with tool_calls) to history
                messages.append(response)

                for tc in response.tool_calls:
                    func_name = tc["function"]["name"]
                    raw_args = tc["function"]["arguments"]
                    try:
                        # arguments may be a dict (internal format) or a JSON string (API format)
                        func_args = raw_args if isinstance(raw_args, dict) else json.loads(raw_args)
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

                    # ── Deduplication: same tool + same args → skip re-execution (LRU bounded cache) ──
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
                        # Execute tool
                        action = registry.get(func_name)
                        if action is None:
                            tool_result = f"[error] Unknown tool: {func_name}"
                        else:
                            try:
                                tool_result = await action.run(**func_args)
                            except Exception as e:
                                tool_result = f"[tool error] {func_name}: {e}"
                        # Cache (max 100 entries, LRU eviction)
                        _call_cache.set(cache_key, str(tool_result)[:300])

                    if self.verbose:
                        preview = str(tool_result)[:500]
                        print(f"  [result] ({len(str(tool_result))} chars): {preview}...")

                    # Append tool result to history
                    messages.append(
                        Message.tool_result(
                            content=str(tool_result),
                            tool_call_id=tc["id"],
                            tool_name=func_name,
                        )
                    )

                    # Record to working memory
                    memory.working.append("tool_calls", {
                        "tool": func_name,
                        "args": func_args,
                        "result_preview": str(tool_result)[:300],
                    })

                continue

            # ── Case 3: Neither content nor tool_calls (anomaly) ──
            final_reply = response.content or "（Agent did not generate a valid response）"
            break

        else:
            # Reached max_steps → ask LLM for final synthesis
            if messages:
                try:
                    force_prompt = Message.user(
                        "You have reached the maximum number of tool-call steps. Based on all information obtained above, "
                        "immediately give your final answer. Do not request more tools; output your conclusion directly."
                    )
                    messages.append(force_prompt)
                    final_resp = await self.llm.chat(messages)
                    final_reply = final_resp.content
                except Exception:
                    final_reply = f"（Agent did not complete the task within {self.max_steps} steps, stopped.）"
            else:
                final_reply = f"（Agent did not complete the task within {self.max_steps} steps, stopped.）"

        # ── Self-critique loop: refine answer through iterative review ──
        if final_reply and self.critique_rounds > 0:
            final_reply = await self._self_critique(
                task=task,
                draft=final_reply,
                role_context=role_context,
            )

        # ── Self-consistency: sample N answers and pick the most consistent ──
        if final_reply and self.self_consistency >= 3:
            final_reply = await self._self_consistency(
                task=task,
                draft=final_reply,
                role_context=role_context,
                n_samples=self.self_consistency,
            )

        # Generate final message
        result = Message.agent(
            content=final_reply,
            steps=steps,
            tool_call_history=memory.working.get("tool_calls", []),
        )
        memory.add_message(result)
        return result

    # ── Self-Critique Loop ─────────────────────────────

    async def _self_critique(
        self,
        task: str,
        draft: str,
        role_context: str,
    ) -> str:
        """Iteratively self-critique and revise the draft answer.

        Each round:
          1. LLM reviews the draft for weaknesses (missing evidence, over-claiming, etc.)
          2. LLM produces a revised answer addressing those weaknesses
          3. If no significant weaknesses found, keep current draft

        Args:
            task: Original user question
            draft: Initial answer from the ReAct loop
            role_context: System prompt (role constraints)

        Returns:
            Refined final answer after N critique rounds
        """
        current_draft = draft
        critique_system = (
            "You are a strict academic peer reviewer. Your job is to critically evaluate "
            "research answers and identify specific weaknesses. "
            "After each critique, you must produce a revised answer.\n"
            "You must respond in the same language as the draft being reviewed.\n\n"
            "For each round, output in this exact format:\n"
            "## Critique\n"
            "<specific weaknesses identified, or 'No significant issues found'>\n\n"
            "## Revised Answer\n"
            "<improved answer addressing the critique>"
        )

        for round_idx in range(1, self.critique_rounds + 1):
            if self.verbose:
                print(f"\n  [critique] Round {round_idx}/{self.critique_rounds}")

            critique_prompt = (
                f"Original Question:\n{task}\n\n"
                f"Current Draft Answer:\n{current_draft}\n\n"
                f"Please review the draft above and provide:\n"
                f"1. A critical critique identifying specific weaknesses\n"
                f"2. A revised answer that addresses those weaknesses"
            )

            try:
                resp = await self.llm.chat([
                    Message.system(critique_system),
                    Message.system(role_context),
                    Message.user(critique_prompt),
                ])
            except Exception as e:
                if self.verbose:
                    print(f"  [critique] Round {round_idx} failed: {e}, keeping current draft")
                break

            raw = resp.content or ""

            # Parse: split on "## Revised Answer" (case-insensitive, single line)
            import re
            marker = re.search(r"##\s*Revised\s*Answer", raw, re.IGNORECASE)
            if marker:
                revised = raw[marker.end():].strip()
                critique_text = raw[:marker.start()].strip()
            else:
                # Fallback: if format is wrong, treat entire response as revised
                revised = raw
                critique_text = ""

            if self.verbose:
                preview_critique = critique_text[:300] if critique_text else "(no critique extracted)"
                print(f"  [critique] {preview_critique}...")
                print(f"  [critique] Revised answer: {revised[:200]}...")

            # Only update draft if we got meaningful revision content
            if revised and len(revised) > max(len(current_draft) * 0.5, 50):
                current_draft = revised
            else:
                if self.verbose:
                    print(f"  [critique] No substantial improvement in round {round_idx}, keeping current draft")
                break

        return current_draft

    # ── Self-Consistency Voting ──────────────────────────────

    async def _self_consistency(
        self,
        task: str,
        draft: str,
        role_context: str,
        n_samples: int = 3,
    ) -> str:
        """Sample N variants of the final answer, then pick the most consistent one.

        Wang et al. 2022 "Self-Consistency Improves Chain of Thought Reasoning in Language Models"
        — particularly helpful for smaller / open-source models (e.g. Llama-3.1-8B)
        where single-shot reasoning is unstable.

        Algorithm (lightweight, single extra LLM call):
          1. Sample (n_samples - 1) additional "core takeaway" statements from the LLM,
             each asked to extract the 1-2 sentence conclusion from `draft`.
          2. Ask the LLM to pick which variant (draft or one of the samples) is most
             semantically consistent with the majority view.
          3. Return the chosen variant.

        Cost: (n_samples - 1) extra short LLM calls + 1 voting call. Default n_samples=3
        gives ~4 extra calls. For 8B models this is a worthwhile trade.

        Args:
            task: Original user question.
            draft: Initial answer (after self-critique).
            role_context: System prompt.
            n_samples: Total number of variants to compare (>=3 to be effective).

        Returns:
            The most consistent answer variant.
        """
        try:
            # Step 1: Generate (n_samples - 1) alternative "core takeaway" extractions
            variants = [draft]
            for i in range(n_samples - 1):
                extract_prompt = (
                    f"Read the following answer to the question below, then write the "
                    f"core takeaway in 1-2 sentences (variant #{i + 1}). Keep the same "
                    f"factual content but vary the wording slightly to reflect an "
                    f"independent reasoning pass.\n\n"
                    f"Question: {task}\n\n"
                    f"Answer:\n{draft}\n\n"
                    f"Core takeaway (variant #{i + 1}):"
                )
                try:
                    resp = await self.llm.chat(
                        [Message.system(role_context), Message.user(extract_prompt)]
                    )
                    if resp.content:
                        variants.append(resp.content.strip())
                except Exception as e:
                    # If a sample fails, skip it but don't break the whole flow
                    if self.verbose:
                        print(f"  [consistency] sample #{i + 1} failed: {e}")

            if len(variants) < 2:
                # Not enough samples to vote; return original draft
                return draft

            # Step 2: Ask LLM to vote — which variant is most consistent with the majority?
            vote_prompt = (
                f"You are given {len(variants)} candidate answers to the same question. "
                f"Your job: identify which candidate is most factually consistent with "
                f"the others (i.e. would survive majority agreement).\n\n"
                f"Question: {task}\n\n"
                + "\n\n---\n\n".join(
                    f"Candidate #{i + 1}:\n{v}" for i, v in enumerate(variants)
                )
                + f"\n\n---\n\nRespond with ONLY the candidate number (1-{len(variants)}) "
                f"that best represents the majority view. No explanation."
            )
            try:
                vote_resp = await self.llm.chat(
                    [Message.system(role_context), Message.user(vote_prompt)]
                )
                choice = vote_resp.content.strip()
                # Parse the number; default to 1 (the original draft) if unclear
                import re
                m = re.search(r"\b([1-9]\d?)\b", choice)
                if m:
                    idx = int(m.group(1)) - 1
                    if 0 <= idx < len(variants):
                        chosen = variants[idx]
                        if self.verbose:
                            print(f"  [consistency] chose variant #{idx + 1} of {len(variants)}")
                        return chosen
            except Exception as e:
                if self.verbose:
                    print(f"  [consistency] voting failed: {e}")

            return draft
        except Exception as e:
            # Self-consistency must NEVER break the main flow
            if self.verbose:
                print(f"  [consistency] error, falling back to draft: {e}")
            return draft


# ── Plan-Execute Mode ──────────────────────────────


class PlanExecuteOrchestrator:
    """Plan-Execute mode.

    Flow:
        1. Plan: LLM decomposes user task into a step list
        2. Execute: Execute each step in order (each step is an internal mini ReAct loop)
        3. Synthesize: Aggregate all step results, generate final answer
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
        # ── Phase 1: Plan ──
        plan = await self._make_plan(task, role_context, memory)
        memory.working.set("plan", plan)

        # ── Phase 2: Execute step-by-step ──
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

        # ── Phase 3: Synthesize final answer ──
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
        """Generate execution plan via LLM."""
        prompt = f"""You are a research assistant. Please decompose the following task into at most {self.max_plan_steps} steps.

Task: {task}

Return format (one step per line, no numbering):
Step description 1
Step description 2
...

Return only the step list, nothing else."""
        # NOTE: This prompt is designed for Chinese-language LLM models (百炼/硅基流动).
        # The LLM should respond in Chinese to match the rest of the agent's dialogue.

        plan_msg = await self.llm.chat([
            Message.system(role_context),
            Message.user(prompt),
        ])

        # Parse step list
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
        """Execute a single step (mini ReAct)."""
        step_task = (
            f"Original task: {original_task}\n"
            f"Current step ({step_index}/{total_steps}): {step}\n"
            f"Please complete this step. Only call tools when this step genuinely requires them."
        )
        # NOTE: Chinese above is for the LLM being called; keep as-is.

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
        """Aggregate all steps, generate final answer."""
        steps_text = "\n\n".join(
            f"Step {i+1}) {r['step']}\nResult: {r['result']}"
            for i, r in enumerate(step_results)
        )

        prompt = f"""Original question: {task}

Below are the execution results of each step:

{steps_text}

Based on the above information, give a complete, structured final answer. Follow the original role constraints."""
        # NOTE: Chinese text in prompt is for the LLM being called; keep as-is.

        result = await self.llm.chat([
            Message.system(role_context),
            Message.user(prompt),
        ])
        return result.content
