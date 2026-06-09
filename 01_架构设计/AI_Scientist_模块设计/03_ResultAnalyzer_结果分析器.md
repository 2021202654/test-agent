# ResultAnalyzer — 结果分析器

> 从实验数据到科学结论
> 统计分析 + 可视化 + 跨尺度一致性检验

---

## 模块定位

**输入**：实验数据（仿真结果）+ 原始假设 + 物理约束
**输出**：统计结论 + 可视化图表 + 一致性检验报告

**核心能力**：
- 统计分析（显著性、相关性、误差分析）
- 自动化可视化（热图、参数扫描、相图）
- 跨尺度一致性检验（连续→稀薄）
- 异常检测（数据质量验证）

---

## 独创性设计

### 1. 跨尺度一致性检验

气固界面研究的关键挑战：不同尺度的模型需要给出一致的结论。

**我们的方法**：建立跨尺度一致性指标

```python
class CrossScaleConsistencyChecker:
    """跨尺度一致性检验器"""

    def __init__(self):
        self.scale_models = {
            "continuum": "Navier-Stokes + 飞行器尺度边界层模型",
            "transition": "DSMC 或 Boltzmann 方程求解器",
            "free_molecular": "自由分子流理论"
        }

        # 一致性阈值（Kn 数区间）
        self.consistency_thresholds = {
            "continuum_to_transition": {"Kn": (0.01, 0.1), "max_deviation": 0.15},
            "transition_to_free_molecular": {"Kn": (10, 100), "max_deviation": 0.20}
        }

    def check_consistency(
        self,
        continuum_results: list[dict],
        transition_results: list[dict],
        free_molecular_results: list[dict]
    ) -> dict:
        """
        检验跨尺度结果的一致性

        Args:
            continuum_results: 连续介质模型结果
            transition_results: 过渡区模型结果
            free_molecular_results: 自由分子流结果

        Returns:
            一致性检验报告
        """
        report = {
            "consistency_checks": [],
            "overall_consistency": True,
            "recommendations": []
        }

        # 1. 连续介质 ↔ 过渡区 一致性检验
        check1 = self._check_two_scale_consistency(
            continuum_results,
            transition_results,
            "continuum",
            "transition"
        )
        report["consistency_checks"].append(check1)

        # 2. 过渡区 ↔ 自由分子流 一致性检验
        check2 = self._check_two_scale_consistency(
            transition_results,
            free_molecular_results,
            "transition",
            "free_molecular"
        )
        report["consistency_checks"].append(check2)

        # 3. 综合评估
        report["overall_consistency"] = all(
            c["is_consistent"] for c in report["consistency_checks"]
        )

        # 4. 生成建议
        if not report["overall_consistency"]:
            report["recommendations"] = self._generate_recommendations(
                report["consistency_checks"]
            )

        return report

    def _check_two_scale_consistency(
        self,
        results1: list[dict],
        results2: list[dict],
        scale1: str,
        scale2: str
    ) -> dict:
        """
        检验两个尺度模型的一致性
        """
        # 找到重叠区域（Kn 数范围）
        overlap_results = self._find_overlap_region(results1, results2)

        if not overlap_results:
            return {
                "scales": [scale1, scale2],
                "is_consistent": None,
                "reason": "无重叠区域，无法检验一致性"
            }

        # 计算相对偏差
        deviations = []
        for r1, r2 in overlap_results:
            q1 = r1["heat_flux"]
            q2 = r2["heat_flux"]
            deviation = abs(q1 - q2) / max(q1, q2)
            deviations.append(deviation)

        # 评估一致性
        max_dev = max(deviations)
        avg_dev = sum(deviations) / len(deviations)

        is_consistent = max_dev < 0.15  # 15% 阈值

        return {
            "scales": [scale1, scale2],
            "is_consistent": is_consistent,
            "max_deviation": max_dev,
            "avg_deviation": avg_dev,
            "overlap_region": {
                "Kn_min": min(r["Kn"] for r, _ in overlap_results),
                "Kn_max": max(r["Kn"] for r, _ in overlap_results)
            }
        }
```

---

### 2. 物理量完整性检验

确保仿真结果包含所有必需的物理量，且满足守恒律。

