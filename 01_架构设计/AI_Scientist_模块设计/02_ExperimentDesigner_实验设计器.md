# ExperimentDesigner — 实验设计器

> 从假设到可执行的实验方案
> 多尺度参数空间设计 + 智能采样策略

---

## 模块定位

**输入**：科学假设 + 物理约束 + 计算资源约束
**输出**：实验方案（变量定义 + 采样策略 + 控制参数）+ 执行脚本

**核心能力**：
- 将假设转化为可操作的实验设计
- 智能采样参数空间（平衡探索与收敛）
- 生成可执行的代码脚本（Python/CFD）

---

## 独创性设计

### 1. 多尺度参数空间映射

气固界面研究跨越多个物理尺度：

```
宏观尺度（飞行器）
    Ma, H, α（马赫数、高度、攻角）
         ↓
中观尺度（边界层）
    Re, Kn, Pr（雷诺数、克努森数、普朗特数）
         ↓
微观尺度（界面）
    γ, σ_v, σ_T（催化效率、动量协调系数、能量协调系数）
         ↓
原子尺度（表面）
    E_ads, S_cat（吸附能、催化位点密度）
```

**我们的方法**：建立跨尺度参数关联模型

```python
class MultiScaleParameterMapper:
    """多尺度参数映射器"""

    def __init__(self):
        self.scale_map = {
            "macro": ["Ma", "H_km", "alpha_deg"],
            "meso": ["Re", "Kn", "Pr"],
            "micro": ["gamma", "sigma_v", "sigma_T"],
            "atomic": ["E_ads_eV", "S_cat_1m2"]
        }

    def map_macroscale_to_micro(self, Ma: float, H_km: float) -> dict:
        """
        从宏观飞行条件映射到微观界面参数

        Example: Ma=15, H=55km → γ=0.1, σ_v=0.8
        """
        # 基于已有文献和经验模型
        kn = self._compute_knudsen(Ma, H_km)

        if kn < 0.01:  # 连续介质
            return {"gamma": 0.3, "sigma_v": 1.0, "sigma_T": 1.0}
        elif kn < 10:  # 过渡区
            # 插值估计
            return {
                "gamma": 0.1 + 0.2 * (1 - kn/10),
                "sigma_v": 0.5 + 0.5 * (1 - kn/10),
                "sigma_T": 0.6 + 0.4 * (1 - kn/10)
            }
        else:  # 自由分子流
            return {"gamma": 0.05, "sigma_v": 0.2, "sigma_T": 0.3}

    def _compute_knudsen(self, Ma: float, H_km: float) -> float:
        """基于飞行条件计算 Knudsen 数"""
        # 简化模型：Kn ∝ H / Ma
        return (H_km / 100) / Ma
```

---

### 2. 智能采样策略

传统方法：网格采样 → 计算成本高，覆盖率低

**我们的方法**：自适应采样 + 物理敏感度引导

