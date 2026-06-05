# 气固热导 AI Agent — 架构方案（v2）

> 日期：2026-06-01（v2 重写，对齐实际代码实现）
> 状态：架构选型已完成，核心框架100%实现，待数据对齐后跑通闭环

---

## 一、Agent 定位与目标

### 1.1 为什么需要 Agent

当前 LLM 能做到：
- 回答气动热领域的事实性问题（T1 精度）
- 基于 RAG 文献进行推理论证（T2 推理）
- 在约束条件下控制幻觉（T3 抗幻觉）

Agent 需要在此基础上做到：
- **自主检索**：根据问题自动选择检索策略（关键词→语义→引文追踪）
- **多步推理**：分解复杂问题为子问题链，逐步求解
- **证据合成**：从多源文献中提取冲突证据，进行交叉验证
- **工具使用**：调用数值计算、单位换算、论文解析等外部能力
- **研究辅助**：文献综述生成、研究空白识别、假设生成与验证

### 1.2 目标用户场景

| 场景 | Agent 行为 |
|------|------|
| "查找 2024 年 SBLI 展向结构的最新研究" | 检索 + 筛选 + 归纳 |
| "比较 SiO₂ 和 SiC 在 2000K 下的催化复合系数" | 多源检索 + 数值提取 + 对比 |
| "评估现有气固界面催化模型在跨尺度条件下的适用性" | 文献综述 + 批判性分析 + 空白识别 |

---

## 二、架构选型（✅ 已决策 + 已实现）

### 选择：自研轻量 Agent 框架

放弃 LangChain/LangGraph 和 LlamaIndex，自行实现了 Role-Action-Memory-Orchestrator 四件套。

**决策理由**：

| 对比维度 | 自研 | LangChain | LlamaIndex |
|----------|:----:|:---------:|:----------:|
| 领域定制化 | ✅ 完全可控 | ❌ 抽象层多，气动热定制成本高 | ⚠️ RAG强但Agent弱 |
| 工具数量需求 | ✅ 2个核心工具 | ❌ 杀鸡用牛刀 | ⚠️ 侧重检索 |
| 部署轻量 | ✅ 零框架依赖 | ❌ 全家桶import几百MB | ❌ 同样重 |
| 调试透明度 | ✅ 断点即达 | ❌ 层层封装，排查痛苦 | ⚠️ 中等 |
| 桌面级8GB适配 | ✅ 内存可控 | ❌ 额外内存开销 | ❌ 同上 |

**核心组件实现（`05_AI_Agent/core/`）**：

| 模块 | 文件 | 功能 |
|------|------|------|
| Agent | `agent.py` | 顶层组装，双模式执行（ReAct/Plan-Execute），工具管理 |
| Orchestrator | `orchestrator.py` | ReAct循环（最大8步）+ Plan-Execute三阶段（分解→执行→综合） |
| Role | `role.py` | Agent身份/目标/约束定义，System Prompt构建 |
| Memory | `memory.py` | ShortTermMemory（滑动窗口+token截断）+ WorkingMemory（KV任务上下文） |
| Action | `action.py` | 工具基类 + ActionRegistry，OpenAI Function Calling Schema导出 |
| LLM | `llm.py` | httpx异步客户端，chat() + chat_with_tools()，3套预设（vLLM/百炼/Ollama） |
| Message | `message.py` | 统一消息格式，角色工厂方法，工具调用支持 |

**已实现工具（`05_AI_Agent/tools/`）**：

| 工具 | 文件 | 状态 |
|------|------|:----:|
| LiteratureSearchTool | `search.py` | 🟡 CSV关键词检索可用，FAISS语义检索代码已写（待embedding模型激活） |
| WebSearchTool | `web_search.py` | ✅ OpenAlex API 外部文献搜索（2.5亿+论文，免费无鉴权） |
| AeroThermalComputeTool | `compute.py` | ✅ 5类计算：驻点热流/Knudsen数/催化系数/单位换算/边界层厚度 |
| CodeExecutionTool | `code_exec.py` | ✅ Python子进程沙箱执行（30s超时，支持pip install） |
| CitationResolverTool | `citation.py` | ✅ CrossRef + OpenAlex DOI解析 + BibTeX生成 |
| PDFAnalysisTool | `pdf_parser.py` | ✅ PyMuPDF论文解析（元数据/全文/章节/参数识别/关键词搜索） |
| ReportTool | `report.py` | ✅ 结构化Markdown研究报告生成 |
| ExportFindingTool | `report.py` | ✅ 单条研究发现追加记录 |
| PandocExportTool | `pandoc_export.py` | ✅ Markdown → LaTeX/DOCX/PDF 格式导出 |