```python
class PhysicsCompletenessChecker:
    """物理量完整性检验器"""

    def __init__(self):
        self.required_quantities = {
            "heat_flux": "驻点热流密度 (W/m²)",
            "temperature_wall": "壁面温度 (K)",
            "temperature_gtw": "气固界面温度 (K)",
            "pressure_wall": "壁面压力 (Pa)",
            "catalytic_efficiency": "催化效率 (-)",
            "knudsen": "克努森数 (-)",
            "mach": "马赫数 (-)"
        }

        self.conservation_laws = {
            "energy": "能量守恒：输入焓 = 对流热 + 辐射热 + 壁面吸热",
            "mass": "质量守恒：入流质量 = 壁面催化消耗 + 出流质量",
            "momentum": "动量守恒：动量输入 = 阻力 + 壁面动量传递"
        }

    def check_completeness(self, result: dict) -> dict:
        """
        检验物理量完整性
        """
        missing = []
        present = []

        for q, desc in self.required_quantities.items():
            if q not in result:
                missing.append((q, desc))
            else:
                present.append(q)

        # 守恒律检验
        conservation_violations = self._check_conservation(result)

        return {
            "is_complete": len(missing) == 0,
            "present_quantities": present,
            "missing_quantities": missing,
            "conservation_violations": conservation_violations,
            "completeness_score": len(present) / len(self.required_quantities)
        }

    def _check_conservation(self, result: dict) -> list[str]:
        """
        检验守恒律（简化版）
        """
        violations = []

        # 能量守恒：q_w = h_re - h_w（简化）
        if all(k in result for k in ["heat_flux", "enthalpy_recovery", "enthalpy_wall"]):
            q_calc = result["enthalpy_recovery"] - result["enthalpy_wall"]
            q_actual = result["heat_flux"]

            if abs(q_calc - q_actual) / max(q_calc, q_actual) > 0.1:  # 10% 阈值
                violations.append("能量守恒偏差 > 10%")

        return violations
```

---

## 核心流程

```
输入：实验数据 + 原始假设 + 物理约束
         ↓
┌──────────────────────────────────────┐
│ Step 1: 数据质量检验                 │
│   - 物理量完整性检验                 │
│   - 守恒律检验                       │
│   - 异常值检测                       │
└──────────────────┬───────────────────┘
                   ↓
┌──────────────────────────────────────┐
│ Step 2: 统计分析                     │
│   - 显著性检验（t-test, ANOVA）      │
│   - 相关性分析（Pearson, Spearman）  │
│   - 误差分析（RMSE, MAE, R²）        │
└──────────────────┬───────────────────┘
                   ↓
┌──────────────────────────────────────┐
│ Step 3: 跨尺度一致性检验             │
│   - 连续 ↔ 过渡 ↔ 自由分子          │
│   - 识别不一致区域                   │
│   - 生成修正建议                     │
└──────────────────┬───────────────────┘
                   ↓
┌──────────────────────────────────────┐
│ Step 4: 自动化可视化                 │
│   - 参数扫描图（热流 vs Ma/H/γ）     │
│   - 相图（不同工况的边界）           │
│   - 一致性对比图                     │
└──────────────────┬───────────────────┘
                   ↓
输出：统计结论 + 可视化 + 一致性报告
```

---

## Prompt 模板

```python
RESULT_ANALYSIS_PROMPT = """
你是一名高超声速气固界面耦合结果分析专家。

# 原始假设
{hypothesis}

# 实验数据
{experiment_data}

# 物理约束
{physics_constraints}

# 任务
1. 检验数据质量（物理量完整性、守恒律）
2. 进行统计分析（显著性、相关性、误差分析）
3. 检验跨尺度一致性（如果有多尺度数据）
4. 自动化可视化
5. 总结实验结论

# 分析框架
1. 假设验证：
   - 假设预测值 vs 实验结果
   - 预测误差分析
   - 假设是否被支持

2. 统计分析：
   - 显著性检验（p < 0.05）
   - 效应量（Cohen's d）
   - 置信区间（95%）

3. 跨尺度一致性：
   - 连续 ↔ 过渡区偏差
   - 过渡区 ↔ 自由分子流偏差
   - 识别不一致区域

4. 可视化建议：
   - 参数扫描图
   - 相图
   - 一致性对比图

# 输出格式（JSON）
{
  "data_quality": {
    "is_complete": true,
    "completeness_score": 0.9,
    "conservation_violations": []
  },
  "hypothesis_validation": {
    "prediction": "预测值",
    "experimental_value": "实验值",
    "relative_error": 0.12,
    "is_supported": true
  },
  "statistical_analysis": {
    "significant": true,
    "p_value": 0.003,
    "effect_size": 0.8,
    "confidence_interval": [0.05, 0.15]
  },
  "cross_scale_consistency": {
    "is_consistent": true,
    "max_deviation": 0.08,
    "critical_regions": []
  },
  "conclusion": "实验结论",
  "next_steps": ["下一步建议"],
  "visualization_specs": [
    {
      "type": "parameter_scan",
      "x_axis": "Ma",
      "y_axis": "heat_flux",
      "color_by": "gamma"
    }
  ]
}
"""
```