```python
class AdaptiveSamplingStrategy:
    """自适应采样策略"""

    def __init__(self):
        self.strategies = {
            "sobol": "Sobol 序列（低差异序列，适合初始探索）",
            "latin_hypercube": "拉丁超立方采样（平衡探索与计算）",
            "physics_guided": "物理敏感度引导采样（聚焦关键区域）",
            "adaptive": "自适应采样（根据前序结果动态调整）"
        }

    def design_experiment(
        self,
        hypothesis: dict,
        budget: int = 50,
        strategy: str = "adaptive"
    ) -> dict:
        """
        设计实验采样方案

        Args:
            hypothesis: 假设信息（含参数范围）
            budget: 计算预算（仿真次数）
            strategy: 采样策略

        Returns:
            采样点列表 + 优先级排序
        """
        params = hypothesis.get("parameters", [])
        ranges = {p["name"]: (p["min"], p["max"]) for p in params}

        if strategy == "physics_guided":
            return self._physics_guided_sampling(hypothesis, budget, ranges)
        elif strategy == "adaptive":
            return self._adaptive_sampling(hypothesis, budget, ranges)
        else:
            return self._standard_sampling(strategy, budget, ranges)

    def _physics_guided_sampling(self, hypothesis: dict, budget: int, ranges: dict) -> dict:
        """
        物理敏感度引导采样

        核心思路：在物理过渡区（如 Kn=0.01-10）加密采样
        """
        samples = []

        # 1. 识别关键过渡区
        critical_regions = self._identify_critical_regions(hypothesis)

        # 2. 分配采样预算
        region_budget = {
            "critical": int(budget * 0.6),  # 60% 用于关键区域
            "baseline": int(budget * 0.2),  # 20% 用于基线区域
            "exploration": int(budget * 0.2)  # 20% 用于探索
        }

        # 3. 各区域采样
        for region, samples_count in region_budget.items():
            if region == "critical":
                region_samples = self._sample_in_critical_regions(
                    critical_regions, samples_count, ranges
                )
            else:
                region_samples = self._sample_uniform(samples_count, ranges)

            samples.extend(region_samples)

        return {"samples": samples, "strategy": "physics_guided"}

    def _identify_critical_regions(self, hypothesis: dict) -> list[dict]:
        """
        识别物理临界区域

        Example: Kn=0.01（连续→过渡）、Ma=5（亚声速→超声速）
        """
        regions = []

        # 克努森数临界区
        if any("Kn" in p["name"] for p in hypothesis["parameters"]):
            regions.append({
                "param": "Kn",
                "range": (0.001, 10),  # 过渡区
                "priority": "high"
            })

        # 马赫数临界区
        if any("Ma" in p["name"] for p in hypothesis["parameters"]):
            regions.append({
                "param": "Ma",
                "range": (0.8, 1.2),  # 跨声速区
                "priority": "medium"
            })

        return regions
```

---

## 核心流程

```
输入：假设 + 物理约束 + 计算资源
         ↓
┌──────────────────────────────────────┐
│ Step 1: 参数定义                     │
│   - 从假设提取关键变量               │
│   - 定义物理约束边界                 │
│   - 映射多尺度参数                   │
└──────────────────┬───────────────────┘
                   ↓
┌──────────────────────────────────────┐
│ Step 2: 采样策略选择                 │
│   - 分析参数敏感度                   │
│   - 选择采样策略（物理引导/自适应）  │
│   - 计算采样点分布                   │
└──────────────────┬───────────────────┘
                   ↓
┌──────────────────────────────────────┐
│ Step 3: 实验配置生成                 │
│   - 生成 CFD/DSMC 配置文件           │
│   - 生成 Python 执行脚本             │
│   - 预估计算时间                     │
└──────────────────┬───────────────────┘
                   ↓
输出：实验方案 + 可执行脚本
```

---

## Prompt 模板

```python
EXPERIMENT_DESIGN_PROMPT = """
你是一名高超声速气固界面耦合实验设计专家。

# 待验证假设
{hypothesis}

# 物理约束
{physics_constraints}

# 计算资源
- 可用计算节点：{num_nodes}
- 单节点算力：{node_spec}
- 预期预算：{budget_hours} 小时

# 任务
1. 从假设中提取关键参数，定义参数空间
2. 选择合适的采样策略（物理敏感度引导/自适应）
3. 设计采样点分布（预算内最大化信息增益）
4. 生成实验配置（CFD/DSMC 输入参数）

# 设计原则
- 在物理过渡区（如 Kn=0.01-10）加密采样
- 采样点需覆盖参数空间的边界和中心
- 预估每个采样点的计算时间
- 总计算时间不超过预算

# 输出格式（JSON）
{
  "parameters": [
    {
      "name": "参数名",
      "min": 最小值,
      "max": 最大值,
      "unit": "单位",
      "scale": "宏观/中观/微观/原子"
    }
  ],
  "sampling_strategy": "策略名",
  "sampling_points": [
    {
      "Ma": 15.0,
      "H_km": 55.0,
      "gamma": 0.1,
      "estimated_time_hours": 0.5
    }
  ],
  "critical_regions": [
    {
      "param": "Kn",
      "range": [0.001, 10],
      "reason": "连续介质到稀薄气体过渡区"
    }
  ],
  "total_estimated_time_hours": 25.0,
  "execution_script": "#!/bin/bash\n..."
}
"""
```

