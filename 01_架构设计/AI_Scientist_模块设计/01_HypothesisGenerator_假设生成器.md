# HypothesisGenerator — 假设生成器

> 从文献 Gap 到可验证科学假设
> 融入物理方程约束 + 创新性评分

---

## 模块定位

**输入**：文献综述（已检索）+ 已知知识边界
**输出**：可验证的科学假设 + 创新性评分 + 验证路径建议

**核心能力**：
- 识别文献中的矛盾点、未覆盖区域、过度简化假设
- 生成符合物理定律的可验证假设
- 评估假设的创新性、可行性、科学价值

---

## 独创性设计

### 1. 物理方程嵌入验证

传统方法：纯 LLM 文本推理 → 容易生成违反物理规律的假设

**我们的方法**：用物理方程作为约束层

```python
class PhysicsConstraintLayer:
    """物理方程约束层"""

    def __init__(self):
        # 气固界面核心物理方程
        self.equations = {
            "catalytic_efficiency": "γ = k_r / (k_r + k_d)",  # 催化效率
            "slip_velocity": "u_s = (2-σ_v)/σ_v · λ · du/dy|_w",  # 滑动速度
            "temperature_jump": "T_s - T_w = (2-σ_T)/σ_T · (2γ/(γ+1)) · λ/k · q_w",  # 温度跳跃
            "knudsen": "Kn = λ/L",  # 克努森数
            "mach_number": "M = u/a",  # 马赫数
        }

    def validate_hypothesis(self, hypothesis: str, params: dict) -> tuple[bool, str]:
        """
        验证假设是否违反物理定律

        Returns:
            (valid, reason): 是否有效 + 原因说明
        """
        # 示例：如果假设提出 γ > 1，则违反定义
        if "catalytic_efficiency" in params and params["catalytic_efficiency"] > 1:
            return False, "催化效率 γ ∈ [0,1]，假设值超出物理边界"

        # 示例：连续介质假设检验
        if "flow_regime" in params:
            kn = params.get("knudsen", 0)
            regime = params["flow_regime"]
            if regime == "continuum" and kn > 0.01:
                return False, f"Kn={kn} > 0.01，不满足连续介质假设"

        return True, "通过物理约束检验"
```

---

### 2. Gap 识别的层次化框架

```
Gap 识别层次
    ↓
┌──────────────────────────────────────┐
│ Level 1: 矛盾点（文献 A 说 X，B 说 Y） │  ← 最容易验证
├──────────────────────────────────────┤
│ Level 2: 未覆盖区域（Ma>15 数据缺失） │  ← 实验机会
├──────────────────────────────────────┤
│ Level 3: 过度简化（忽略稀薄效应）      │  ← 理论改进空间
├──────────────────────────────────────┤
│ Level 4: 跨尺度不一致（连续域→稀薄域）  │  ← 系统性问题
└──────────────────────────────────────┘
```

**System Prompt 设计**：

```
你是一名高超声速气固界面耦合研究领域的假设生成专家。

你的任务是：
1. 阅读提供的文献综述，识别研究 Gap
2. 基于物理约束，生成可验证的科学假设
3. 评估每个假设的创新性、可行性、科学价值

Gap 识别框架：
- Level 1 矛盾点：不同文献对同一现象给出矛盾结论
- Level 2 未覆盖区域：某些参数范围或工况缺乏数据
- Level 3 过度简化：现有模型忽略了重要的物理效应
- Level 4 跨尺度不一致：连续介质假设在稀薄区域失效

假设生成原则：
- 必须可验证（通过计算、实验或文献对比）
- 必须符合物理定律（能量守恒、质量守恒、动量守恒）
- 必须有明确的成功判据

输出格式：
{
  "gap_level": 1-4,
  "gap_description": "Gap 描述",
  "hypothesis": "假设陈述",
  "prediction": "预测结果（具体数值或趋势）",
  "validation_method": "验证方法（计算/实验/文献对比）",
  "physics_constraints": ["涉及的物理方程"],
  "innovation_score": 0-100,
  "feasibility_score": 0-100,
  "scientific_value_score": 0-100
}
```

---

## 核心流程

```
输入：文献综述 + 已知边界
         ↓
┌──────────────────────────────────────┐
│ Step 1: Gap 识别（层次化框架）        │
│   - 矛盾点提取                       │
│   - 未覆盖区域检测                   │
│   - 过度简化识别                     │
│   - 跨尺度不一致检测                 │
└──────────────────┬───────────────────┘
                   ↓
┌──────────────────────────────────────┐
│ Step 2: 假设生成（LLM + 物理约束）    │
│   - 基于每个 Gap 生成 3-5 个假设     │
│   - 物理方程嵌入验证                 │
│   - 过滤违反物理定律的假设           │
└──────────────────┬───────────────────┘
                   ↓
┌──────────────────────────────────────┐
│ Step 3: 假设评分                     │
│   - 创新性（与现有文献的差异度）     │
│   - 可行性（计算/实验资源需求）       │
│   - 科学价值（解决的实际问题）       │
└──────────────────┬───────────────────┘
                   ↓
输出：可验证假设 + 评分 + 排序
```

---

## Prompt 模板