---

## 示例输出

```json
{
  "data_quality": {
    "is_complete": true,
    "completeness_score": 1.0,
    "conservation_violations": []
  },
  "hypothesis_validation": {
    "prediction": "修正模型在 2000-2500K 区域的 RMS 误差从 0.35 降低至 < 0.15",
    "experimental_value": "RMS 误差 = 0.12",
    "relative_error": 0.20,
    "is_supported": true
  },
  "statistical_analysis": {
    "significant": true,
    "p_value": 0.001,
    "effect_size": 1.2,
    "confidence_interval": [0.08, 0.16]
  },
  "cross_scale_consistency": {
    "is_consistent": true,
    "max_deviation": 0.07,
    "critical_regions": []
  },
  "conclusion": "引入表面温度依赖的吸附能修正可显著提升 2000-2500K 区域的催化复合系数预测精度，跨尺度一致性检验通过，假设得到验证。",
  "next_steps": [
    "扩展温度范围至 2500-3000K 验证外推能力",
    "补充不同材料（SiC, Al2O3）的实验验证"
  ],
  "visualization_specs": [
    {
      "type": "parameter_scan",
      "x_axis": "Temperature_K",
      "y_axis": "gamma",
      "series": ["baseline", "corrected"]
    }
  ]
}
```

---

## 与现有工具的集成

```python
class ResultAnalyzer(Action):
    """结果分析器工具"""

    name = "analyze_results"
    description = "分析实验数据，生成统计结论和可视化"
    parameters = {
        "type": "object",
        "properties": {
            "data_path": {"type": "string", "description": "实验数据文件路径"},
            "hypothesis": {"type": "string", "description": "JSON 格式的假设信息"}
        },
        "required": ["data_path"]
    }

    def __init__(self, llm: LLMInterface):
        self.llm = llm
        self.quality_checker = PhysicsCompletenessChecker()
        self.consistency_checker = CrossScaleConsistencyChecker()
        self.visualizer = ResultVisualizer()

    async def run(self, data_path: str, hypothesis: str = None) -> str:
        # 1. 加载数据
        data = self._load_data(data_path)

        # 2. 数据质量检验
        quality_report = self.quality_checker.check_completeness(data)

        if not quality_report["is_complete"]:
            return json.dumps({
                "error": "数据不完整",
                "details": quality_report["missing_quantities"]
            }, indent=2)

        # 3. 跨尺度一致性检验（如果有多个尺度）
        consistency_report = self._check_cross_scale(data)

        # 4. 构建 prompt
        prompt = RESULT_ANALYSIS_PROMPT.format(
            hypothesis=hypothesis or "{}",
            experiment_data=json.dumps(data, indent=2),
            physics_constraints=self._get_physics_constraints()
        )

        # 5. LLM 分析
        response = await self.llm.chat([Message.user(prompt)])
        analysis = json.loads(response.content)

        # 6. 融合检验报告
        analysis["data_quality"] = quality_report
        analysis["cross_scale_consistency"] = consistency_report

        # 7. 生成可视化
        figures = self.visualizer.generate_plots(
            analysis["visualization_specs"], data
        )

        # 8. 保存结果
        report_path = self._save_report(analysis, figures)

        return json.dumps({
            "analysis": analysis,
            "figures": figures,
            "report_path": report_path
        }, indent=2, ensure_ascii=False)
```

---

## 评测指标

| 指标 | 定义 | 目标值 |
|------|------|--------|
| **异常检测准确率** | 识别异常数据的准确率 | ≥ 90% |
| **一致性检验覆盖率** | 多尺度数据的一致性检验覆盖率 | ≥ 80% |
| **统计显著性正确率** | 正确识别显著/不显著结果的比例 | ≥ 85% |
| **可视化有效性** | 生成图表能清晰展示关键信息的比例 | ≥ 90% |

---

## 参考文献（设计参考）

- [AutoGPT for Data Science](https://github.com/jerryjliu/llama_index/tree/main/llama-index-packs/autogpt-data-science) — 数据分析 Agent 设计
- [Nature: Statistical Analysis Automation](https://www.nature.com/articles/s42256-024-00837-w) — 统计分析方法
- [Cross-Scale Modeling in Hypersonics](https://arxiv.org/abs/2305.08987) — 跨尺度建模理论