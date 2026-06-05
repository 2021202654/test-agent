# 气固热导 AI Agent — 系统总览

> 基于微调 LLM 的气动热物理研究 Agent，面向高超声速气固界面耦合领域的文献分析、知识推理与辅助研究。

---

## 定位

**LLM** = 专家的大脑（微调领域知识 + RAG 检索增强）
**Agent** = 专家的手和眼（工具调用 + 多步推理 + 记忆管理 + 自主行动）

LLM 回答"是什么"，Agent 回答"怎么做"——找到最优检索策略、组合多源证据、批判性验证结论。

---

## 架构草图

```
用户输入
  ↓
编排引擎（ReAct / Plan-Execute）
  ├── 工具链（9 个：文献检索、数值计算、论文解析、格式导出）
  ├── 记忆系统（对话历史、研究上下文、RAG 桥接）
  └── LLM 推理核（微调专家模型 + RAG + System Prompt）
  ↓
多步推理 → 证据链合成 → 批判性验证 → 输出
```

---

## 子目录

| 目录 | 用途 | 关键产出 |
|------|------|----------|
| `01_架构设计/` | Agent 总架构、LLM-Agent 接口、系统边界 | 架构方案文档 |
| `02_工具链/` | 工具定义（检索/计算/解析）、Function Schema | 工具注册表 |
| `03_编排引擎/` | 推理路由、ReAct 循环、Plan-Execute 状态机 | 编排逻辑 |
| `04_记忆系统/` | 短期对话记忆、长期研究上下文、知识缓存 | 记忆管理 |
| `05_评测基准/` | 任务完成率、工具调用精度、幻觉检测 | 评测框架 |
| `06_部署集成/` | API 服务、Gradio UI、前端接入 | 部署方案 |

---

## 与 LLM 线的协作

```
03_知识工程/        ← Agent 和 LLM 共享的数据底座
├── 文献库          ← Agent 检索工具的索引源
├── QA 数据集       ← LLM 微调的训练数据
├── 向量索引        ← RAG 检索的核心组件
└── 知识图谱        ← Agent 结构化推理的基础层（规划中）

04_LLM微调线/       ← Agent 的推理内核
└── LoRA 权重       ← Agent 调用的专家模型
```

---

## 当前状态

**Phase 1：原型开发阶段**（2026-06-01 启动）

- [x] Agent 框架选型 → 自研轻量框架（仿 MetaGPT Role-Action-Memory）
- [x] 核心框架实现 → `core/`（Role + Action + Memory + Orchestrator + LLM Interface）
- [x] 内置工具集 → `tools/`（9 个工具）
- [x] 百炼 API 跑通 Agent 全流程 → 首份技术报告已生成
- [x] Gradio Web UI → `app.py`
- [x] DSW 部署 notebook → 4 个新 notebook（环境/下载/训练/部署）
- [ ] FAISS 语义检索激活（需配置 embedding 模型）
- [ ] 微调模型端到端验证（待 DSW 训练完成）
- [ ] Agent 评测基准（`05_评测基准/`）

---

## 工具链（9 个）

| # | 工具 | 文件 | 功能 |
|---|------|------|------|
| 1 | LiteratureSearchTool | `search.py` | 本地 CSV 关键词 + FAISS 语义检索（3,326 篇） |
| 2 | WebSearchTool | `web_search.py` | OpenAlex API 全球学术文献搜索（2.5 亿+ 论文） |
| 3 | AeroThermalComputeTool | `compute.py` | 驻点热流 / Knudsen / 催化系数 / 单位换算 / 边界层 |
| 4 | CodeExecutionTool | `code_exec.py` | Python 子进程沙箱执行（30s 超时，支持 pip install） |
| 5 | CitationResolverTool | `citation.py` | CrossRef / OpenAlex DOI 解析 + BibTeX 生成 |
| 6 | PDFAnalysisTool | `pdf_parser.py` | PyMuPDF 论文解析（元数据/全文/章节/参数识别/搜索） |
| 7 | ReportTool | `report.py` | 结构化 Markdown 研究报告生成 |
| 8 | ExportFindingTool | `report.py` | 单条研究发现追加记录 |
| 9 | PandocExportTool | `pandoc_export.py` | Markdown → LaTeX / DOCX / PDF（XeLaTeX + CJK） |

---

## 框架速览

```
core/
├── message.py      # 消息体（user/agent/system/tool）
├── llm.py          # OpenAI 兼容 API 接口（vLLM / 百炼 / Ollama）
├── action.py       # 工具基类 + 注册表
├── memory.py       # 短期 + 工作 + 长期记忆
├── role.py         # Agent 身份/目标/约束
├── orchestrator.py # ReAct + Plan-Execute 循环
└── agent.py        # 顶层入口，组装一切

tools/
├── search.py       # 文献检索（FAISS + CSV）
├── web_search.py   # OpenAlex 外部文献搜索
├── compute.py      # 气动热参数计算
├── code_exec.py    # Python 代码沙箱执行
├── citation.py     # DOI 引文解析
├── pdf_parser.py   # PDF 论文解析
├── report.py       # 报告生成 + 发现记录
└── pandoc_export.py # 格式导出（LaTeX/DOCX/PDF）

config.py           # 统一配置（4 套 LLM 预设）
run_agent.py        # CLI 入口
app.py              # Gradio Web UI 入口
```

---

## 快速开始

### CLI 模式

```bash
cd 05_AI_Agent

# 交互模式（百炼 API，即开即用）
python run_agent.py --llm bailian

# 单次任务
python run_agent.py --llm bailian --task "计算马赫数15下的驻点热流密度"

# Plan-Execute 模式
python run_agent.py --llm bailian --mode plan_execute --task "评估气固界面催化模型跨尺度适用性"

# 自定义 LLM 端点（vLLM / Ollama 等）
python run_agent.py --llm custom --base-url http://localhost:8000/v1
```

### Gradio Web UI

```bash
# 百炼 API
python app.py --llm bailian

# vLLM 本地
python app.py --llm vllm_local

# DSW 部署（自动获取公网链接）
python app.py --llm custom --port 7860
```

### DSW 部署

按 `04_LLM微调线/04_推理部署/` 下 4 个 notebook 顺序执行：

1. `0_DSW环境部署.ipynb` — 环境一键配齐
2. `1_模型下载与数据注册.ipynb` — 下载基座 + 注册数据集
3. `2_训练与导出.ipynb` — QLoRA 微调 + 合并导出
4. `3_推理与Agent部署.ipynb` — vLLM + Agent Gradio 上线
