# 02 工具链

## 状态：✅ 核心工具已实现

### 已实现

| 工具 | 文件 | 功能 |
|------|------|------|
| `LiteratureSearchTool` | `../tools/search.py` | FAISS 语义检索 + CSV 关键词检索（3,326篇文献库） |
| `AeroThermalComputeTool` | `../tools/compute.py` | 驻点热流、Kn数、催化系数、单位换算、边界层厚度 |

### 待实现

| 工具 | 说明 |
|------|------|
| `PaperAnalysisTool` | PDF 全文解析 -> 关键参数提取（Phase 2） |
| `KnowledgeGraphQueryTool` | 知识图谱查询（Phase 3） |
| `WebSearchTool` | arXiv / Google Scholar 外部搜索 |
| `CodeExecutionTool` | Python 沙箱执行（作图+计算） |

### 工具定义规范

所有工具继承 `core.action.Action`，实现 `run()` 方法。自动导出 OpenAI function-calling JSON Schema。

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
