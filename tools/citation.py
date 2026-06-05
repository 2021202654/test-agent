"""
引文解析工具 —— DOI 元数据查询 + BibTeX 生成

支持两种解析路径：
1. CrossRef API（主要）：DOI → 完整元数据 + BibTeX
2. OpenAlex API（回退）：CrossRef 不可用时回退

应用场景：
- 验证 Agent 检索到的 DOI 是否真实存在
- 获取论文的完整引用信息（作者/卷期页码）
- 生成标准 BibTeX 引用条目
- 按标题+作者模糊匹配（查漏补缺）
"""

from __future__ import annotations

import re
from typing import Any

import httpx

from core.action import Action


class CitationResolverTool(Action):
    """引文解析 —— DOI 验证、元数据查询、BibTeX 生成。"""

    name = "resolve_citation"
    description = (
        "通过 DOI 查询论文完整元数据，或按标题+作者模糊匹配。"
        "返回：标题、全部作者、年份、期刊、卷期页码、摘要、引用数、BibTeX 条目。"
        "用于验证检索到的文献、生成规范引用、补充缺失的元数据。"
    )
    parameters = {
        "type": "object",
        "properties": {
            "doi": {
                "type": "string",
                "description": (
                    "论文 DOI（不含 https://doi.org/ 前缀）。"
                    "例如: '10.1017/jfm.2021.123' 或 '10.2514/1.T7003'"
                ),
            },
            "output_format": {
                "type": "string",
                "enum": ["full", "bibtex", "compact"],
                "description": "输出格式：full=完整元数据, bibtex=仅BibTeX, compact=标题+作者+期刊+年份",
                "default": "full",
            },
        },
        "required": ["doi"],
    }

    CROSSREF_BASE = "https://api.crossref.org"
    OPENALEX_BASE = "https://api.openalex.org"

    def __init__(self):
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=20.0)
        return self._client

    async def run(
        self,
        doi: str,
        output_format: str = "full",
    ) -> str:
        # 清理 DOI
        doi = self._clean_doi(doi)
        if not doi:
            return "❌ 无效的 DOI 格式。"

        client = await self._get_client()
        metadata = await self._resolve_crossref(client, doi)
        source = "CrossRef"

        if metadata is None:
            metadata = await self._resolve_openalex(client, doi)
            source = "OpenAlex"

        if metadata is None:
            return (
                f"❌ 未找到 DOI `{doi}` 对应的论文。\n"
                f"已尝试 CrossRef 和 OpenAlex 两个数据源。\n"
                f"建议：检查 DOI 拼写，或尝试在 Google Scholar 中手动搜索。"
            )

        metadata["doi"] = doi
        metadata["source"] = source

        if output_format == "bibtex":
            return self._format_bibtex(metadata)
        elif output_format == "compact":
            return self._format_compact(metadata)
        else:
            return self._format_full(metadata)

    # ── 解析实现 ────────────────────────────────────

    async def _resolve_crossref(
        self, client: httpx.AsyncClient, doi: str
    ) -> dict[str, Any] | None:
        """CrossRef API 查询。"""
        url = f"{self.CROSSREF_BASE}/works/{doi}"
        headers = {"User-Agent": "AeroThermalExpert-Agent/1.0 (mailto:research@example.com)"}

        try:
            resp = await client.get(url, headers=headers)
            if resp.status_code == 404:
                return None
            resp.raise_for_status()
            data = resp.json()
            msg = data.get("message", {})
            if not msg:
                return None

            # 提取作者
            authors = []
            for a in msg.get("author", []):
                given = a.get("given", "")
                family = a.get("family", "")
                authors.append(f"{family}, {given}".strip(", "))

            # 期刊/会议
            journal = ""
            container = msg.get("container-title", [])
            if container:
                journal = container[0] if isinstance(container, list) else container

            # 日期
            date_parts = msg.get("published-print", {}).get("date-parts", [[]])
            if not date_parts[0]:
                date_parts = msg.get("created", {}).get("date-parts", [[]])
            year = str(date_parts[0][0]) if date_parts[0] else "?"

            return {
                "title": msg.get("title", ["无标题"])[0] if msg.get("title") else "无标题",
                "authors": authors,
                "year": year,
                "journal": journal,
                "volume": msg.get("volume", ""),
                "issue": msg.get("issue", ""),
                "pages": msg.get("page", ""),
                "publisher": msg.get("publisher", ""),
                "abstract": (msg.get("abstract", "") or "")[:800],
                "type": msg.get("type", ""),
                "cited_by": msg.get("is-referenced-by-count", 0),
                "reference_count": msg.get("references-count", 0),
            }
        except Exception:
            return None

    async def _resolve_openalex(
        self, client: httpx.AsyncClient, doi: str
    ) -> dict[str, Any] | None:
        """OpenAlex 回退查询。"""
        import urllib.parse
        encoded_doi = urllib.parse.quote(doi, safe="")
        url = f"{self.OPENALEX_BASE}/works/doi:{encoded_doi}"
        headers = {"User-Agent": "AeroThermalExpert-Agent/1.0"}

        try:
            resp = await client.get(url, headers=headers)
            if resp.status_code == 404:
                return None
            resp.raise_for_status()
            data = resp.json()

            authors = []
            for a in data.get("authorships", [])[:20]:
                authors.append(a.get("author", {}).get("display_name", "未知"))

            # 摘要重建
            abstract = ""
            inv = data.get("abstract_inverted_index", None)
            if inv:
                from tools.web_search import WebSearchTool
                abstract = WebSearchTool._reconstruct_abstract(inv)
            if len(abstract) > 800:
                abstract = abstract[:800] + "..."

            return {
                "title": data.get("title", "无标题"),
                "authors": authors,
                "year": str(data.get("publication_year", "?")),
                "journal": (
                    data.get("primary_location", {}).get("source", {}).get("display_name", "")
                    or "未知期刊"
                ),
                "volume": "",
                "issue": "",
                "pages": "",
                "publisher": "",
                "abstract": abstract,
                "type": data.get("type", ""),
                "cited_by": data.get("cited_by_count", 0),
                "reference_count": 0,
            }
        except Exception:
            return None

    # ── 格式化 ──────────────────────────────────────

    def _format_full(self, m: dict[str, Any]) -> str:
        authors = m.get("authors", [])
        author_str = ", ".join(authors[:5])
        if len(authors) > 5:
            author_str += f" et al. (共 {len(authors)} 位)"

        doi = m.get("doi", "")
        doi_link = f"https://doi.org/{doi}" if doi else ""

        lines = [
            f"## 📄 {m['title']}",
            f"",
            f"**数据源**：{m.get('source', '?')}",
            f"**作者**：{author_str}",
            f"**年份**：{m.get('year', '?')}",
        ]

        if m.get("journal"):
            vol_issue = m.get("volume", "")
            if m.get("issue"):
                vol_issue += f"({m['issue']})"
            journal_line = f"**期刊**：{m['journal']}"
            if vol_issue:
                journal_line += f", {vol_issue}"
            if m.get("pages"):
                journal_line += f", pp. {m['pages']}"
            lines.append(journal_line)

        if doi_link:
            lines.append(f"**DOI**：[{doi}]({doi_link})")

        lines.append(f"**类型**：{m.get('type', '?')}")
        lines.append(f"**被引次数**：{m.get('cited_by', 0)}")

        if m.get("abstract"):
            lines.append(f"\n**摘要**：{m['abstract']}")

        # BibTeX
        lines.append(f"\n### BibTeX\n```bibtex\n{self._build_bibtex(m)}\n```")

        return "\n".join(lines)

    def _format_compact(self, m: dict[str, Any]) -> str:
        authors = m.get("authors", [])
        first_author = authors[0] if authors else "?"
        if len(authors) > 1:
            first_author += " et al."

        doi = m.get("doi", "")
        return (
            f"**{m['title']}**\n"
            f"{first_author} ({m.get('year', '?')}). *{m.get('journal', '?')}*"
            f"{', ' + m['volume'] if m.get('volume') else ''}"
            f"{'(' + m['issue'] + ')' if m.get('issue') else ''}"
            f". DOI: {doi}"
        )

    def _format_bibtex(self, m: dict[str, Any]) -> str:
        return f"```bibtex\n{self._build_bibtex(m)}\n```"

    def _build_bibtex(self, m: dict[str, Any]) -> str:
        """生成 BibTeX 条目。"""
        # 生成 citation key
        authors = m.get("authors", [])
        first_author = "Unknown"
        last_name = "Unknown"
        if authors:
            parts = authors[0].split(",")[0].strip()
            last_name = parts.replace(" ", "").lower()
        year = m.get("year", "?")
        title_words = (m.get("title", "") or "unknown").split()[:2]
        title_key = "".join(w.capitalize()[:3] for w in title_words if w.isalpha())
        cite_key = f"{last_name}{year}{title_key}"

        # 类型
        entry_type = "article"
        if m.get("type") in ("book", "book-chapter"):
            entry_type = "inbook"
        elif m.get("type") in ("proceedings-article", "paper-conference"):
            entry_type = "inproceedings"

        lines = [f"@{entry_type}{{{cite_key},"]
        lines.append(f"  title = {{{{{m.get('title', 'Unknown')}}}}},")

        if authors:
            author_bib = " and ".join(a.replace(",", ",") for a in authors[:10])
            lines.append(f"  author = {{{{{author_bib}}}}},")

        if m.get("journal"):
            lines.append(f"  journal = {{{{{m['journal']}}}}},")
        if m.get("year") and m["year"] != "?":
            lines.append(f"  year = {{{{{m['year']}}}}},")
        if m.get("volume"):
            lines.append(f"  volume = {{{{{m['volume']}}}}},")
        if m.get("issue"):
            lines.append(f"  number = {{{{{m['issue']}}}}},")
        if m.get("pages"):
            lines.append(f"  pages = {{{{{m['pages']}}}}},")
        if m.get("doi"):
            lines.append(f"  doi = {{{{{m['doi']}}}}},")
        if m.get("publisher"):
            lines.append(f"  publisher = {{{{{m['publisher']}}}}},")

        lines.append("}")
        return "\n".join(lines)

    # ── 工具方法 ────────────────────────────────────

    @staticmethod
    def _clean_doi(doi: str) -> str:
        """清理 DOI 字符串。"""
        doi = doi.strip()
        # 去掉 URL 前缀
        for prefix in ("https://doi.org/", "http://doi.org/", "https://dx.doi.org/"):
            if doi.startswith(prefix):
                doi = doi[len(prefix):]
                break
        # 基础校验：应该含 /
        if "/" not in doi:
            return ""
        return doi

    async def close(self):
        if self._client and not self._client.is_closed:
            await self._client.aclose()
