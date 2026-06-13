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

**自省迭代升级**（2026-06-12）：
- `core/orchestrator.py`：新增 `critique_rounds` 参数（默认 2 轮），ReAct 主循环结束后进入 LLM 自审迭代，识别初版答案弱点并修订
- `config.py` / `app.py` / `run_agent.py`：`--critique-rounds` CLI 参数，可配置自省轮数（设为 0 禁用）
- `core/role.py`：强化 System Prompt，确保自省过程遵循身份约束

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

# 自省迭代（默认 2 轮）+ 最大步数上限（默认 15）
python run_agent.py --llm bailian --critique-rounds 2 --max-react-steps 20 -t "对比 SiO₂、SiC、RCG 在 1500K–3000K 的催化复合系数"

# Policy Routing + 自动降级（需用户确认）
python run_agent.py --llm bailian --auto-route -t "分析气固界面催化系数建模的 Gap 并生成假设"

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

# 自省迭代 + 最大步数 + Policy Routing
python app.py --llm bailian --critique-rounds 2 --max-react-steps 20 --auto-route
```

### DSW 部署

按 `04_LLM微调线/04_推理部署/` 下 4 个 notebook 顺序执行：

1. `0_DSW环境部署.ipynb` — 环境一键配齐
2. `1_模型下载与数据注册.ipynb` — 下载基座 + 注册数据集
3. `2_训练与导出.ipynb` — QLoRA 微调 + 合并导出
4. `3_推理与Agent部署.ipynb` — vLLM + Agent Gradio 上线

---

# Hypersonic Gas-Solid Thermal Coupling AI Agent — System Overview

> **AI Scientist** for Hypersonic Gas-Solid Interface Coupling — From Passive Q&A to Autonomous Research
> Built on LLM + 10-tool Agent + Physics Constraint Verification; supports closed-loop hypothesis generation, experimental design, and paper generation

---

## Positioning

```
Q&A Expert (v1)                  AI Scientist (v2) 🆕
     ↓                              ↓
Answer "what is it"              Solve "why + what else"
Retrieval + Reasoning → Report   Hypothesis → Experiment → Paper → Review
     9 tools                        10 tools (+ HypothesisGenerator)
```

**LLM** = The expert's brain (fine-tuned domain knowledge + RAG + SiliconFlow/Bailian API)
**Agent** = The scientist's hands and eyes (tool calling + multi-step reasoning + hypothesis generation + physics constraint verification)

---

## Architecture Sketch

```
User Input
  ↓
Orchestration Engine (ReAct / Plan-Execute)
  ├── Toolchain (10 tools: literature search, numerical computation, paper parsing, format export, **hypothesis generation**)
  ├── Memory System (conversation history, research context, RAG bridging)
  ├── Physics Constraint Layer (PhysicsConstraintLayer: parameter bounds / flow regime / conservation law verification)
  └── LLM Reasoning Core (fine-tuned expert model + RAG + System Prompt)
  ↓
Multi-step Reasoning → Evidence Chain Synthesis → Hypothesis Generation → Critical Verification → Output
```

---

## Subdirectories

| Directory | Purpose | Key Outputs |
|------|------|----------|
| `01_架构设计/` | Agent overall architecture + 🆕 **AI Scientist 5-module design** | Architecture plan + AI Scientist documentation |
| `02_工具链/` | Tool definitions (search/compute/parse), Function Schema | Tool registry |
| `03_编排引擎/` | Reasoning routing, ReAct loop, Plan-Execute state machine | Orchestration logic |
| `04_记忆系统/` | Short-term conversation memory, long-term research context, knowledge cache | Memory management |
| `05_评测基准/` | Task completion rate, tool call accuracy, hallucination detection | Evaluation framework |
| `06_部署集成/` | API service, Gradio UI, frontend integration | Deployment plan |

---

## Collaboration with the LLM Pipeline

```
03_知识工程/        ← Shared data foundation for Agent and LLM
├── 文献库          ← Index source for Agent retrieval tools
├── QA 数据集       ← Training data for LLM fine-tuning
├── 向量索引        ← Core component for RAG retrieval
└── 知识图谱        ← Foundation layer for Agent structured reasoning (planned)

