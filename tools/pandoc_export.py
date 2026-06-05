"""
Pandoc 格式导出工具 —— Markdown 报告 → LaTeX / DOCX / PDF

在 DSW Linux 环境中调用系统 pandoc，将 Agent 生成的 Markdown 研究报告
转换为学术论文可直接使用的 LaTeX、DOCX 或 PDF 格式。

依赖：系统需安装 pandoc（apt-get install pandoc）
      PDF 输出需 texlive-xetex（apt-get install texlive-xetex）
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from core.action import Action


class PandocExportTool(Action):
    """Markdown → LaTeX/DOCX/PDF 格式导出。"""

    name = "export_document"
    description = (
        "将 Markdown 研究报告转换为 LaTeX、DOCX 或 PDF 格式。"
        "依赖系统 pandoc（需预先安装）。"
        "LaTeX 输出支持 XeLaTeX 引擎（CJK 中文兼容），可指定模板和 .bib 参考文献。"
        "适用于：论文初稿导出、引用格式化、与 Overleaf/Word 工作流衔接。"
    )
    parameters = {
        "type": "object",
        "properties": {
            "input_path": {
                "type": "string",
                "description": (
                    "输入的 Markdown 文件路径（相对于 Agent 目录或绝对路径）。"
                    "例如: 'reports/20260602_190824_report.md'"
                ),
            },
            "output_format": {
                "type": "string",
                "enum": ["latex", "docx", "pdf"],
                "description": (
                    "输出格式：\n"
                    "- latex: LaTeX 源文件（.tex），适合 Overleaf 或本地编辑\n"
                    "- docx: Word 文档，适合导师批注、投稿转换\n"
                    "- pdf: 直接生成 PDF（需系统安装 texlive-xetex）"
                ),
                "default": "latex",
            },
            "template": {
                "type": "string",
                "description": (
                    "可选的 LaTeX 模板文件路径。仅 output_format='latex' 或 'pdf' 时生效。"
                    "例如 Elsevier 模板: 'templates/elsevier.latex'"
                ),
            },
            "reference_docx": {
                "type": "string",
                "description": (
                    "可选的 DOCX 参考样式文件路径。仅 output_format='docx' 时生效。"
                    "用于控制输出 Word 文档的字体/段落/页边距样式。"
                ),
            },
            "bibliography": {
                "type": "string",
                "description": (
                    "可选的 .bib 参考文献文件路径。pandoc 会自动使用 --citeproc 处理引用。"
                    "例如: 'refs.bib'"
                ),
            },
            "output_dir": {
                "type": "string",
                "description": "输出目录。默认为 Markdown 文件所在目录下的 exports/ 子目录。",
            },
        },
        "required": ["input_path", "output_format"],
    }

    # ── 格式 → 扩展名 + pandoc 参数映射 ──────────────

    FORMAT_MAP = {
        "latex": {
            "ext": ".tex",
            "pandoc_fmt": "latex",
            "extra_args": ["--pdf-engine=xelatex"],
            "standalone": True,
        },
        "docx": {
            "ext": ".docx",
            "pandoc_fmt": "docx",
            "extra_args": [],
            "standalone": True,
        },
        "pdf": {
            "ext": ".pdf",
            "pandoc_fmt": "pdf",
            "extra_args": [
                "--pdf-engine=xelatex",
                "-V", "CJKmainfont=Noto Serif CJK SC",
                "-V", "CJKsansfont=Noto Sans CJK SC",
                "-V", "CJKmonofont=Noto Sans Mono CJK SC",
            ],
            "standalone": True,
        },
    }

    def __init__(self):
        self._pandoc_path: str | None = None

    def _find_pandoc(self) -> str:
        """查找 pandoc 可执行文件路径。"""
        if self._pandoc_path:
            return self._pandoc_path

        # 先尝试 which
        found = shutil.which("pandoc")
        if found:
            self._pandoc_path = found
            return found

        raise FileNotFoundError(
            "未找到 pandoc。请先安装：\n"
            "  Ubuntu/Debian: sudo apt-get install pandoc\n"
            "  Conda:         conda install -c conda-forge pandoc\n"
            "  Windows:       winget install Pandoc.Pandoc"
        )

    async def run(
        self,
        input_path: str,
        output_format: str = "latex",
        template: str = "",
        reference_docx: str = "",
        bibliography: str = "",
        output_dir: str = "",
    ) -> str:
        # ── 检查 pandoc ───────────────────────────────
        try:
            pandoc = self._find_pandoc()
        except FileNotFoundError as e:
            return f"❌ {e}"

        # ── 路径解析 ──────────────────────────────────
        md_path = Path(input_path)
        if not md_path.is_absolute():
            agent_dir = Path(__file__).parent.parent
            md_path = (agent_dir / input_path).resolve()

        if not md_path.exists():
            return f"❌ 输入文件不存在：{md_path}"

        if md_path.suffix.lower() not in (".md", ".markdown", ".txt"):
            return f"⚠️ 输入文件不是 Markdown 格式：{md_path.name}（仍会尝试转换）"

        # ── 输出路径 ──────────────────────────────────
        fmt_cfg = self.FORMAT_MAP[output_format]
        if output_dir:
            out_dir = Path(output_dir)
        else:
            out_dir = md_path.parent / "exports"
        out_dir.mkdir(parents=True, exist_ok=True)

        stem = md_path.stem
        out_path = out_dir / f"{stem}{fmt_cfg['ext']}"

        # ── 模板路径解析 ──────────────────────────────
        if template:
            tmpl_path = Path(template)
            if not tmpl_path.is_absolute():
                agent_dir = Path(__file__).parent.parent
                tmpl_path = (agent_dir / template).resolve()
            if not tmpl_path.exists():
                return f"❌ 模板文件不存在：{tmpl_path}"

        if reference_docx:
            ref_path = Path(reference_docx)
            if not ref_path.is_absolute():
                agent_dir = Path(__file__).parent.parent
                ref_path = (agent_dir / reference_docx).resolve()
            if not ref_path.exists():
                return f"❌ 参考样式文件不存在：{ref_path}"

        if bibliography:
            bib_path = Path(bibliography)
            if not bib_path.is_absolute():
                agent_dir = Path(__file__).parent.parent
                bib_path = (agent_dir / bibliography).resolve()
            if not bib_path.exists():
                return f"❌ 参考文献文件不存在：{bib_path}"

        # ── 构建 pandoc 命令 ──────────────────────────
        cmd = [
            pandoc,
            str(md_path),
            "-f", "markdown+smart",
            "-t", fmt_cfg["pandoc_fmt"],
            "-o", str(out_path),
        ]

        if fmt_cfg["standalone"]:
            cmd.append("--standalone")
        cmd.extend(fmt_cfg["extra_args"])

        # 元数据
        cmd.extend(["--metadata", f"title={stem.replace('_', ' ')}"])
        cmd.extend(["--metadata", "date=\\today"])

        # 参考文献处理
        if bibliography:
            cmd.append("--citeproc")
            cmd.extend(["--bibliography", str(bib_path)])

        # 模板
        if template and output_format in ("latex", "pdf"):
            cmd.extend(["--template", str(tmpl_path)])

        # DOCX 参考样式
        if reference_docx and output_format == "docx":
            cmd.extend(["--reference-doc", str(ref_path)])

        # ── 执行 ─────────────────────────────────────
        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=120,  # pandoc 通常很快，但大文件 + citeproc 可能慢
            )
        except subprocess.TimeoutExpired:
            return "⏱️ Pandoc 转换超时（120s）。文件可能过大，或 citeproc 处理复杂引用耗时过长。"
        except Exception as e:
            return f"❌ Pandoc 执行异常：{e}"

        # ── 结果分析 ─────────────────────────────────
        lines = []
        if proc.returncode != 0:
            lines.append(f"❌ **转换失败**（退出码 {proc.returncode}）")
            stderr = proc.stderr.strip()
            if stderr:
                lines.append(f"```\n{stderr[:1000]}\n```")
            return "\n".join(lines)

        # 成功
        file_size = out_path.stat().st_size
        lines.extend([
            f"✅ **导出成功**",
            f"",
            f"| 项目 | 详情 |",
            f"|------|------|",
            f"| 输入 | {md_path.name}",
            f"| 输出 | {out_path.name}",
            f"| 格式 | {output_format.upper()}",
            f"| 大小 | {file_size:,} 字节",
            f"| 路径 | {out_path}",
        ])

        if output_format == "latex":
            lines.extend([
                "",
                "📝 **后续步骤**：",
                f"- Overleaf 在线编辑：上传 `{out_path.name}` 到 Overleaf 项目",
                f"- 本地编译：`xelatex {out_path.name}`",
                "- 配合 .bib 文件使用：设置 bibliography 参数自动处理引用",
            ])
        elif output_format == "docx":
            lines.extend([
                "",
                "📝 **后续步骤**：",
                f"- 用 Word/WPS 打开 `{out_path.name}` 继续编辑",
                "- 如需自定义样式，先用 Word 另存一个 docx 作为 reference_docx",
            ])
        elif output_format == "pdf":
            lines.extend([
                "",
                "📝 **后续步骤**：",
                f"- PDF 已可直接查看：`{out_path.name}`",
                "- 如需调整排版，修改 Markdown 源文件后重新导出",
            ])

        if proc.stderr.strip():
            stderr_preview = proc.stderr.strip()[:500]
            lines.extend(["", f"⚠️ **stderr 输出**（非致命）：", f"```\n{stderr_preview}\n```"])

        return "\n".join(lines)
