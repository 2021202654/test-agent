# Agent 评测基准

> **用途**：评估自研 Agent 框架的编排能力，独立于 LLM 微调质量（用同一基座模型即可跑）
> **被测对象**：Agent（core/agent.py + core/orchestrator.py）+ 两个领域工具
> **设计日期**：2026-06-02
> **状态**：设计完成，待执行

---

## 一、评测体系总览

| 维度 | 代号 | 题目数 | 测试目标 |
|------|:---:|:-----:|----------|
| 工具选择精度 | T1 | 5 | 能否正确判断"该用哪个工具" |
| 多步任务编排 | T2 | 5 | 检索→计算→综合 端到端成功率 |
| 工具滥用防御 | T3 | 4 | 不该用工具时能否克制 |
| 编排鲁棒性 | T4 | 4 | 工具异常/参数缺失/歧义查询时的降级能力 |

**总计 18 题**，预计单次评测耗时 ~15-20 分钟（本地 RTX 5060 4-bit）。

---

## 二、T1 — 工具选择精度 (Tool Selection Accuracy)

> 测试 Agent 能否根据查询意图，正确选择 LiteratureSearchTool 或 AeroThermalComputeTool，或直接回答。

### T1-Q1: 明确检索 — 催化壁材料

**Query**: "Find papers that report catalytic recombination coefficients for SiO₂ and SiC surfaces."

| 正确答案 | 记分 |
|----------|:--:|
| 调用 LiteratureSearchTool，搜索关键词含 "catalytic recombination" + "SiO₂" 或 "SiC" | 2 |
| 调用了 LiteratureSearchTool 但关键词不完整 | 1 |
| 调用了 AeroThermalComputeTool 或直接回答无检索 | 0 |

---

### T1-Q2: 明确计算 — 驻点热流

**Query**: "Calculate the stagnation-point heat flux for a reentry vehicle with nose radius 1.2 m, velocity 6.5 km/s, at 55 km altitude where density is approximately 0.001 kg/m³."

| 正确答案 | 记分 |
|----------|:--:|
| 调用 AeroThermalComputeTool，calc_type="stagnation_heat_flux"，参数 velocity=6500, radius=1.2, density=0.001 | 2 |
| 调用了 AeroThermalComputeTool 但参数不全或类型错误 | 1 |
| 调用了 LiteratureSearchTool 或直接计算无工具 | 0 |

---

### T1-Q3: 明确计算 — 流态判断

**Query**: "A hypersonic vehicle has a characteristic length of 2 m at 80 km altitude (T ≈ 200 K, P ≈ 1 Pa). Is the flow in the continuum regime, transitional, or free-molecular?"

| 正确答案 | 记分 |
|----------|:--:|
| 调用 AeroThermalComputeTool，calc_type="knudsen_number"，根据返回值判断流态 | 2 |
| 调用了工具但 calc_type 选错（如选了 stagnation_heat_flux） | 1 |
| 没有调用工具，凭"知识"直接回答 | 0 |

---

### T1-Q4: 明确检索 — 特定文献

**Query**: "What does the literature say about the effect of surface roughness on catalytic recombination at the gas-solid interface?"

| 正确答案 | 记分 |
|----------|:--:|
| 调用 LiteratureSearchTool，搜索 "surface roughness" + "catalytic recombination" 或 "gas-solid interface" | 2 |
| 调用了 LiteratureSearchTool 但关键词不够精确 | 1 |
| 调用了错误工具或直接编造 | 0 |

---

### T1-Q5: 无需工具 — 概念定义

**Query**: "What is the definition of the Knudsen number?"

| 正确答案 | 记分 |
|----------|:--:|
| 直接回答（基座模型知识足够），不调用任何工具 | 2 |
| 调用了 LiteratureSearchTool（过度依赖检索，但不扣大分） | 1 |
| 调用了 AeroThermalComputeTool 做计算（完全错误的选择） | 0 |

---

## 三、T2 — 多步任务编排 (Multi-Step Orchestration)

> 测试 Agent 能否完成"检索 → 提取 → 计算 → 综合"的端到端流程。每题需要 ≥2 步工具调用。

### T2-Q1: 检索+计算 — Apollo 驻点热流验证

**Query**: "Find the reported stagnation-point heat flux for the Apollo capsule under FCW conditions, then verify the value using the Fay-Riddell correlation with typical Apollo entry parameters (velocity = 11 km/s, nose radius = 4.7 m, density = 0.0012 kg/m³). Compare the two results."

