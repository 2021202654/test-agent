"""
报告生成工具 —— 将 Agent 研究结果输出为结构化 Markdown 报告

支持两种模式：
1. generate_report: 生成完整研究报告（含标题、时间戳、内容、引用）
2. export_finding:  追加一条结构化研究发现到当前工作区

所有报告保存到 05_AI_Agent/reports/ 目录。
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from core.action import Action


class ReportTool(Action):
    """研究报告生成 —— 将 Agent 推理结果持久化为 Markdown 报告。"""

    name = "generate_report"
    description = (
        "将当前研究任务的发现、计算过程、文献引用等内容生成为结构化 Markdown 报告，"
        "保存到 reports/ 目录。适用于：研究结论归档、实验记录、文献综述汇总。"
        "报告自动附带时间戳，引用文献请注明 DOI。"
    )
    parameters = {
        "type": "object",
        "properties": {
            "title": {
                "type": "string",
                "description": "报告标题，简洁明确。例如: 'SiO₂催化复合系数文献综述'",
            },
            "content": {
                "type": "string",
                "description": (
                    "报告正文，支持 Markdown 格式。应包含：研究背景、方法/工具、"
                    "主要发现、数值计算结果（如有）、引用文献（附DOI）、"
                    "不确定性说明、结论与建议。"
                ),
            },
            "findings": {
                "type": "array",
                "description": "可选的结构化研究发现列表，每条包含 claim/evidence/confidence/source",
                "items": {
                    "type": "object",
                    "properties": {
                        "claim": {"type": "string", "description": "研究发现或结论，一句话概括"},
                        "evidence": {"type": "string", "description": "支撑该结论的证据或推理过程"},
                        "confidence": {
                            "type": "string",
                            "enum": ["高", "中", "低"],
                            "description": "置信度：高=文献直接支撑或计算验证，中=间接推理，低=待验证推测",
                        },
                        "source": {"type": "string", "description": "证据来源（DOI、文献标题或工具名称）"},
                    },
                    "required": ["claim", "confidence"],
                },
            },
            "references": {
                "type": "array",
                "description": "报告中引用的文献列表",
                "items": {
                    "type": "object",
                    "properties": {
                        "title": {"type": "string", "description": "文献标题"},
                        "doi": {"type": "string", "description": "DOI（不含 https://doi.org/ 前缀）"},
                        "year": {"type": "string", "description": "发表年份"},
                        "relevance": {"type": "string", "description": "与本研究的相关性说明"},
                    },
                    "required": ["title"],
                },
            },
        },
        "required": ["title", "content"],
    }

    def __init__(self, output_dir: str | Path | None = None):
        if output_dir:
            self._output_dir = Path(output_dir)
        else:
            self._output_dir = Path(__file__).parent.parent / "reports"
        self._output_dir.mkdir(parents=True, exist_ok=True)

    async def run(
        self,
        title: str,
        content: str,
        findings: list[dict] | None = None,
        references: list[dict] | None = None,
    ) -> str:
        """生成 Markdown 报告并保存。"""
        timestamp = datetime.now()
        safe_title = self._sanitize_filename(title)
        filename = f"{timestamp.strftime('%Y%m%d_%H%M%S')}_{safe_title}.md"
        filepath = self._output_dir / filename

        report = self._build_report(
            title=title,
            content=content,
            findings=findings or [],
            references=references or [],
            timestamp=timestamp,
        )

        filepath.write_text(report, encoding="utf-8")

        return (
            f"✅ 报告已生成：{filename}\n"
            f"📁 保存路径：{filepath}\n"
            f"📏 报告长度：{len(report)} 字符\n"
            f"📎 结构化发现：{len(findings or [])} 条\n"
            f"📚 引用文献：{len(references or [])} 篇"
        )

    # ── 内部方法 ────────────────────────────────────

    def _build_report(
        self,
        title: str,
        content: str,
        findings: list[dict],
        references: list[dict],
        timestamp: datetime,
    ) -> str:
        lines = [
            f"# {title}",
            "",
            f"**生成时间**：{timestamp.strftime('%Y-%m-%d %H:%M:%S')}",
            f"**生成工具**：AeroThermalExpert Agent (ReportTool)",
            "",
            "---",
            "",
            "## 📋 研究内容",
            "",
            content,
        ]

        if findings:
            lines.extend([
                "",
                "---",
                "",
                "## 🔍 结构化发现",
                "",
                "| # | 结论 | 置信度 | 证据来源 |",
                "|---|------|--------|----------|",
            ])
            for i, f in enumerate(findings, 1):
                claim = f.get("claim", "—")
                confidence = f.get("confidence", "—")
                evidence = f.get("evidence", "")
                source = f.get("source", "")
                ev_src = f"{evidence} ({source})" if source else evidence
                lines.append(f"| {i} | {claim} | **{confidence}** | {ev_src} |")
            lines.append("")

        if references:
            lines.extend([
                "---",
                "",
                "## 📚 参考文献",
                "",
            ])
            for i, ref in enumerate(references, 1):
                title = ref.get("title", "未知标题")
                doi = ref.get("doi", "")
                year = ref.get("year", "?")
                relevance = ref.get("relevance", "")
                doi_str = f" [{doi}](https://doi.org/{doi})" if doi else ""
                lines.append(f"{i}. **{title}**{doi_str} ({year})")
                if relevance:
                    lines.append(f"   - 相关性：{relevance}")
                lines.append("")

        lines.extend([
            "---",
            "",
            f"*本报告由气固热导 AI Agent 自动生成，内容需经人工审核确认。*",
        ])

        return "\n".join(lines)

    @staticmethod
    def _sanitize_filename(title: str) -> str:
        """清理文件名中的非法字符。"""
        safe = title.replace("/", "_").replace("\\", "_").replace(":", "：")
        safe = safe.replace("*", "").replace("?", "").replace('"', "")
        safe = safe.replace("<", "").replace(">", "").replace("|", "")
        # 限制长度
        if len(safe) > 60:
            safe = safe[:60]
        return safe.strip()


class ExportFindingTool(Action):
    """单条发现导出 —— 轻量级，适合在 ReAct 循环中逐条记录。"""

    name = "export_finding"
    description = (
        "将单条研究结论追加保存到 findings/ 目录的 Markdown 日志中。"
        "适合在推理过程中逐步记录发现，而非等全部完成后再生成报告。"
    )
    parameters = {
        "type": "object",
        "properties": {
            "claim": {
                "type": "string",
                "description": "研究发现或结论，一句话概括",
            },
            "evidence": {
                "type": "string",
                "description": "支撑证据（文献引用、计算结果、逻辑推理）",
            },
            "confidence": {
                "type": "string",
                "enum": ["高", "中", "低"],
                "description": "置信度：高/中/低",
            },
            "source": {
                "type": "string",
                "description": "证据来源（DOI、文献标题或工具名称）",
            },
            "tags": {
                "type": "array",
                "items": {"type": "string"},
                "description": "分类标签，如 ['catalytic', 'SiO2', 'experiment']",
            },
        },
        "required": ["claim", "confidence"],
    }

    def __init__(self, output_dir: str | Path | None = None):
        if output_dir:
            self._output_dir = Path(output_dir)
        else:
            self._output_dir = Path(__file__).parent.parent / "findings"
        self._output_dir.mkdir(parents=True, exist_ok=True)
        self._log_file = self._output_dir / "findings_log.md"

    async def run(
        self,
        claim: str,
        confidence: str = "中",
        evidence: str = "",
        source: str = "",
        tags: list[str] | None = None,
    ) -> str:
        """追加一条发现到 findings 日志。"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        tags_str = " ".join(f"`{t}`" for t in (tags or []))

        entry = (
            f"### {claim}\n"
            f"- **时间**：{timestamp}\n"
            f"- **置信度**：{confidence}\n"
        )
        if evidence:
            entry += f"- **证据**：{evidence}\n"
        if source:
            entry += f"- **来源**：{source}\n"
        if tags_str:
            entry += f"- **标签**：{tags_str}\n"
        entry += "\n"

        # 追加写入
        with open(self._log_file, "a", encoding="utf-8") as f:
            # 如果文件不存在或为空，写入标题
            if not self._log_file.exists() or self._log_file.stat().st_size == 0:
                f.write("# 研究发现日志\n\n> 由 AeroThermalExpert Agent 自动记录\n\n")
            f.write(entry)

        return (
            f"✅ 发现已记录\n"
            f"📝 结论：{claim}\n"
            f"🎯 置信度：{confidence}\n"
            f"📁 日志文件：{self._log_file}"
        )