04_LLM微调线/       ← Agent's reasoning core
└── LoRA 权重       ← Expert model called by Agent
```

---

## Current Status

**Phase 2: AI Scientist Leap** (started 2026-06-09)

- [x] Agent framework selection → Custom lightweight framework (modeled after MetaGPT Role-Action-Memory)
- [x] Core framework implementation → `core/` (Role + Action + Memory + Orchestrator + LLM Interface)
- [x] Built-in toolset → `tools/` (**10 tools**)
- [x] Bailian API running full Agent workflow → First technical report generated
- [x] Gradio Web UI → `app.py`
- [x] DSW deployment notebooks → 4 new notebooks (environment/download/training/deployment)
- [x] **HypothesisGenerator** → `tools/hypothesis.py` (AI Scientist core, LLM injection architecture)
- [x] **PhysicsConstraintLayer** → `tools/physics_constraints.py` (physics constraint verification)
- [x] **AI Scientist 5-module design document** → `01_架构设计/AI_Scientist_模块设计/`
- [x] **SiliconFlow API preset** → `--llm siliconflow` (DeepSeek-V3, 1+2 ¥/M)
- [ ] FAISS semantic retrieval activation (requires embedding model configuration)
- [ ] End-to-end fine-tuned model validation (pending DSW training completion)
- [ ] Agent evaluation benchmark (`05_评测基准/`)
- [ ] ExperimentDesigner / ResultAnalyzer / PaperWriter / AutoReviewer implementation

### Recent Updates (2026-06-11)

**Security Audit Fixes**:
- `core/orchestrator.py`: JSON parsing exception protection (try/except); new `_BoundedCache` LRU bounded cache (max=100), replacing unlimited dict cache
- `tools/code_exec.py`: pip install parameter injection defense (package name whitelist regex + prohibited `--index-url` and other dangerous flags)
- `.env`: Bailian API Key rotated

**System Prompt Hallucination Defense Strengthening**:
- `core/role.py`: Added Rule 3 (mandatory parameter traceability), Rule 8 (tool warning propagation), Rule 11 (formula names must exactly match tool returns), Rule 12 (supplementary data source annotation)
- `tools/search.py`: DOI filtering, literature without DOI not passed to LLM

**End-to-End Validation**:
- Apollo stagnation point heat flux ReAct test passed (3.89 MW/m², complete toolchain: stagnation_heat_flux → knudsen_number → export_finding → generate_report)

**Self-Critique Iteration Upgrade** (2026-06-12):
- `core/orchestrator.py`: Added `critique_rounds` parameter (default 2 rounds); after main ReAct loop, LLM enters self-review iteration to identify weaknesses in the initial draft and revise
- `config.py` / `app.py` / `run_agent.py`: `--critique-rounds` CLI flag, configurable number of self-critique rounds (set to 0 to disable)
- `core/role.py`: System Prompt reinforcement to ensure self-critique process follows identity constraints

---

## Toolchain (10 Tools)

| # | Tool | File | Function |
|---|------|------|------|
| 1 | LiteratureSearchTool | `search.py` | Local CSV keyword + FAISS semantic search (3,326 papers) |
| 2 | WebSearchTool | `web_search.py` | OpenAlex API global academic literature search (2.5 billion+ papers) |
| 3 | AeroThermalComputeTool | `compute.py` | Stagnation heat flux / Knudsen / catalytic coefficient / unit conversion / boundary layer |
| 4 | CodeExecutionTool | `code_exec.py` | Python subprocess sandbox execution (30s timeout, supports pip install) |
| 5 | CitationResolverTool | `citation.py` | CrossRef / OpenAlex DOI resolution + BibTeX generation |
| 6 | PDFAnalysisTool | `pdf_parser.py` | PyMuPDF paper parsing (metadata/full-text/sections/parameter recognition/search) |
| 7 | ReportTool | `report.py` | Structured Markdown research report generation |
| 8 | ExportFindingTool | `report.py` | Single research finding append recording |
| 9 | PandocExportTool | `pandoc_export.py` | Markdown → LaTeX / DOCX / PDF (XeLaTeX + CJK) |
| 10 | 🆕 **HypothesisGenerator** | `hypothesis.py` | LLM injection architecture: literature retrieval → Gap identification → Hypothesis generation → Physics constraint verification → Scoring & ranking |

---

## Framework Overview

```
core/
├── message.py      # Message body (user/agent/system/tool)
├── llm.py          # OpenAI-compatible API interface (vLLM / Bailian / Ollama)
├── action.py       # Tool base class + registry
├── memory.py       # Short-term + working + long-term memory
├── role.py         # Agent identity / goals / constraints
├── orchestrator.py # ReAct + Plan-Execute loop
└── agent.py        # Top-level entry, assembles everything