| 评分维度 | 满分 |
|----------|:--:|
| 步骤 1：调用 LiteratureSearchTool 检索 Apollo + stagnation heat flux + FCW | 1 |
| 步骤 2：调用 AeroThermalComputeTool 用 Fay-Riddell 公式计算 | 1 |
| 步骤 3：对比文献值与计算值，给出差异分析 | 1 |
| **总分** | **3** |

---

### T2-Q2: 检索+提取+计算 — 催化系数对比

**Query**: "Find the catalytic recombination coefficient of SiO₂ at 2000K from the literature, then calculate the Knudsen number for a TPS tile of 0.05 m characteristic length under typical reentry conditions at 60 km (T ≈ 247 K, P ≈ 20 Pa). Based on the flow regime result, discuss whether the reported catalytic coefficient is applicable."

| 评分维度 | 满分 |
|----------|:--:|
| 步骤 1：LiteratureSearchTool 检索 SiO₂ catalytic coefficient at 2000K | 1 |
| 步骤 2：AeroThermalComputeTool knudsen_number (L=0.05, T=247, P=20) | 1 |
| 步骤 3：综合两个工具的结果，讨论流态对催化系数适用性的影响 | 1 |
| **总分** | **3** |

---

### T2-Q3: 多源检索+综合 — SBLI 热环境

**Query**: "Search for papers on shock-wave/boundary-layer interaction (SWBLI) heating augmentation, then search for papers on gap heating in control surfaces. Synthesize both findings to explain the compound aerothermal risk at a body-flap hinge line."

| 评分维度 | 满分 |
|----------|:--:|
| 步骤 1：LiteratureSearchTool 检索 SWBLI + heating augmentation | 1 |
| 步骤 2：LiteratureSearchTool 检索 gap heating + control surface（第二次独立检索） | 1 |
| 步骤 3：将两次检索结果综合为连贯分析 | 1 |
| **总分** | **3** |

---

### T2-Q4: 检索+数值提取+单位换算

**Query**: "Find the maximum stagnation-point heat flux value reported for the X-34 vehicle. Convert it from the reported unit to kW/m². Determine whether this value exceeds the typical TPS design limit of 500 kW/m²."

| 评分维度 | 满分 |
|----------|:--:|
| 步骤 1：LiteratureSearchTool 检索 X-34 + stagnation heat flux | 1 |
| 步骤 2：AeroThermalComputeTool unit_conversion 转单位 | 1 |
| 步骤 3：对比换算结果与 500 kW/m² 阈值 | 1 |
| **总分** | **3** |

---

### T2-Q5: 检索+边界层计算 — 转捩预测

**Query**: "Search for literature on hypersonic boundary-layer transition criteria. Then estimate the boundary-layer thickness at x = 1.5 m with Re = 5×10⁶ on a flat plate. Discuss whether the estimated thickness is consistent with the transition mechanisms described in the retrieved literature."

| 评分维度 | 满分 |
|----------|:--:|
| 步骤 1：LiteratureSearchTool 检索 boundary-layer transition + hypersonic | 1 |
| 步骤 2：AeroThermalComputeTool boundary_layer (x=1.5, reynolds=5e6) | 1 |
| 步骤 3：文献机制与计算结果交叉验证，给出"一致/不一致+理由" | 1 |
| **总分** | **3** |

---

## 四、T3 — 工具滥用防御 (Tool Abuse Resistance)

> 测试 Agent 是否在不该使用工具时正确克制。失败模式：Agent 过度 eager，见什么查什么。

### T3-Q1: 纯常识 — Nusselt 数定义

**Query**: "What is the physical meaning of the Nusselt number? How does it differ from the Stanton number?"

| 正确答案 | 记分 |
|----------|:--:|
| 直接回答，不调用工具（基座模型常识足够） | 2 |
| 调用了 LiteratureSearchTool 但回答仍正确 | 1 |
| 调用了 AeroThermalComputeTool 做无意义的计算 | 0 |

---

### T3-Q2: 伪精确数值 — 捏造参数

**Query**: "What is the exact catalytic recombination coefficient of Teflon at 3500 K?"

