# 02 工具链

## 状态：✅ 10 个工具全部实现

### 基础工具（9 个）

| # | 工具 | 文件 | 功能 |
|---|------|------|------|
| 1 | `LiteratureSearchTool` | `../tools/search.py` | CSV 关键词 + FAISS 语义检索（3,326 篇）；**无 DOI 结果自动过滤** |
| 2 | `WebSearchTool` | `../tools/web_search.py` | OpenAlex API 全球学术文献搜索（2.5 亿+ 论文） |
| 3 | `AeroThermalComputeTool` | `../tools/compute.py` | 驻点热流 / Knudsen / 催化系数 / 单位换算 / 边界层厚度 |
| 4 | `CodeExecutionTool` | `../tools/code_exec.py` | Python 子进程沙箱（180s 超时，pip install 带安全过滤） |
| 5 | `CitationResolverTool` | `../tools/citation.py` | CrossRef / OpenAlex DOI 解析 + BibTeX 生成 |
| 6 | `PDFAnalysisTool` | `../tools/pdf_parser.py` | PyMuPDF 论文解析（元数据/全文/章节/参数/搜索） |
| 7 | `ReportTool` | `../tools/report.py` | 结构化 Markdown 研究报告生成 |
| 8 | `ExportFindingTool` | `../tools/report.py` | 单条研究发现追加记录 |
| 9 | `PandocExportTool` | `../tools/pandoc_export.py` | Markdown → LaTeX / DOCX / PDF（XeLaTeX + CJK） |

### AI Scientist 工具（1 个）🆕

| # | 工具 | 文件 | 功能 |
|---|------|------|------|
| 10 | `HypothesisGenerator` | `../tools/hypothesis.py` | LLM 注入架构：文献检索→4级Gap识别→假设生成→物理约束验证→评分排序 |
| — | `PhysicsConstraintLayer` | `../tools/physics_constraints.py` | 纯规则层：参数边界/流态一致性/守恒律/模型适用性验证 |

### 工具定义规范

**标准工具**：继承 `core.action.Action`，实现 `async run()` 方法。

**LLM 注入工具**：`HypothesisGenerator` 是首个需要 LLM 实例的工具（用于假设生成的二次推理），通过构造器注入 `LLMInterface`：

```python
agent.equip(HypothesisGenerator(
    llm=agent.llm,
    search_tool=search,
    web_tool=web,
))
```

所有工具自动导出 OpenAI function-calling JSON Schema。定义规范：

```python
from core.action import Action

class MyTool(Action):
    name = "my_tool"
    description = "工具描述"
    parameters = {
        "type": "object",
        "properties": {...},
        "required": [...],
    }

    async def run(self, **kwargs) -> str:
        return "result"
```
