#!/usr/bin/env python3
"""
AeroThermAI — Gradio Web UI

Usage:
    # Connect to local vLLM
    python app.py --llm vllm_local

    # Connect to Bailian API
    python app.py --llm bailian

    # Custom endpoint
    python app.py --llm custom --base-url http://localhost:8000/v1

    # Specify mode
    python app.py --mode plan_execute

DSW deployment automatically provides a public URL (Gradio proxy).
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

# Path setup
AGENT_DIR = Path(__file__).parent
PROJECT = AGENT_DIR.parent
sys.path.insert(0, str(AGENT_DIR))
sys.path.insert(0, str(PROJECT))

import gradio as gr

from config import AgentConfig
from tools.search import LiteratureSearchTool
from tools.web_search import WebSearchTool
from tools.compute import AeroThermalComputeTool
from tools.code_exec import CodeExecutionTool
from tools.citation import CitationResolverTool
from tools.pdf_parser import PDFAnalysisTool
from tools.report import ReportTool, ExportFindingTool
from tools.pandoc_export import PandocExportTool


# ── Global Agent Instance ────────────────────────────

_agent = None
_config = None


def build_agent(llm: str = "vllm_local", mode: str = "react", verbose: bool = False, critique_rounds: int = 2):
    """Build and equip the Agent."""
    global _agent, _config

    _config = AgentConfig(llm=llm, mode=mode, verbose=verbose, critique_rounds=critique_rounds)
    _agent = _config.build_agent()

    # Equip all 9 tools
    _agent.equip(LiteratureSearchTool())
    _agent.equip(WebSearchTool())
    _agent.equip(AeroThermalComputeTool())
    _agent.equip(CodeExecutionTool())
    _agent.equip(CitationResolverTool())
    _agent.equip(PDFAnalysisTool())
    _agent.equip(ReportTool())
    _agent.equip(ExportFindingTool())
    _agent.equip(PandocExportTool())

    return _agent


# ── Chat Handler ────────────────────────────────────


async def respond(message: str, history: list):
    """Handle each dialogue turn."""
    if _agent is None:
        yield "Gradio Web UI — Hypersonic Aerothermodynamics Research Assistant"
        return

    # Agent internally manages memory; history param is only used by Gradio for display
    try:
        reply = await _agent.run(message)
    except Exception as e:
        yield f"Agent execution error: {e}"
        return

    yield reply.content


# ── Status Viewer ───────────────────────────────────


def get_agent_info():
    """Return current Agent status."""
    if _agent is None:
        return "Agent not initialized"

    tools = _agent.registry.list_names()
    return (
        f"**LLM**: {_agent.llm.config.model} @ {_agent.llm.config.base_url}\n"
        f"**Mode**: {_agent.mode}\n"
        f"**Tools** ({len(tools)}): {', '.join(tools)}\n"
        f"**Memory**: {len(_agent.memory.short)} messages"
    )


# ── CLI ─────────────────────────────────────────────


def main():
    parser = argparse.ArgumentParser(description="AeroThermAI — Gradio Web UI")
    parser.add_argument(
        "--llm", "-l", type=str, default="vllm_local",
        choices=["vllm_local", "bailian", "ollama", "custom"],
        help="LLM backend selection",
    )
    parser.add_argument(
        "--mode", "-m", type=str, default="react",
        choices=["react", "plan_execute"],
        help="Agent running mode",
    )
    parser.add_argument(
        "--base-url", type=str, default=None,
        help="Override LLM API address (required when --llm custom)",
    )
    parser.add_argument(
        "--model", type=str, default=None,
        help="Override LLM model name",
    )
    parser.add_argument(
        "--port", "-p", type=int, default=7860,
        help="Gradio server port (default 7860)",
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true", default=False,
        help="Print tool call details",
    )
    parser.add_argument(
        "--share", action="store_true", default=False,
        help="Generate Gradio public URL (for non-DSW environments)",
    )
    parser.add_argument(
        "--critique-rounds", type=int, default=2,
        help="Number of self-critique rounds after ReAct loop (default 2, set to 0 to disable)",
    )

    args = parser.parse_args()
    llm = args.llm
    if llm == "custom" and not args.base_url:
        parser.error("--llm custom requires --base-url")

    # Build Agent
    agent = build_agent(llm=llm, mode=args.mode, verbose=args.verbose, critique_rounds=args.critique_rounds)
    if args.model:
        agent.llm.config.model = args.model
    if args.base_url:
        agent.llm.config.base_url = args.base_url

    # Title and description
    title = "AeroThermAI — Hypersonic Aerothermodynamics Research Assistant"
    description = f"""
**LLM**: {agent.llm.config.model} @ {agent.llm.config.base_url}
**Mode**: {agent.mode} | **Tools**: {', '.join(agent.registry.list_names())}

Enter a research question; the Agent will automatically retrieve literature, run computations, and generate reports.
"""

    # Build UI
    demo = gr.ChatInterface(
        fn=respond,
        title=title,
        description=description,
        theme="soft",
        examples=[
            "Compare catalytic recombination coefficients of SiO2 and SiC at 2000 K",
            "Calculate stagnation-point heat flux for Mach 15, altitude 55 km, nose radius 0.5 m",
            "Search recent 3-year research progress on hypersonic boundary-layer transition",
        ],
        undo_btn="Undo",
        clear_btn="Clear Memory",
    )

    print(f"[*] Agent ready")
    print(f"    LLM: {agent.llm.config.model} @ {agent.llm.config.base_url}")
    print(f"    Mode: {agent.mode}")
    print(f"    Tools: {len(agent.registry)}")
    print(f"    Port: {args.port}")
    print()

    demo.launch(
        server_name="0.0.0.0",
        server_port=args.port,
        share=args.share,
    )


if __name__ == "__main__":
    main()