tools/
├── search.py       # Literature search (FAISS + CSV)
├── web_search.py   # OpenAlex external literature search
├── compute.py      # Aerothermal parameter computation
├── code_exec.py    # Python code sandbox execution
├── citation.py     # DOI citation resolution
├── pdf_parser.py   # PDF paper parsing
├── report.py       # Report generation + finding records
├── pandoc_export.py # Format export (LaTeX/DOCX/PDF)
├── hypothesis.py   # 🆕 AI Scientist: hypothesis generator (LLM injection)
└── physics_constraints.py # 🆕 Physics constraint verification layer

config.py           # Unified configuration (5 LLM presets: bailian/siliconflow/vllm_local/ollama/custom)
run_agent.py        # CLI entry point (--llm siliconflow 🆕)
app.py              # Gradio Web UI entry
```

---

## Quick Start

### CLI Mode

```bash
cd 05_AI_Agent

# Interactive mode (Bailian API, ready to use)
python run_agent.py --llm bailian

# SiliconFlow (best cost-performance, DeepSeek-V3)
python run_agent.py --llm siliconflow

# Single task
python run_agent.py --llm bailian --task "Calculate stagnation-point heat flux at Mach 15"

# Plan-Execute mode
python run_agent.py --llm bailian --mode plan_execute --task "Evaluate cross-scale applicability of gas-solid interface catalytic model"

# Self-critique iteration (default 2 rounds) + max steps cap (default 15)
python run_agent.py --llm bailian --critique-rounds 2 --max-react-steps 20 -t "Compare catalytic recombination coefficients of SiO2, SiC, RCG at 1500K–3000K"

# Policy Routing + auto-fallback (requires user confirmation)
python run_agent.py --llm bailian --auto-route -t "Identify research gaps in catalytic coefficient modeling and generate hypotheses"

# Custom LLM endpoint (vLLM / Ollama etc.)
python run_agent.py --llm custom --base-url http://localhost:8000/v1
```

### Gradio Web UI

```bash
# Bailian API
python app.py --llm bailian

# vLLM local
python app.py --llm vllm_local

# DSW deployment (auto-fetch public URL)
python app.py --llm custom --port 7860

# With self-critique + max steps + auto-route
python app.py --llm bailian --critique-rounds 2 --max-react-steps 20 --auto-route
```

### DSW Deployment

Execute the 4 notebooks under `04_LLM微调线/04_推理部署/` in order:

1. `0_DSW环境部署.ipynb` — One-click environment setup
2. `1_模型下载与数据注册.ipynb` — Download base model + register dataset
3. `2_训练与导出.ipynb` — QLoRA fine-tuning + merge and export
4. `3_推理与Agent部署.ipynb` — vLLM + Agent Gradio deployment
