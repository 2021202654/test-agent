"""
文献检索工具 —— Agent 最核心的能力

支持两种检索路径：
1. 向量语义检索（FAISS）：语义相关但关键词不一定匹配
2. CSV 标题关键词检索：精确匹配标题中的术语（FAISS 不可用时的回退）
"""

from __future__ import annotations

import csv
import pickle
from pathlib import Path
from typing import Any

import numpy as np

from core.action import Action


class LiteratureSearchTool(Action):
    """文献检索工具 —— 在气固热导 3,326 篇文献库中检索。"""

    name = "search_literature"
    description = (
        "在气固热导领域文献库中检索（共3,326篇，覆盖气动热力学、催化复合、"
        "激波边界层干扰、非平衡流动、热防护等方向）。"
        "输入检索关键词（英文），返回最相关的文献标题、年份、期刊和DOI。"
    )
    parameters = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "检索关键词或短语，英文。例如: 'catalytic recombination coefficient SiO2'",
            },
            "top_k": {
                "type": "integer",
                "description": "返回文献数量，默认5，最多20",
                "default": 5,
            },
        },
        "required": ["query"],
    }

    def __init__(
        self,
        faiss_index_dir: str | Path | None = None,
        csv_path: str | Path | None = None,
    ):
        self._index_dir = Path(faiss_index_dir) if faiss_index_dir else None
        self._csv_path = Path(csv_path) if csv_path else None
        self._index = None
        self._metadata = None
        self._csv_rows: list[dict[str, str]] = []

    # ── 路径解析 ────────────────────────────────────

    @property
    def index_dir(self) -> Path:
        if self._index_dir:
            return self._index_dir
        project = Path(__file__).parent.parent.parent
        return project / "03_知识工程" / "05_向量索引" / "faiss_index"

    @property
    def csv_path(self) -> Path:
        if self._csv_path:
            return self._csv_path
        project = Path(__file__).parent.parent.parent
        return project / "03_知识工程" / "03_文献库" / "Final_Merged_Literature.csv"

    # ── 延迟加载 ────────────────────────────────────

    def _ensure_index_loaded(self):
        if self._index is not None:
            return
        faiss_file = self.index_dir / "index.faiss"
        pkl_file = self.index_dir / "index.pkl"
        if faiss_file.exists() and pkl_file.exists():
            try:
                import faiss
                self._index = faiss.read_index(str(faiss_file))
                with open(pkl_file, "rb") as f:
                    self._metadata = pickle.load(f)
            except Exception:
                pass  # 静默回退到 CSV 检索

    def _ensure_csv_loaded(self):
        if self._csv_rows:
            return
        csv_file = self.csv_path
        if not csv_file.exists():
            return
        # 自动检测编码：UTF-8 → Latin-1 → GBK 依次尝试
        for encoding in ("utf-8", "latin-1", "gbk"):
            try:
                with open(csv_file, "r", encoding=encoding) as f:
                    reader = csv.DictReader(f)
                    self._csv_rows = list(reader)
                break  # 加载成功，退出编码尝试
            except (UnicodeDecodeError, UnicodeError):
                continue

    # ── 检索入口 ────────────────────────────────────

    async def run(self, query: str, top_k: int = 5) -> str:
        top_k = min(top_k, 20)
        results: list[dict[str, Any]] = []
        seen_titles: set[str] = set()

        # Path 1: FAISS 语义检索
        try:
            self._ensure_index_loaded()
            if self._index is not None:
                faiss_results = self._faiss_search(query, top_k)
                for r in faiss_results:
                    if r.get("title", "") not in seen_titles:
                        results.append(r)
                        seen_titles.add(r.get("title", ""))
        except Exception as e:
            pass  # 静默回退

        # Path 2: CSV 关键词检索（补充/回退）
        try:
            self._ensure_csv_loaded()
            if self._csv_rows and len(results) < top_k:
                csv_results = self._csv_keyword_search(query, top_k - len(results))
                for r in csv_results:
                    if r.get("title", "") not in seen_titles:
                        results.append(r)
                        seen_titles.add(r.get("title", ""))
        except Exception:
            pass

        if not results:
            return f"未找到与 '{query}' 相关的文献。建议尝试更广泛的关键词，或检查文献库路径配置。"

        return self._format_results(query, results[:top_k])

    # ── 检索实现 ────────────────────────────────────

    def _faiss_search(self, query: str, top_k: int) -> list[dict[str, Any]]:
        """FAISS 语义检索。需要配置 embedding 模型才能激活。"""
        # 实际部署时取消注释以下代码：
        # import openai
        # client = openai.OpenAI(base_url="...", api_key="...")
        # q_vec = client.embeddings.create(model="text-embedding-3-small", input=query)
        # vec = np.array([q_vec.data[0].embedding], dtype=np.float32)
        # D, I = self._index.search(vec, top_k)
        # results = []
        # for i, idx in enumerate(I[0]):
        #     if idx >= 0 and self._metadata:
        #         meta = self._metadata[idx]
        #         results.append({
        #             "title": meta.get("title", ""),
        #             "year": str(meta.get("year", "?")),
        #             "journal": meta.get("journal", ""),
        #             "doi": meta.get("doi", ""),
        #             "score": f"语义相似度 {1-D[0][i]:.2f}",
        #         })
        # return results
        return []  # 当前回退到 CSV 检索

    def _csv_keyword_search(self, query: str, top_k: int) -> list[dict[str, Any]]:
        """CSV 标题+摘要关键词匹配。"""
        keywords = query.lower().split()
        scored: list[tuple[int, dict[str, str]]] = []

        for row in self._csv_rows:
            title = row.get("Title", "")
            journal = row.get("Journal", "")
            text = (title + " " + journal).lower()
            score = sum(1 for kw in keywords if kw in text)
            if score > 0:
                scored.append((score, row))

        scored.sort(key=lambda x: x[0], reverse=True)

        return [
            {
                "title": row.get("Title", "无标题").strip('"'),
                "year": row.get("Year", "?"),
                "journal": row.get("Journal", "未知期刊").strip('"'),
                "doi": row.get("DOI", ""),
                "score": f"关键词命中 {score}/{len(keywords)}",
            }
            for score, row in scored[:top_k]
        ]

    def _format_results(self, query: str, results: list[dict[str, Any]]) -> str:
        lines = [f"🔍 检索 '{query}' 返回 {len(results)} 篇文献：\n"]
        for i, r in enumerate(results, 1):
            doi = r.get("doi", "")
            doi_link = f"https://doi.org/{doi}" if doi else "无DOI"
            lines.append(
                f"{i}. **{r['title']}**\n"
                f"   {r.get('journal', '?')} ({r.get('year', '?')})\n"
                f"   DOI: {doi_link}\n"
                f"   {r.get('score', '')}\n"
            )
        return "\n".join(lines)