```python
HYPOTHESIS_GENERATION_PROMPT = """
你是一名高超声速气固界面耦合研究领域的假设生成专家。

# 文献综述
{literature_review}

# 已知知识边界
{knowledge_boundary}

# 物理方程约束
{physics_constraints}

# 任务
1. 识别文献综述中的研究 Gap（使用层次化框架）
2. 为每个 Gap 生成 3-5 个可验证的科学假设
3. 用物理方程验证每个假设
4. 评分并排序

# Gap 识别框架
- Level 1 矛盾点：不同文献对同一现象给出矛盾结论
- Level 2 未覆盖区域：某些参数范围或工况缺乏数据
- Level 3 过度简化：现有模型忽略了重要的物理效应
- Level 4 跨尺度不一致：连续介质假设在稀薄区域失效

# 假设生成原则
- 必须可验证（通过计算、实验或文献对比）
- 必须符合物理定律
- 必须有明确的成功判据

# 输出格式（JSON）
{
  "gap_analysis": [
    {
      "level": 1-4,
      "description": "Gap 描述",
      "evidence": ["支持证据"],
      "hypotheses": [
        {
          "hypothesis": "假设陈述",
          "prediction": "预测结果",
          "validation_method": "验证方法",
          "physics_constraints": ["涉及的物理方程"],
          "innovation_score": 0-100,
          "feasibility_score": 0-100,
          "scientific_value_score": 0-100
        }
      ]
    }
  ],
  "top_hypothesis": {
    "gap_index": int,
    "hypothesis_index": int,
    "composite_score": float
  }
}
"""
```

---

## 示例输出

```json
{
  "gap_analysis": [
    {
      "level": 3,
      "description": "现有催化复合系数模型在 2000K 以上时忽略了表面温度对吸附能的影响",
      "evidence": [
        "Anderson et al. 2023: γ(T) = γ₀ · exp(-Ea/RT) 在 T > 2000K 时偏差 > 30%",
        "Zhang et al. 2024: 提出 T 依赖的吸附能模型，但未验证"
      ],
      "hypotheses": [
        {
          "hypothesis": "引入表面温度依赖的吸附能修正：Ea(T) = Ea₀ + α·(T - 1500K) 可将 2000-2500K 区域的预测误差降低至 15% 以内",
          "prediction": "修正模型在 2000-2500K 区域的 RMS 误差从 0.35 降低至 < 0.15",
          "validation_method": "计算验证（DSMC 仿真 + 文献实验数据对比）",
          "physics_constraints": ["catalytic_efficiency", "temperature_jump"],
          "innovation_score": 85,
          "feasibility_score": 90,
          "scientific_value_score": 80
        }
      ]
    }
  ],
  "top_hypothesis": {
    "gap_index": 0,
    "hypothesis_index": 0,
    "composite_score": 85.0
  }
}
```

---

## 与现有工具的集成

```python
class HypothesisGenerator(Action):
    """假设生成器工具"""

    name = "generate_hypothesis"
    description = "基于文献综述生成可验证的科学假设"
    parameters = {
        "type": "object",
        "properties": {
            "topic": {"type": "string", "description": "研究主题，如'催化复合系数建模'"},
            "max_hypotheses": {"type": "integer", "default": 5, "description": "最大假设数量"}
        },
        "required": ["topic"]
    }

    def __init__(self, llm: LLMInterface, registry: ActionRegistry):
        self.llm = llm
        self.registry = registry
        self.physics = PhysicsConstraintLayer()

    async def run(self, topic: str, max_hypotheses: int = 5) -> str:
        # 1. 调用文献检索工具
        search_tool = self.registry.get("search_literature")
        lit_review = await search_tool.run(query=topic)

        # 2. 调用 Web 搜索补充最新研究
        web_tool = self.registry.get("web_search")
        latest_lit = await web_tool.run(query=f"{topic} recent advances 2024")

        # 3. 构建 prompt
        prompt = HYPOTHESIS_GENERATION_PROMPT.format(
            literature_review=lit_review + "\n" + latest_lit,
            knowledge_boundary=self._load_boundary(topic),
            physics_constraints=self._format_constraints()
        )

        # 4. LLM 生成假设
        response = await self.llm.chat([Message.user(prompt)])
        hypotheses = json.loads(response.content)

        # 5. 物理约束验证
        for gap in hypotheses["gap_analysis"]:
            for h in gap["hypotheses"]:
                valid, reason = self.physics.validate_hypothesis(
                    h["hypothesis"], self._extract_params(h)
                )
                h["physics_validation"] = {"valid": valid, "reason": reason}

        # 6. 排序并返回 top-k
        top_hypotheses = self._rank_and_filter(hypotheses, max_hypotheses)
        return json.dumps(top_hypotheses, indent=2, ensure_ascii=False)
```

---

## 评测指标

| 指标 | 定义 | 目标值 |
|------|------|--------|
| **物理约束通过率** | 假设通过物理验证的比例 | ≥ 80% |
| **创新性评分** | 与现有文献的差异度 | ≥ 70 |
| **可验证性** | 假设有明确验证方法的比例 | = 100% |
| **专家一致性** | 与领域专家生成的假设的重合度 | ≥ 60% |

---

## 参考文献（设计参考）

- [AutoGPT-Scientist](https://github.com/koenvo/AutoGPT-Scientist) — 文献综述到假设生成的流程
- [Nature: AI Agents for Experimental Design](https://www.science.org/doi/10.1126/science.ade5672) — 假设生成的评估框架
- [ChemCrow: Chemistry Research Agent](https://arxiv.org/abs/2404.07573) — 领域约束嵌入设计