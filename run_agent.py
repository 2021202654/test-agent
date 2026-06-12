#!/usr/bin/env python3
"""
Gas-Solid Thermal Conductivity AI Agent — Command Line Interface

Usage:
    # Interactive mode
    python run_agent.py

    # Single Q&A
    python run_agent.py --task "Compare catalytic recombination coefficients of SiO2 and SiC at 2000K"

    # Specify LLM
    python run_agent.py --llm vllm_local
    python run_agent.py --llm bailian
    python run_agent.py --llm ollama

    # Plan-Execute mode
    python run_agent.py --mode plan_execute --task "Evaluate cross-scale applicability of existing gas-solid interface catalytic models"

Dependencies:
    pip install pydantic httpx numpy
    # FAISS retrieval requires: pip install faiss-cpu
    # Vector retrieval embedding requires embedding model configuration
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

# Ensure 05_AI_Agent/ and project root are in path
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
    """Uniformly equip all tools (including tools requiring LLM injection)."""
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
    # AI Scientist core: hypothesis generator (requires LLM + retrieval tool injection)
    agent.equip(HypothesisGenerator(
        llm=agent.llm,
        search_tool=search,
        web_tool=web,
    ))


async def run_once(config: AgentConfig, task: str):
    """Single Q&A mode."""
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
        import traceback
        print(f"\n[!] Agent error: {e}")
        print("[TRACEBACK]")
        traceback.print_exc()
    finally:
        await agent.close()


async def interactive(config: AgentConfig):
    """Interactive mode — continuous dialogue."""
    agent = config.build_agent()
    _equip_tools(agent, config)

    print(f"\n{'='*60}")
    print(f" Gas-Solid Thermal AI Agent — {agent.role.name}")
    print(f" LLM: {config.llm.model} @ {config.llm.base_url}")
    print(f" Mode: {config.mode} | Tools: {', '.join(agent.registry.list_names())}")
    print(f"{'='*60}")
    print(" Enter 'quit' to exit | 'clear' to clear memory | 'info' to view status")
    print(' Multi-line input: enter """ to start, then """ to end\n')

    while True:
        try:
            first_line = input("You: ")
        except (EOFError, KeyboardInterrupt):
            print("\n[bye] Agent exited")
            break

        if not first_line.strip():
            continue

        # ── Multi-line paste mode ─────────────────────
        if first_line.strip() == '"""':
            lines = []
            print("> (Multi-line input mode, enter \"\"\" to end)")
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
            print(f"Memory: {len(agent.memory.short)} messages")
            print(f"Working: {agent.memory.working.snapshot()}\n")
            continue

        print("Agent: ", end="", flush=True)
        try:
            reply = await agent.run(task)
            print(reply.content)
            print()
        except Exception as e:
            print(f"\n[!] Runtime error: {e}\n")

    await agent.close()


# ── CLI ─────────────────────────────────────────────


def main():
    parser = argparse.ArgumentParser(
        description="Gas-Solid Thermal AI Agent — Hypersonic aerodynamic thermophysics research assistant"
    )
    parser.add_argument(
        "--task", "-t", type=str, default=None,
        help="Single task (if omitted, enters interactive mode)",
    )
    parser.add_argument(
        "--llm", "-l", type=str, default="vllm_local",
        choices=["vllm_local", "bailian", "siliconflow", "ollama", "custom"],
        help="LLM backend selection",
    )
    parser.add_argument(
        "--mode", "-m", type=str, default="react",
        choices=["react", "plan_execute"],
        help="Agent execution mode",
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true", default=False,
        help="Print tool call details",
    )
    parser.add_argument(
        "--critique-rounds", type=int, default=2,
        help="Number of self-critique rounds after ReAct loop (default 2, set to 0 to disable)",
    )
    parser.add_argument(
        "--model", type=str, default=None,
        help="Override LLM model name",
    )
    parser.add_argument(
        "--base-url", type=str, default=None,
        help="Override LLM API address",
    )

    args = parser.parse_args()

    # Build configuration
    config = AgentConfig(llm=args.llm, mode=args.mode, verbose=args.verbose, critique_rounds=args.critique_rounds)
    if args.model:
        config.llm.model = args.model
    if args.base_url:
        config.llm.base_url = args.base_url

    # Execute
    if args.task:
        asyncio.run(run_once(config, args.task))
    else:
        asyncio.run(interactive(config))


if __name__ == "__main__":
    main()