| 正确答案 | 记分 |
|----------|:--:|
| 先尝试检索 LiteratureSearchTool → 无结果 → 明确告知"文献中未找到 Teflon 在 3500K 的催化系数数据" | 2 |
| 调用了 AeroThermalComputeTool 但 catalytic_coefficient 参数表里没有 Teflon → 返回工具错误信息 → Agent 如实传递 | 1 |
| 不查直接编造数值 | 0 |

---

### T3-Q3: 纯逻辑推理 — 无需工具

**Query**: "If the Knudsen number Kn >> 1, would the Fay-Riddell stagnation heat flux formula still be applicable? Why or why not?"

| 正确答案 | 记分 |
|----------|:--:|
| 直接基于物理知识推理：Fay-Riddell 假定连续介质，Kn≫1 是自由分子流，不适用 | 2 |
| 调用了 AeroThermalComputeTool 计算 Knudsen 数，但推理仍然正确 | 1 |
| 调用了 LiteratureSearchTool 检索 "Fay-Riddell validity Knudsen"，多此一举 | 1 |
| 不调用工具但推理错误 | 0 |

---

### T3-Q4: 主观研究问题 — 不应检索

**Query**: "What do you think is the most promising direction for future research in hypersonic aerothermodynamics?"

| 正确答案 | 记分 |
|----------|:--:|
| 基于 Agent 角色定义给出有根据的判断，可调用 LiteratureSearchTool 检索研究前沿 → 综合回答 | 2 |
| 直接回答无检索（虽然不算错，但领域 Agent 最好有文献支撑） | 1 |
| 胡乱调用 AeroThermalComputeTool | 0 |

> 注：这题和前三题不同——"研究展望"用检索是合理的。区分度在于：Agent 应该用检索获取前沿动态再回答。

---

## 五、T4 — 编排鲁棒性 (Orchestration Robustness)

> 测试 Agent 在边界条件下的降级处理能力。

### T4-Q1: 工具返回无结果 — 检索空集

**Query**: "Find papers on the application of quantum computing to catalytic wall modeling in hypersonic flows."

| 正确答案 | 记分 |
|----------|:--:|
| 调用 LiteratureSearchTool → 返回空或噪声 → Agent 告知"当前文献库未找到相关研究"而非编造 | 2 |
| 调用了工具，但取了一条不相关的结果强行回答 | 1 |
| 不查直接编造"量子计算在催化壁建模中的应用……" | 0 |

---

### T4-Q2: 参数缺失 — Agent 应追问

**Query**: "Calculate the stagnation-point heat flux for a reentry vehicle."

| 正确答案 | 记分 |
|----------|:--:|
| 识别参数不足（velocity / radius / density 至少缺两个），反问用户补充 | 2 |
| 盲目调用 AeroThermalComputeTool 使用默认值（radius=1.0），未提醒用户这是假定值 | 1 |
| 编造参数直接给出结果 | 0 |

---

### T4-Q3: 多义词歧义消解 — "catalytic wall"

**Query**: "What is the efficiency of a catalytic wall?"

| 正确答案 | 记分 |
|----------|:--:|
| 意识到"催化壁"在气动热领域有特定含义（表面催化复合），与化学工程中的催化壁不同。调用 LiteratureSearchTool 前先澄清查询意图，或检索时限定 aerothermal 上下文字段 | 2 |
| 直接检索 "catalytic wall efficiency" 可能搜到化学催化文献，但 Agent 在综合时能识别领域不匹配并过滤 | 1 |
| 检索到化学催化文献后直接混合引用，混淆两个领域 | 0 |

---

### T4-Q4: ReAct 循环超限 — 复杂任务

**Query**: "For each of the following five TPS materials — SiO₂, SiC, Al₂O₃, carbon-phenolic, and RCG — find their catalytic recombination coefficients at 2000K, compute the corresponding stagnation heat flux reduction relative to FCW for a vehicle with R_n = 2 m, V = 7 km/s, ρ = 0.0008 kg/m³, and rank them from best to worst catalytic performance."

| 正确答案 | 记分 |
|----------|:--:|
| 合理分解任务：先检索多个材料的催化系数 → 逐个计算 → 排序。如果 ReAct 步数上限（8 步）不够，Agent 应输出已完成部分 + "部分完成"标记 | 2 |
| 尝试完成全任务但超过最大步数被截断，输出不完整 | 1 |
| 放弃执行或只处理了 1-2 个材料 | 0 |

---

## 六、评分汇总表

### 6.1 主评分表

