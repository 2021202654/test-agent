# 气固热导 AI Agent — 系统总览

> 高超声速气固界面耦合 **AI Scientist** —— 从被动问答到自主科研
> 基于 LLM + 10 工具 Agent + 物理约束验证，支持假设生成、实验设计、论文生成闭环

---

## 定位

```
问答专家（v1）                AI Scientist（v2）🆕
     ↓                              ↓
回答"是什么"                    解决"为什么 + 还能怎样"
检索 + 推理 → 报告              假设生成 → 实验验证 → 论文 → 评审
     9 工具                          10 工具（+ HypothesisGenerator）
```

**LLM** = 专家的大脑（微调领域知识 + RAG + 硅基流动/百炼 API）
**Agent** = 科学家的手和眼（工具调用 + 多步推理 + 假设生成 + 物理约束验证）

---

## 架构草图

```
用户输入
  ↓
编排引擎（ReAct / Plan-Execute）
  ├── 工具链（10 个：文献检索、数值计算、论文解析、格式导出、**假设生成**）
  ├── 记忆系统（对话历史、研究上下文、RAG 桥接）
  ├── 物理约束层（PhysicsConstraintLayer：参数边界/流态/守恒律验证）
  └── LLM 推理核（微调专家模型 + RAG + System Prompt）
  ↓
多步推理 → 证据链合成 → 假设生成 → 批判性验证 → 输出
```

---

## 子目录

| 目录 | 用途 | 关键产出 |
|------|------|----------|
| `01_架构设计/` | Agent 总架构 + 🆕 **AI Scientist 5 模块设计** | 架构方案 + AI Scientist 文档 |
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

**Phase 2：AI Scientist 跃迁**（2026-06-09 启动）

- [x] Agent 框架选型 → 自研轻量框架（仿 MetaGPT Role-Action-Memory）
- [x] 核心框架实现 → `core/`（Role + Action + Memory + Orchestrator + LLM Interface）
- [x] 内置工具集 → `tools/`（**10 个工具**）
- [x] 百炼 API 跑通 Agent 全流程 → 首份技术报告已生成
- [x] Gradio Web UI → `app.py`
- [x] DSW 部署 notebook → 4 个新 notebook（环境/下载/训练/部署）
- [x] **HypothesisGenerator** → `tools/hypothesis.py`（AI Scientist 核心，LLM 注入架构）
- [x] **PhysicsConstraintLayer** → `tools/physics_constraints.py`（物理约束验证）
- [x] **AI Scientist 5 模块设计文档** → `01_架构设计/AI_Scientist_模块设计/`
- [x] **硅基流动 API 预设** → `--llm siliconflow`（DeepSeek-V3，1+2 ¥/M）
- [ ] FAISS 语义检索激活（需配置 embedding 模型）
- [ ] 微调模型端到端验证（待 DSW 训练完成）
- [ ] Agent 评测基准（`05_评测基准/`）
- [ ] ExperimentDesigner / ResultAnalyzer / PaperWriter / AutoReviewer 实现

### 最近更新（2026-06-11）

**安全审计修复**：
- `core/orchestrator.py`：JSON 解析异常保护（try/except）；新增 `_BoundedCache` LRU 有界缓存（max=100），替换无限 dict 缓存
- `tools/code_exec.py`：pip install 参数注入防御（包名白名单正则 + 禁止 `--index-url` 等危险 flag）
- `.env`：百炼 API Key 已轮换

**System Prompt 幻觉防御强化**：
- `core/role.py`：新增规则 3（参数溯源强制）、规则 8（工具警告传递）、规则 11（公式名称与工具返回完全一致）、规则 12（补充数据标注来源）
- `tools/search.py`：DOI 过滤，无 DOI 文献不传递给 LLM

**端到端验证**：
- Apollo 驻点热流 ReAct 测试通过（3.89 MW/m²，工具链完整：stagnation_heat_flux → knudsen_number → export_finding → generate_report）

---

## 工具链（10 个）

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
| 10 | 🆕 **HypothesisGenerator** | `hypothesis.py` | LLM 注入架构：文献检索→Gap 识别→假设生成→物理约束验证→评分排序 |

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
├── pandoc_export.py # 格式导出（LaTeX/DOCX/PDF）
├── hypothesis.py   # 🆕 AI Scientist：假设生成器（LLM 注入）
└── physics_constraints.py # 🆕 物理约束验证层

config.py           # 统一配置（5 套 LLM 预设：bailian/siliconflow/vllm_local/ollama/custom）
run_agent.py        # CLI 入口（--llm siliconflow 🆕）
app.py              # Gradio Web UI 入口
```

---

## 快速开始

### CLI 模式

```bash
cd 05_AI_Agent

# 交互模式（百炼 API，即开即用）
python run_agent.py --llm bailian

# 硅基流动（性价比最高，DeepSeek-V3）
python run_agent.py --llm siliconflow

# 单次任务
python run_agent.py --llm bailian --task "计算马赫数15下的驻点热流密度"

# Plan-Execute 模式
python run_agent.py --llm bailian --mode plan_execute --task "评估气固界面催化模型跨尺度适用性"

# AI Scientist：假设生成
python run_agent.py --llm bailian --verbose --task "分析气固界面催化系数建模的研究Gap，生成3个可验证假设"

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
