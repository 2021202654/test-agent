"""
内置工具集 —— Agent 开箱即用的领域工具

- LiteratureSearchTool    : FAISS 语义检索 + CSV 关键词检索（本地 3,326 篇文献库）
- WebSearchTool            : OpenAlex API 外部文献搜索（全球 2.5 亿+ 论文）
- AeroThermalComputeTool   : 气动热参数计算（驻点热流 / Knudsen / 催化 / 边界层）
- CodeExecutionTool        : Python 子进程沙箱执行（计算+作图+验证）
- CitationResolverTool     : CrossRef/OpenAlex DOI 解析 + BibTeX 生成
- PDFAnalysisTool          : PDF 论文解析（文本/元数据/章节/参数识别）
- ReportTool               : 结构化 Markdown 研究报告生成
- ExportFindingTool        : 单条研究发现记录
- PandocExportTool         : Markdown → LaTeX/DOCX/PDF 格式导出
"""

from .search import LiteratureSearchTool
from .compute import AeroThermalComputeTool
from .web_search import WebSearchTool
from .code_exec import CodeExecutionTool
from .citation import CitationResolverTool
from .pdf_parser import PDFAnalysisTool
from .report import ReportTool, ExportFindingTool
from .pandoc_export import PandocExportTool

__all__ = [
    "LiteratureSearchTool",
    "WebSearchTool",
    "AeroThermalComputeTool",
    "CodeExecutionTool",
    "CitationResolverTool",
    "PDFAnalysisTool",
    "ReportTool",
    "ExportFindingTool",
    "PandocExportTool",
]