| 题号 | 维度 | 满分 | 最低通过线 |
|:---:|------|:---:|:--------:|
| T1-Q1 | 工具选择 | 2 | 1 |
| T1-Q2 | 工具选择 | 2 | 1 |
| T1-Q3 | 工具选择 | 2 | 1 |
| T1-Q4 | 工具选择 | 2 | 1 |
| T1-Q5 | 工具选择 | 2 | 1 |
| T2-Q1 | 多步编排 | 3 | 2 |
| T2-Q2 | 多步编排 | 3 | 2 |
| T2-Q3 | 多步编排 | 3 | 2 |
| T2-Q4 | 多步编排 | 3 | 2 |
| T2-Q5 | 多步编排 | 3 | 2 |
| T3-Q1 | 工具滥用 | 2 | 1 |
| T3-Q2 | 工具滥用 | 2 | 1 |
| T3-Q3 | 工具滥用 | 2 | 1 |
| T3-Q4 | 工具滥用 | 2 | 1 |
| T4-Q1 | 鲁棒性 | 2 | 1 |
| T4-Q2 | 鲁棒性 | 2 | 1 |
| T4-Q3 | 鲁棒性 | 2 | 1 |
| T4-Q4 | 鲁棒性 | 2 | 1 |
| **总计** | | **41** | **26** |

### 6.2 维度分

| 维度 | 满分 | 及格线 | 定义 |
|------|:---:|:-----:|------|
| 工具选择精度 (FA) | 10 | 6 | T1 总分 |
| 多步任务完成率 (MC) | 15 | 9 | T2 总分 |
| 工具克制率 (TR) | 8 | 5 | T3 总分 |
| 鲁棒性 (RB) | 8 | 5 | T4 总分 |
| **综合 (Total)** | **41** | **26** | |

### 6.3 论文可用派生指标

| 指标 | 公式 | 说明 |
|------|------|------|
| Tool Selection Accuracy | T1 得分 / 10 | 正确工具选择率 |
| Multi-Step Completion Rate | T2 ≥2 分的题目数 / 5 | 端到端任务成功率 |
| Tool Abuse Rate | (T3 满分8 - T3 得分) / 8 | 越低越好 |
| Orchestration Robustness | T4 得分 / 8 | 边界条件处理能力 |

---

## 七、评测执行矩阵

### 7.1 配置对照

| 配置 | LLM | Agent 框架 | 工具 | 目的 |
|:---:|-----|:---:|------|------|
| Config A | Llama3.1-8B 基座 (4-bit) | ✅ core/ | ✅ search + compute | **基线**：基座模型 + Agent |
| Config B | Llama3.1-8B + LoRA (4-bit) | ✅ core/ | ✅ search + compute | **目标**：微调模型 + Agent |
| Config C | Llama3.1-8B (4-bit) | ❌ 无编排，单轮对话 | ❌ 无工具 | **消融下限**：纯基座无 Agent |

### 7.2 论文中可做的分析

```
Config A vs Config C → 量化 Agent 框架的独立贡献（工具使用能力）
Config B vs Config A → 量化领域微调对 Agent 能力的提升（编排质量改善）
T4 全系列          → 各配置的鲁棒性退化模式分析
```

---

## 八、执行注意事项

1. **评测环境**：WSL2 Ubuntu 24.04，RTX 5060 8GB，bitsandbytes 4-bit NF4
2. **重复次数**：每 query 跑 3 次取中位数（LLM 输出有随机性）
3. **评分方式**：人工评分 + LLM-as-a-Judge 辅助校验，最终以人工为准
4. **prompt 固定**：System Prompt 使用 `core/role.py` 中的 `AEROTHERMAL_EXPERT_ROLE` 模板
5. **统计报告**：每配置需报告维度分 + 总分 + 失败模式分布（如"T2 类失败集中在检索噪声"）

---

## 九、与 Golden Questions 的关系

| 对比 | Golden Questions (LLM 评测) | Agent 评测基准 |
|------|---------------------------|--------------|
| 被测对象 | LLM/RAG 文本质量 | Agent 编排+工具使用 |
| 工具调用 | 不涉及 | 核心考察点 |
| 难度分布 | T1/T2/T3 按推理深度 | T1-T4 按编排复杂度 |
| 复用关系 | 可作为 Agent 的"推理质量"子维度 | **互补**，两套评测覆盖完整系统 |
