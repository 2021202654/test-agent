#!/usr/bin/env python3
"""
气固热导 AI Agent —— 命令行入口

用法：
    # 交互模式
    python run_agent.py

    # 单次问答
    python run_agent.py --task "比较 SiO₂ 和 SiC 在 2000K 下的催化复合系数"

    # 指定 LLM
    python run_agent.py --llm vllm_local
    python run_agent.py --llm bailian
    python run_agent.py --llm ollama

    # Plan-Execute 模式
    python run_agent.py --mode plan_execute --task "评估现有气固界面催化模型的跨尺度适用性"

依赖：
    pip install pydantic httpx numpy
    # FAISS 检索需要：pip install faiss-cpu
    # 向量检索 embedding 需要配置 embedding 模型
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

# 确保 05_AI_Agent/ 和项目根在 path 中
AGENT_DIR = Path(__file__).parent
PROJECT = AGENT_DIR.parent
sys.path.insert(0, str(AGENT_DIR))
sys.path.insert(0, str(PROJECT))

from config import AgentConfig
from tools.search import LiteratureSearchTool
from tools.web_search import WebSearchTool
from tools.compute import AeroThermalComputeTool
from tools.code_exec import CodeExecutionTool
from tools.citation import CitationResolverTool
from tools.pdf_parser import PDFAnalysisTool
from tools.report import ReportTool, ExportFindingTool
from tools.pandoc_export import PandocExportTool
from tools.hypothesis import HypothesisGenerator


def _equip_tools(agent, config: AgentConfig):
    """统一装备所有工具（含需要 LLM 注入的工具）。"""
    search = LiteratureSearchTool()
    web = WebSearchTool()

    agent.equip(search)
    agent.equip(web)
    agent.equip(AeroThermalComputeTool())
    agent.equip(CodeExecutionTool())
    agent.equip(CitationResolverTool())
    agent.equip(PDFAnalysisTool())
    agent.equip(ReportTool())
    agent.equip(ExportFindingTool())
    agent.equip(PandocExportTool())
    # AI Scientist 核心：假设生成器（需要 LLM + 检索工具注入）
    agent.equip(HypothesisGenerator(
        llm=agent.llm,
        search_tool=search,
        web_tool=web,
    ))


async def run_once(config: AgentConfig, task: str):
    """单次问答模式。"""
    agent = config.build_agent()
    _equip_tools(agent, config)

    print(f"\n{'='*60}")
    print(f"Agent: {agent.role.name}")
    print(f"LLM:  {config.llm.model} @ {config.llm.base_url}")
    print(f"Mode: {config.mode}")
    print(f"Tools: {agent.registry.list_names()}")
    print(f"{'='*60}\n")
    print(f"[*] Task: {task}\n")
    print(f"{'─'*60}")
    print("[...] Agent thinking...\n")

    try:
        reply = await agent.run(task)
        print(reply.content)
        print(f"\n{'─'*60}")
        print(f"[i] Metadata: {reply.metadata}")
    except Exception as e:
        print(f"\n[!] Agent error：{e}")
    finally:
        await agent.close()


async def interactive(config: AgentConfig):
    """交互模式 —— 持续对话。"""
    agent = config.build_agent()
    _equip_tools(agent, config)

    print(f"\n{'='*60}")
    print(f" 气固热导 AI Agent — {agent.role.name}")
    print(f" LLM: {config.llm.model} @ {config.llm.base_url}")
    print(f" 模式: {config.mode} | 工具: {', '.join(agent.registry.list_names())}")
    print(f"{'='*60}")
    print(" 输入 'quit' 退出 | 'clear' 清空记忆 | 'info' 查看状态")
    print(' 多行输入: 输入 """ 开始, 再输入 """ 结束\n')

    while True:
        try:
            first_line = input("You: ")
        except (EOFError, KeyboardInterrupt):
            print("\n[bye] Agent exited")
            break

        if not first_line.strip():
            continue

        # ── 多行粘贴模式 ──────────────────────────
        if first_line.strip() == '"""':
            lines = []
            print("> （多行输入模式，输入 \"\"\" 结束）")
            while True:
                try:
                    line = input()
                except (EOFError, KeyboardInterrupt):
                    break
                if line.strip() == '"""':
                    break
                lines.append(line)
            task = "\n".join(lines).strip()
            if not task:
                continue
        else:
            task = first_line.strip()

        if task.lower() == "quit":
            print("[bye] Agent exited")
            break
        if task.lower() == "clear":
            agent.memory.clear()
            print("[clear] Memory cleared\n")
            continue
        if task.lower() == "info":
            print(agent.describe())
            print(f"Memory: {len(agent.memory.short)} 条消息")
            print(f"Working: {agent.memory.working.snapshot()}\n")
            continue

        print("Agent: ", end="", flush=True)
        try:
            reply = await agent.run(task)
            print(reply.content)
            print()
        except Exception as e:
            print(f"\n❌ 运行异常：{e}\n")

    await agent.close()


# ── CLI ─────────────────────────────────────────────


def main():
    parser = argparse.ArgumentParser(
        description="气固热导 AI Agent — 高超声速气动热物理研究助手"
    )
    parser.add_argument(
        "--task", "-t", type=str, default=None,
        help="单次任务（省略则进入交互模式）",
    )
    parser.add_argument(
        "--llm", "-l", type=str, default="vllm_local",
        choices=["vllm_local", "bailian", "siliconflow", "ollama", "custom"],
        help="LLM 后端选择",
    )
    parser.add_argument(
        "--mode", "-m", type=str, default="react",
        choices=["react", "plan_execute"],
        help="Agent 运行模式",
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true", default=False,
        help="打印工具调用详情",
    )
    parser.add_argument(
        "--model", type=str, default=None,
        help="覆盖 LLM 模型名",
    )
    parser.add_argument(
        "--base-url", type=str, default=None,
        help="覆盖 LLM API 地址",
    )

    args = parser.parse_args()

    # 构建配置
    config = AgentConfig(llm=args.llm, mode=args.mode, verbose=args.verbose)
    if args.model:
        config.llm.model = args.model
    if args.base_url:
        config.llm.base_url = args.base_url

    # 运行
    if args.task:
        asyncio.run(run_once(config, args.task))
    else:
        asyncio.run(interactive(config))


if __name__ == "__main__":
    main()
