"""
外部文献搜索工具 —— 通过 OpenAlex API 搜索全球学术文献

OpenAlex 是一个开放的学术文献索引，覆盖 2.5 亿+ 论文。
- 免费、无鉴权、REST API
- 速率限制 100k 请求/天
- 支持关键词、DOI、主题、年份等多维度检索

与 LiteratureSearchTool 的区别：
- LiteratureSearchTool：本地 3,326 篇文献库（CSV + FAISS）
- WebSearchTool：全球开放学术文献（OpenAlex API）
"""

from __future__ import annotations

from typing import Any

import httpx

from core.action import Action


class WebSearchTool(Action):
    """外部文献搜索 —— 通过 OpenAlex API 检索全球学术文献。"""

    name = "web_search"
    description = (
        "在 OpenAlex 全球学术文献索引中检索（覆盖 2.5 亿+ 论文）。"
        "适用于：查找最新研究进展、补充本地文献库未覆盖的论文、按 DOI 精确查找、验证引用。"
        "支持关键词搜索、年份/主题过滤、按引用量排序。"
    )
    parameters = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": (
                    "检索关键词（英文），支持布尔运算符 AND/OR。"
                    "例如: 'catalytic recombination coefficient SiO2' 或 'shock wave boundary layer interaction hypersonic'"
                ),
            },
            "search_type": {
                "type": "string",
                "enum": ["keyword", "doi", "title"],
                "description": "检索类型：keyword=关键词搜索, doi=按DOI精确查找, title=按标题搜索",
                "default": "keyword",
            },
            "per_page": {
                "type": "integer",
                "description": "返回结果数量，默认 5，最大 25",
                "default": 5,
            },
            "year_from": {
                "type": "integer",
                "description": "起始发表年份（含），如 2020",
            },
            "year_to": {
                "type": "integer",
                "description": "截止发表年份（含），如 2025",
            },
            "sort": {
                "type": "string",
                "enum": ["relevance_score:desc", "cited_by_count:desc", "publication_date:desc"],
                "description": "排序方式：relevance_score:desc=相关性, cited_by_count:desc=引用量, publication_date:desc=最新",
                "default": "relevance_score:desc",
            },
        },
        "required": ["query"],
    }

    BASE_URL = "https://api.openalex.org"

    def __init__(self, email: str = ""):
        self._email = email  # OpenAlex 礼貌参数，可填邮箱
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=30.0)
        return self._client

    async def run(
        self,
        query: str,
        search_type: str = "keyword",
        per_page: int = 5,
        year_from: int | None = None,
        year_to: int | None = None,
        sort: str = "relevance_score:desc",
    ) -> str:
        per_page = min(per_page, 25)

        try:
            client = await self._get_client()
        except Exception as e:
            return f"[网络错误] 无法创建 HTTP 客户端：{e}"

        # ── 构建请求 ────────────────────────────────
        if search_type == "doi":
            results = await self._lookup_by_doi(client, query)
            return self._format_results(query, results, search_type)
        elif search_type == "title":
            return await self._search_by_title(client, query, per_page)
        else:
            results = await self._search_keyword(
                client, query, per_page, year_from, year_to, sort
            )
            return self._format_results(query, results, search_type)

    # ── 检索实现 ────────────────────────────────────

    async def _search_keyword(
        self,
        client: httpx.AsyncClient,
        query: str,
        per_page: int,
        year_from: int | None = None,
        year_to: int | None = None,
        sort: str = "relevance",
    ) -> list[dict[str, Any]]:
        """OpenAlex 关键词搜索。"""
        url = f"{self.BASE_URL}/works"

        # 构建 filter
        filters = []
        if year_from:
            filters.append(f"publication_year:{year_from}")
        if year_to:
            if year_from:
                filters.insert(-1 if filters else 0, f"publication_year:{year_from}-{year_to}")
                # 重新构建
                filters = [f for f in filters if not f.startswith(f"publication_year:{year_from}") or "-" in f]
                filters = [f for f in filters if not (f.startswith(f"publication_year:{year_from}") and not "-" in f)]
        if year_from and year_to:
            filters = [f for f in filters if f == filters[-1] or not f.startswith("publication_year:")]
            filters.append(f"publication_year:{year_from}-{year_to}")
        elif year_from:
            filters.append(f"publication_year:{year_from}")
        # else: no year filter

        # 简化的过滤逻辑
        filter_str = ""
        if year_from and year_to:
            filter_str = f"publication_year:{year_from}-{year_to}"
        elif year_from:
            filter_str = f"publication_year:{year_from}"
        elif year_to:
            filter_str = f"publication_year:1900-{year_to}"

        params: dict[str, Any] = {
            "search": query,
            "per_page": per_page,
            "sort": sort,
        }
        if filter_str:
            params["filter"] = filter_str
        if self._email:
            params["mailto"] = self._email

        headers = {"User-Agent": "AeroThermalExpert-Agent/1.0"}

        try:
            resp = await client.get(url, params=params, headers=headers)
            resp.raise_for_status()
            data = resp.json()
        except httpx.HTTPError as e:
            return [{"error": f"OpenAlex API 请求失败：{e}"}]
        except Exception as e:
            return [{"error": f"解析响应失败：{e}"}]

        return self._parse_works(data.get("results", []))

    async def _lookup_by_doi(
        self, client: httpx.AsyncClient, doi: str
    ) -> list[dict[str, Any]]:
        """按 DOI 精确查找。"""
        # 清理 DOI 前缀
        clean_doi = doi.strip()
        if clean_doi.startswith("https://doi.org/"):
            clean_doi = clean_doi[16:]
        elif clean_doi.startswith("http://doi.org/"):
            clean_doi = clean_doi[15:]
        url = f"{self.BASE_URL}/works/doi:{httpx.URL('https://doi.org/' + clean_doi).path.split('/')[-1] if '/' not in clean_doi else clean_doi}"
        # 简化：直接编码 DOI
        import urllib.parse
        encoded_doi = urllib.parse.quote(clean_doi, safe="")
        url = f"{self.BASE_URL}/works/doi:{encoded_doi}"
        headers = {"User-Agent": "AeroThermalExpert-Agent/1.0"}

        try:
            resp = await client.get(url, headers=headers)
            if resp.status_code == 404:
                return [{"error": f"DOI 未找到：{doi}"}]
            resp.raise_for_status()
            data = resp.json()
            return self._parse_works([data]) if data.get("id") else [{"error": "无结果"}]
        except httpx.HTTPError as e:
            return [{"error": f"请求失败：{e}"}]

    async def _search_by_title(
        self, client: httpx.AsyncClient, title: str, per_page: int
    ) -> str:
        """按标题搜索（使用 filter 精确匹配）。"""
        url = f"{self.BASE_URL}/works"
        params: dict[str, Any] = {
            "filter": f"title.search:{title}",
            "per_page": per_page,
        }
        headers = {"User-Agent": "AeroThermalExpert-Agent/1.0"}

        try:
            resp = await client.get(url, params=params, headers=headers)
            resp.raise_for_status()
            data = resp.json()
            results = self._parse_works(data.get("results", []))
            return self._format_results(title, results, "title")
        except Exception as e:
            return f"[搜索错误] {e}"

    # ── 解析 ────────────────────────────────────────

    def _parse_works(self, works: list[dict]) -> list[dict[str, Any]]:
        """将 OpenAlex work 对象解析为统一格式。"""
        parsed = []
        for w in works:
            if "error" in w:
                parsed.append(w)
                continue

            # 提取作者（前 5 位）
            authorships = w.get("authorships", [])
            authors = [
                a.get("author", {}).get("display_name", "未知")
                for a in authorships[:5]
            ]

            # 提取期刊/会议名
            primary_loc = w.get("primary_location", {}) or {}
            source = primary_loc.get("source", {}) or {}
            journal = source.get("display_name", "")

            # 摘要（OpenAlex 提供 inverted abstract → 重组为纯文本）
            abstract = ""
            abstract_inverted = w.get("abstract_inverted_index", None)
            if abstract_inverted:
                abstract = self._reconstruct_abstract(abstract_inverted)
            # 截取前 500 字符
            if len(abstract) > 500:
                abstract = abstract[:500] + "..."

            doi = w.get("doi", "")
            doi_clean = doi.replace("https://doi.org/", "") if doi else ""

            parsed.append({
                "title": w.get("title", "无标题"),
                "authors": authors,
                "year": str(w.get("publication_year", "?")),
                "journal": journal or "未知期刊",
                "doi": doi_clean,
                "cited_by": w.get("cited_by_count", 0),
                "type": w.get("type", "unknown"),
                "abstract": abstract,
                "openalex_url": w.get("id", ""),
                "is_open_access": w.get("open_access", {}).get("is_oa", False),
            })
        return parsed

    @staticmethod
    def _reconstruct_abstract(inverted: dict) -> str:
        """将 OpenAlex 的倒排索引摘要重建为纯文本。"""
        if not inverted:
            return ""
        # 构建 {position: word} 映射
        positions: dict[int, str] = {}
        for word, pos_list in inverted.items():
            for pos in pos_list:
                positions[pos] = word
        # 按位置排序拼接
        return " ".join(positions[i] for i in sorted(positions))

    # ── 格式化 ──────────────────────────────────────

    def _format_results(
        self, query: str, results: list[dict[str, Any]], search_type: str
    ) -> str:
        """格式化检索结果为 Markdown。"""
        if not results:
            return f"🔍 未找到与 '{query}' 相关的外部文献。"

        if len(results) == 1 and "error" in results[0]:
            return f"❌ 检索失败：{results[0]['error']}"

        lines = [
            f"## 🔍 外部文献检索：'{query}'",
            f"**数据源**：OpenAlex | **结果数**：{len(results)} 篇\n",
        ]

        for i, r in enumerate(results, 1):
            if "error" in r:
                continue

            authors = ", ".join(r.get("authors", [])[:3])
            if len(r.get("authors", [])) > 3:
                authors += " et al."

            doi = r.get("doi", "")
            doi_link = f"https://doi.org/{doi}" if doi else ""

            lines.append(f"### {i}. {r['title']}")
            lines.append(f"- **作者**：{authors}")
            lines.append(f"- **期刊**：{r.get('journal', '?')} ({r.get('year', '?')})")
            if doi_link:
                lines.append(f"- **DOI**：[{doi}]({doi_link})")
            lines.append(f"- **引用数**：{r.get('cited_by', 0)}")
            if r.get("is_open_access"):
                lines.append(f"- **OA**：✅ 开放获取")
            if r.get("abstract"):
                lines.append(f"- **摘要**：{r['abstract']}")
            lines.append("")

        return "\n".join(lines)

    async def close(self):
        if self._client and not self._client.is_closed:
            await self._client.aclose()
