"""
PDF 论文解析工具 —— 文本提取 / 元数据 / 章节结构 / 关键参数识别

基于 PyMuPDF (fitz) 实现，比 pdfplumber 快 3-5 倍。
支持模式：
- metadata: 标题/作者/创建日期
- full: 全文文本
- sections: 章节标题结构
- parameters: 气动热关键参数自动识别
- search: 关键词定位
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from core.action import Action


class PDFAnalysisTool(Action):
    """PDF 论文解析 —— 文本/元数据/章节/参数提取。"""

    name = "parse_pdf"
    description = (
        "解析 PDF 论文文件，提取文本内容、元数据、章节结构、关键参数。"
        "支持模式：metadata(标题/作者), full(全文), sections(章节标题), "
        "parameters(气动热参数自动识别), search(关键词定位)。"
        "适用于：阅读论文、提取数据、验证引用、文献综述。"
    )
    parameters = {
        "type": "object",
        "properties": {
            "file_path": {
                "type": "string",
                "description": "PDF 文件的绝对路径或相对于项目根目录的路径。例如: '06_论文工作区/01_参考文献/HMT-D-26-01279.pdf'",
            },
            "mode": {
                "type": "string",
                "enum": ["metadata", "full", "sections", "parameters", "search"],
                "description": (
                    "解析模式：\n"
                    "- metadata: 提取标题、作者、创建日期等元数据\n"
                    "- full: 提取全部文本内容\n"
                    "- sections: 提取章节标题结构\n"
                    "- parameters: 自动识别气动热关键参数（温度、压力、热流、催化系数等）\n"
                    "- search: 在 PDF 中搜索指定关键词"
                ),
                "default": "metadata",
            },
            "keyword": {
                "type": "string",
                "description": "当 mode='search' 时的搜索关键词。例如: 'catalytic recombination'",
            },
            "max_pages": {
                "type": "integer",
                "description": "最大解析页数。默认 50，设为 0 表示全部。用于限制大文件的解析范围。",
                "default": 50,
            },
            "extract_tables": {
                "type": "boolean",
                "description": "是否尝试提取表格（仅 mode='full' 时有效）。可能较慢。",
                "default": False,
            },
        },
        "required": ["file_path"],
    }

    # ── 气动热参数正则模式 ──────────────────────────
    PARAM_PATTERNS = {
        "温度": [
            (r"(\d+\.?\d*)\s*[Kk]\b", "K"),
            (r"(\d+\.?\d*)\s*°C", "°C"),
            (r"(\d+\.?\d*)\s*℃", "°C"),
            (r"temperature[:\s]*(\d+\.?\d*)\s*[Kk]", "K"),
        ],
        "热流密度": [
            (r"(\d+\.?\d*)\s*[Ww]/[m㎡][²2]\b", "W/m²"),
            (r"(\d+\.?\d*)\s*[kK][Ww]/[m㎡][²2]\b", "kW/m²"),
            (r"(\d+\.?\d*)\s*[Mm][Ww]/[m㎡][²2]\b", "MW/m²"),
            (r"heat\s*flux[:\s]*(\d+\.?\d*)", "W/m²"),
        ],
        "压力": [
            (r"(\d+\.?\d*)\s*[Pp][Aa]\b", "Pa"),
            (r"(\d+\.?\d*)\s*[kK][Pp][Aa]\b", "kPa"),
            (r"(\d+\.?\d*)\s*[aA][tT][mM]\b", "atm"),
            (r"(\d+\.?\d*)\s*[bB][aA][rR]\b", "bar"),
        ],
        "速度": [
            (r"(\d+\.?\d*)\s*[mM]/[sS]\b", "m/s"),
            (r"(\d+\.?\d*)\s*[kK][mM]/[sS]\b", "km/s"),
            (r"Mach\s*(\d+\.?\d*)", "Ma"),
        ],
        "催化复合系数": [
            (r"[γγ][_ ]?\w*\s*[=≈～~]\s*(\d+\.?\d*(?:[eE][+-]?\d+)?)", ""),
            (r"catalytic[-\s]?\w*\s*coefficient[:\s]*(\d+\.?\d*(?:[eE][+-]?\d+)?)", ""),
            (r"recombination[-\s]?\w*\s*coefficient[:\s]*(\d+\.?\d*(?:[eE][+-]?\d+)?)", ""),
        ],
        "高度/距离": [
            (r"(\d+\.?\d*)\s*[kK][mM]\b", "km"),
            (r"(\d+\.?\d*)\s*[mM][mM]\b", "mm"),
            (r"(\d+\.?\d*)\s*[μµm][mM]\b", "μm"),
        ],
        "Knudsen数": [
            (r"[Kk]nudsen[-\s]?\w*\s*[=≈～~]?\s*(\d+\.?\d*(?:[eE][+-]?\d+)?)", ""),
            (r"[Kk][Nn]\s*[=≈～~]\s*(\d+\.?\d*(?:[eE][+-]?\d+)?)", ""),
        ],
    }

    def __init__(self):
        self._fitz = None

    def _ensure_fitz(self):
        """延迟导入 PyMuPDF。"""
        if self._fitz is None:
            try:
                import fitz
                self._fitz = fitz
            except ImportError:
                raise ImportError(
                    "需要安装 PyMuPDF：pip install pymupdf\n"
                    "或使用 conda：conda install -c conda-forge pymupdf"
                )

    async def run(
        self,
        file_path: str,
        mode: str = "metadata",
        keyword: str = "",
        max_pages: int = 50,
        extract_tables: bool = False,
    ) -> str:
        # ── 路径解析 ──────────────────────────────────
        pdf_path = Path(file_path)
        if not pdf_path.is_absolute():
            # 相对路径，以 Agent 目录（05_AI_Agent/）为基准
            agent_dir = Path(__file__).parent.parent
            pdf_path = (agent_dir / file_path).resolve()

        if not pdf_path.exists():
            return f"❌ 文件不存在：{pdf_path}"

        if pdf_path.suffix.lower() != ".pdf":
            return f"❌ 不是 PDF 文件：{pdf_path.name}"

        try:
            self._ensure_fitz()
        except ImportError as e:
            return f"❌ {e}"

        # ── 打开 PDF ──────────────────────────────────
        try:
            doc = self._fitz.open(str(pdf_path))
        except Exception as e:
            return f"❌ 无法打开 PDF：{e}"

        result = ""

        try:
            if mode == "metadata":
                result = self._extract_metadata(doc, pdf_path)
            elif mode == "full":
                result = self._extract_full_text(doc, pdf_path, max_pages)
            elif mode == "sections":
                result = self._extract_sections(doc, pdf_path, max_pages)
            elif mode == "parameters":
                result = self._extract_parameters(doc, pdf_path, max_pages)
            elif mode == "search":
                result = self._search_keyword(doc, pdf_path, keyword, max_pages)
            else:
                result = f"❌ 未知模式：{mode}"
        finally:
            doc.close()

        return result

    # ── Mode: metadata ───────────────────────────────

    def _extract_metadata(self, doc, pdf_path: Path) -> str:
        """提取 PDF 元数据。"""
        meta = doc.metadata
        toc = doc.get_toc()  # 目录
        pages = doc.page_count

        title = meta.get("title", "未知")
        author = meta.get("author", "未知")
        subject = meta.get("subject", "")
        creator = meta.get("creator", "")
        creation_date = meta.get("creationDate", "")

        lines = [
            f"## 📄 PDF 元数据：{pdf_path.name}",
            f"",
            f"**标题**：{title}",
            f"**作者**：{author}",
            f"**页数**：{pages}",
        ]
        if subject:
            lines.append(f"**主题**：{subject}")
        if creation_date:
            lines.append(f"**创建日期**：{creation_date[:10]}")
        if creator:
            lines.append(f"**生成工具**：{creator}")

        if toc:
            lines.append(f"\n### 目录结构（前 15 条）")
            for level, heading, page_num in toc[:15]:
                indent = "  " * (level - 1)
                lines.append(f"{indent}- [{heading}] → 第 {page_num} 页")

        return "\n".join(lines)

    # ── Mode: full ───────────────────────────────────

    def _extract_full_text(self, doc, pdf_path: Path, max_pages: int) -> str:
        """提取全文文本。"""
        pages_to_read = min(doc.page_count, max_pages) if max_pages > 0 else doc.page_count

        lines = [
            f"## 📄 {pdf_path.name}",
            f"**总页数**：{doc.page_count} | **已读取**：{pages_to_read} 页\n",
        ]

        total_chars = 0
        char_limit = 15000  # 避免返回超长内容

        for page_num in range(pages_to_read):
            page = doc[page_num]
            text = page.get_text("text")

            if text.strip():
                lines.append(f"### ── 第 {page_num + 1} 页 ──")
                if total_chars + len(text) > char_limit:
                    remaining = char_limit - total_chars
                    lines.append(text[:remaining])
                    lines.append(f"\n⚠️ **文本截断**：已达 {char_limit} 字符上限，剩余页未读取。")
                    break
                lines.append(text)
                total_chars += len(text)

        return "\n".join(lines)

    # ── Mode: sections ───────────────────────────────

    def _extract_sections(self, doc, pdf_path: Path, max_pages: int) -> str:
        """提取章节标题结构。"""
        pages_to_read = min(doc.page_count, max_pages) if max_pages > 0 else doc.page_count

        lines = [
            f"## 📑 章节结构：{pdf_path.name}",
            f"",
        ]

        section_pattern = re.compile(
            r"^(\d+(?:\.\d+)*)\s+(.+)|"
            r"^(Abstract|Introduction|Method|Experiment|Result|Discussion|Conclusion|Reference|Appendix|"
            r"Nomenclature|Acknowledgment)",
            re.IGNORECASE
        )

        found_sections: list[tuple[int, str]] = []

        for page_num in range(pages_to_read):
            page = doc[page_num]
            # 先看目录
            blocks = page.get_text("blocks")
            for block in blocks:
                text = block[4] if len(block) > 4 else ""  # block 格式: (x0,y0,x1,y1,text,block_no,block_type)

                # 只取字体较大的文本块（可能是标题）
                # block[2]-block[0] = x范围, block[3]-block[1] = y范围
                is_bold = False  # fitz 不直接提供字体信息，用启发式判断
                text_stripped = text.strip()

                if 10 < len(text_stripped) < 150:  # 标题长度
                    match = section_pattern.match(text_stripped)
                    if match:
                        found_sections.append((page_num + 1, text_stripped))

        if found_sections:
            for page, section in found_sections:
                lines.append(f"- [第 {page} 页] {section}")
        else:
            lines.append("未检测到显式章节标题。建议使用 'full' 模式查看全文。")

        return "\n".join(lines)

    # ── Mode: parameters ─────────────────────────────

    def _extract_parameters(self, doc, pdf_path: Path, max_pages: int) -> str:
        """自动识别气动热关键参数。"""
        pages_to_read = min(doc.page_count, max_pages) if max_pages > 0 else doc.page_count

        lines = [
            f"## 🔬 气动热参数识别：{pdf_path.name}",
            f"**扫描页数**：{pages_to_read}\n",
        ]

        full_text = ""
        for page_num in range(pages_to_read):
            full_text += doc[page_num].get_text("text") + "\n"

        found_any = False
        for category, patterns in self.PARAM_PATTERNS.items():
            category_results = []
            for pattern, unit in patterns:
                for match in re.finditer(pattern, full_text, re.IGNORECASE):
                    value = match.group(1) if match.lastindex else match.group(0)
                    # 获取上下文（前后 40 字符）
                    start = max(0, match.start() - 40)
                    end = min(len(full_text), match.end() + 40)
                    context = full_text[start:end].replace("\n", " ").strip()
                    # 高亮匹配值
                    display = f"{value} {unit}".strip() if unit else value
                    category_results.append((display, context))

            if category_results:
                found_any = True
                lines.append(f"### {category}")
                # 去重（取前 10 个唯一值）
                seen = set()
                unique = []
                for val, ctx in category_results:
                    if val not in seen:
                        seen.add(val)
                        unique.append((val, ctx))
                for val, ctx in unique[:10]:
                    lines.append(f"- **{val}** — `...{ctx}...`")
                if len(unique) > 10:
                    lines.append(f"  *... 另有 {len(unique) - 10} 处匹配*")
                lines.append("")

        if not found_any:
            lines.append("未识别到气动热相关参数。可能是非气动热领域论文，或 PDF 文本提取质量较低。")

        return "\n".join(lines)

    # ── Mode: search ─────────────────────────────────

    def _search_keyword(self, doc, pdf_path: Path, keyword: str, max_pages: int) -> str:
        """在 PDF 中搜索关键词。"""
        if not keyword:
            return "❌ 请提供搜索关键词（keyword 参数）。"

        pages_to_read = min(doc.page_count, max_pages) if max_pages > 0 else doc.page_count

        lines = [
            f"## 🔍 搜索 '{keyword}' — {pdf_path.name}",
            f"**扫描页数**：{pages_to_read}\n",
        ]

        found_count = 0
        for page_num in range(pages_to_read):
            page = doc[page_num]
            text = page.get_text("text")

            if keyword.lower() in text.lower():
                found_count += 1
                # 提取匹配上下文
                idx = text.lower().find(keyword.lower())
                start = max(0, idx - 80)
                end = min(len(text), idx + len(keyword) + 80)
                snippet = text[start:end].replace("\n", " ").strip()

                lines.append(f"**第 {page_num + 1} 页**：`...{snippet}...`")

                if found_count >= 20:
                    lines.append(f"\n⚠️ 已显示前 20 处匹配，可能还有更多。")
                    break

        if found_count == 0:
            lines.append(f"未找到 '{keyword}'。")

        return "\n".join(lines)