---

## 示例输出

```json
{
  "parameters": [
    {"name": "Ma", "min": 10, "max": 20, "unit": "-", "scale": "macro"},
    {"name": "H_km", "min": 40, "max": 70, "unit": "km", "scale": "macro"},
    {"name": "gamma", "min": 0.05, "max": 0.3, "unit": "-", "scale": "micro"}
  ],
  "sampling_strategy": "physics_guided",
  "sampling_points": [
    {"Ma": 15.0, "H_km": 55.0, "gamma": 0.1, "estimated_time_hours": 0.5},
    {"Ma": 12.5, "H_km": 47.5, "gamma": 0.2, "estimated_time_hours": 0.6},
    {"Ma": 17.5, "H_km": 62.5, "gamma": 0.15, "estimated_time_hours": 0.4}
  ],
  "critical_regions": [
    {
      "param": "Kn",
      "range": [0.001, 10],
      "reason": "连续介质到稀薄气体过渡区"
    }
  ],
  "total_estimated_time_hours": 25.0,
  "execution_script": "#!/bin/bash\n# DSMC 仿真批量执行脚本\nfor i in {0..49}; do\n  python run_dsmc.py --config=config_$i.json --output=result_$i.dat\ndone"
}
```

---

## 与现有工具的集成

```python
class ExperimentDesigner(Action):
    """实验设计器工具"""

    name = "design_experiment"
    description = "将科学假设转化为可执行的实验方案"
    parameters = {
        "type": "object",
        "properties": {
            "hypothesis": {"type": "string", "description": "JSON 格式的假设信息"},
            "budget_hours": {"type": "number", "default": 24.0, "description": "计算预算（小时）"},
            "strategy": {"type": "string", "default": "adaptive", "description": "采样策略"}
        },
        "required": ["hypothesis"]
    }

    def __init__(self, llm: LLMInterface, compute_tool: AeroThermalComputeTool):
        self.llm = llm
        self.compute_tool = compute_tool
        self.mapper = MultiScaleParameterMapper()
        self.sampler = AdaptiveSamplingStrategy()

    async def run(self, hypothesis: str, budget_hours: float = 24.0, strategy: str = "adaptive") -> str:
        # 1. 解析假设
        hyp = json.loads(hypothesis)

        # 2. 构建 prompt
        prompt = EXPERIMENT_DESIGN_PROMPT.format(
            hypothesis=json.dumps(hyp, indent=2),
            physics_constraints=self._get_physics_constraints(),
            num_nodes=4,
            node_spec="V100 16GB",
            budget_hours=budget_hours
        )

        # 3. LLM 生成实验设计
        response = await self.llm.chat([Message.user(prompt)])
        design = json.loads(response.content)

        # 4. 多尺度参数映射验证
        validated_design = self._validate_multi_scale_mapping(design)

        # 5. 生成执行脚本
        execution_script = self._generate_execution_script(validated_design)
        validated_design["execution_script"] = execution_script

        # 6. 保存配置文件
        self._save_configs(validated_design)

        return json.dumps(validated_design, indent=2, ensure_ascii=False)
```

---

## 评测指标

| 指标 | 定义 | 目标值 |
|------|------|--------|
| **参数覆盖率** | 采样点覆盖参数空间的比例 | ≥ 90% |
| **关键区域密度** | 物理过渡区的采样点密度 | ≥ 基线的 2 倍 |
| **预算准确性** | 实际计算时间与预估的偏差 | ≤ 20% |
| **脚本可执行性** | 生成脚本一次运行成功率 | ≥ 95% |

---

## 参考文献（设计参考）

- [Nature: AI Agents for Experimental Design](https://www.science.org/doi/10.1126/science.ade5672) — 实验设计方法论
- [SciAgents: Autonomous Research Agents](https://github.com/scientific-ai/sciagents) — 采样策略设计
- [Bayesian Optimization for Scientific Discovery](https://arxiv.org/abs/2305.08987) — 自适应采样理论