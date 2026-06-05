#!/usr/bin/env python3
"""
气固热导 AI Agent — Gradio Web UI

用法：
    # 连接本地 vLLM
    python app.py --llm vllm_local

    # 连接百炼 API
    python app.py --llm bailian

    # 自定义端点
    python app.py --llm custom --base-url http://localhost:8000/v1

    # 指定模式
    python app.py --mode plan_execute

DSW 部署时自动获得公网链接（Gradio proxy）。
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

# 路径
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


# ── 全局 Agent 实例 ─────────────────────────────────

_agent = None
_config = None


def build_agent(llm: str = "vllm_local", mode: str = "react", verbose: bool = False):
    """构建并装配 Agent。"""
    global _agent, _config

    _config = AgentConfig(llm=llm, mode=mode, verbose=verbose)
    _agent = _config.build_agent()

    # 装配全部 9 个工具
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


# ── Chat 处理 ───────────────────────────────────────


async def respond(message: str, history: list):
    """处理每轮对话。"""
    if _agent is None:
        yield "⚠️ Agent 未初始化，请检查 LLM 连接配置。"
        return

    # Agent 内部自动管理记忆，history 参数仅用于 Gradio 显示
    try:
        reply = await _agent.run(message)
    except Exception as e:
        yield f"❌ Agent 运行异常：{e}"
        return

    yield reply.content


# ── 状态查看 ────────────────────────────────────────


def get_agent_info():
    """返回 Agent 当前状态。"""
    if _agent is None:
        return "Agent 未初始化"

    tools = _agent.registry.list_names()
    return (
        f"**LLM**: {_agent.llm.config.model} @ {_agent.llm.config.base_url}\n"
        f"**Mode**: {_agent.mode}\n"
        f"**Tools** ({len(tools)}): {', '.join(tools)}\n"
        f"**Memory**: {len(_agent.memory.short)} 条消息"
    )


# ── CLI ─────────────────────────────────────────────


def main():
    parser = argparse.ArgumentParser(description="气固热导 AI Agent — Gradio Web UI")
    parser.add_argument(
        "--llm", "-l", type=str, default="vllm_local",
        choices=["vllm_local", "bailian", "ollama", "custom"],
        help="LLM 后端选择",
    )
    parser.add_argument(
        "--mode", "-m", type=str, default="react",
        choices=["react", "plan_execute"],
        help="Agent 运行模式",
    )
    parser.add_argument(
        "--base-url", type=str, default=None,
        help="覆盖 LLM API 地址（--llm custom 时必填）",
    )
    parser.add_argument(
        "--model", type=str, default=None,
        help="覆盖 LLM 模型名",
    )
    parser.add_argument(
        "--port", "-p", type=int, default=7860,
        help="Gradio 服务端口（默认 7860）",
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true", default=False,
        help="打印工具调用详情",
    )
    parser.add_argument(
        "--share", action="store_true", default=False,
        help="生成 Gradio 公网链接（非 DSW 环境用）",
    )

    args = parser.parse_args()
    llm = args.llm
    if llm == "custom" and not args.base_url:
        parser.error("--llm custom 需要 --base-url")

    # 构建 Agent
    agent = build_agent(llm=llm, mode=args.mode, verbose=args.verbose)
    if args.model:
        agent.llm.config.model = args.model
    if args.base_url:
        agent.llm.config.base_url = args.base_url

    # 标题与描述
    title = "气固热导 AI Agent — 高超声速气动热物理研究助手"
    description = f"""
**LLM**: {agent.llm.config.model} @ {agent.llm.config.base_url}
**Mode**: {agent.mode} | **Tools**: {', '.join(agent.registry.list_names())}

输入研究问题，Agent 自动检索文献、执行计算、生成报告。
"""

    # 构建 UI
    demo = gr.ChatInterface(
        fn=respond,
        title=title,
        description=description,
        theme="soft",
        examples=[
            "比较 SiO₂ 和 SiC 在 2000K 下的催化复合系数",
            "计算马赫数15、高度55km、头部半径0.5m的驻点热流密度",
            "搜索近3年高超声速边界层转捩的研究进展",
        ],
        undo_btn="撤销",
        clear_btn="清空记忆",
    )

    print(f"[*] Agent 已就绪")
    print(f"    LLM: {agent.llm.config.model} @ {agent.llm.config.base_url}")
    print(f"    Mode: {agent.mode}")
    print(f"    Tools: {len(agent.registry)} 个")
    print(f"    Port: {args.port}")
    print()

    demo.launch(
        server_name="0.0.0.0",
        server_port=args.port,
        share=args.share,
    )


if __name__ == "__main__":
    main()