**LLM 后端**：自训8B QLoRA（推理内核），备选百炼API / Ollama

---

## 三、核心模块

### 3.1 工具链（Tool Registry）

**已实现**：
- ✅ 文献检索：本地CSV关键词 + FAISS语义（代码就绪，待embedding激活）
- ✅ 外部文献搜索：OpenAlex API（2.5亿+论文，关键词/DOI/标题多模式检索）
- ✅ 气动热参数计算：驻点热流/Knudsen/催化系数/单位换算/边界层厚度
- ✅ Python代码执行：子进程沙箱，超时30s，适用于复杂计算+作图
- ✅ 引文解析：CrossRef/OpenAlex DOI→完整元数据+BibTeX
- ✅ PDF论文解析：PyMuPDF文本提取/元数据/章节结构/气动热参数识别
- ✅ 报告生成：结构化Markdown + 单条发现追加记录
- ✅ 格式导出：Pandoc Markdown→LaTeX/DOCX/PDF（CJK支持）

**待扩展**：
```
知识图谱工具（Phase 3）
└── 跨文献关系查询（引用链、主题聚类、知识缺口识别）

数据提取工具
└── 结构化正则匹配（温度/压力/催化系数等领域的批量参数提取）
```

### 3.2 编排引擎（Orchestrator）

已实现在 `core/orchestrator.py`：

```
用户输入 → Agent.run()
              ├── ReAct 模式：推理→行动→观察 循环（最大8步）
              │   └── LLM决策 → 工具调用 → 结果记录 → 下一轮推理
              │
              └── Plan-Execute 模式：规划→分步执行→综合
                  ├── Phase 1: LLM 分解任务为步骤列表
                  ├── Phase 2: 逐步执行（每步是mini ReAct循环）
                  └── Phase 3: LLM 综合所有步骤结果为最终答案
```

### 3.3 记忆系统（Memory）

已实现在 `core/memory.py`：

```
ShortTermMemory：对话历史滑动窗口
  ├── 基于token估算自动截断
  └── 保留最近N轮交互上下文

WorkingMemory：任务上下文KV存储
  ├── 已检索关键词
  ├── 已阅读论文列表
  ├── 中间计算结果
  └── 当前推理状态

待扩展：
  └── LongTermMemory：跨会话持久化（SQLite/向量库）
```

### 3.4 与 LLM 的接口

已实现在 `core/llm.py`：

```
Agent 编排引擎
  ├── 调用 LLM（自训8B QLoRA）做推理决策
  ├── 调用 RAG 检索增强（FAISS待重建后激活）
  └── 调用外部工具链（OpenAI Function Calling协议）

LLM 角色：
  - 规划者：将用户意图分解为子任务
  - 决策者：根据当前状态选择下一步行动
  - 合成者：将多源证据合并为连贯回答
  - 批判者：验证输出的一致性与可靠性
```

---

## 四、评测体系

| 维度 | 指标 | 方法 |
|------|------|------|
| 任务完成率 | 多步任务端到端成功率 | 10-20题领域评测集 |
| 检索质量 | Precision/Recall@K | 标注查询-相关论文对 |
| 工具调用精度 | 正确工具选择率、参数正确率 | 功能测试用例 |
| 幻觉率 | 编造引用/数值比例 | 自动校验 + 人工抽样 |
| 效率 | 平均步数、Token 消耗 | 日志统计 |

---

## 五、开发路线图

| Phase | 内容 | 状态 |
|:--:|------|:--:|
| 0 | 架构设计 + 技术选型 | ✅ 自研框架已选定并实现 |
| 1 | 数据对齐（QA→索引→微调）+ 激活FAISS语义检索 | 🔴 依赖新版QA |
| 2 | 编排验证 + Re-ranker/QIS集成 + 长期记忆 | 🔴 待数据对齐后启动 |
| 3 | 评测体系 + 论文解析工具 + 领域深度 | 🔴 待启动 |
| 4 | 部署集成（Gradio/API）+ 用户测试 | 🔴 待启动 |

---

## 六、已决策事项（无待定）

| 决策点 | 决定 | 状态 |
|------|------|:--:|
| Agent 框架 | 自研（core/ 已实现） | ✅ |
| 工具调用协议 | OpenAI Function Calling（action.py + llm.py） | ✅ |
| Agent LLM | 自训8B QLoRA，后端走vLLM/百炼/Ollama | ✅ |
| 记忆存储 | 短期滑动窗口 + 工作记忆KV（已实现），长期记忆待扩展 | 🟡 |
| 前端 | Gradio（已有web_ablation.py可复用） | 🟡 |
| MCP协议 | 不需要，Function Calling足够 | ✅ |
