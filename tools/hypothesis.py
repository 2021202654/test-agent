"""
假设生成器 —— AI Scientist 核心模块

从文献 Gap 到可验证科学假设，融入物理方程约束验证。
流程：文献检索 → Gap 识别 → 假设生成 → 物理约束验证 → 评分排序
"""

from __future__ import annotations

import json
from typing import Any

from core.action import Action
from core.llm import LLMInterface
from core.message import Message
from .physics_constraints import PhysicsConstraintLayer
from .search import LiteratureSearchTool
from .web_search import WebSearchTool


# ── Prompt 模板 ──────────────────────────────────────

HYPOTHESIS_GENERATION_PROMPT = """\
你是高超声速气固界面耦合领域的假设生成专家。基于文献综述识别研究Gap，生成可验证假设。

# 文献综述
{literature_review}

# 已知知识边界
{knowledge_boundary}

# 物理约束
{physics_constraints}

# Gap 识别框架
- L1 矛盾点：不同文献对同一现象给出矛盾结论
- L2 未覆盖区域：参数范围或工况缺乏数据
- L3 过度简化：模型忽略重要物理效应
- L4 跨尺度不一致：连续介质假设在稀薄区失效

# 要求
- 假设必须可验证、符合物理定律、有明确成功判据
- description 控制在50字以内，evidence 最多2条，hypothesis 控制在80字以内
- 输出严格 JSON，不要任何额外文字

# 输出格式
{{
  "gap_analysis": [
    {{
      "level": 1,
      "description": "Gap简述（≤50字）",
      "evidence": ["证据1"],
      "hypotheses": [
        {{
          "hypothesis": "假设（≤80字）",
          "prediction": "预测（数值或趋势）",
          "validation_method": "验证方法",
          "innovation_score": 80,
          "feasibility_score": 80,
          "scientific_value_score": 80
        }}
      ]
    }}
  ]
}}
"""


# ── 假设生成器工具 ──────────────────────────────────


class HypothesisGenerator(Action):
    """假设生成器 —— 基于文献 Gap 生成可验证的科学假设。

    AI Scientist 的核心入口。从被动问答跃迁到主动假设生成。
    """

    name = "generate_hypothesis"
    description = (
        "基于气固热导领域文献，识别研究 Gap 并生成可验证的科学假设。"
        "支持 4 级 Gap 识别（矛盾/未覆盖/过度简化/跨尺度不一致），"
        "自动进行物理约束验证（催化效率、Kn数、守恒律等），"
        "输出结构化假设列表（含创新性/可行性/科学价值评分）。"
        "输入研究主题关键词，返回排序后的假设。"
    )
    parameters = {
        "type": "object",
        "properties": {
            "topic": {
                "type": "string",
                "description": (
                    "研究主题关键词，英文。"
                    "例如: 'catalytic recombination modeling gap', "
                    "'gas-surface interaction Knudsen transition', "
                    "'TPS material comparison'"
                ),
            },
            "max_hypotheses": {
                "type": "integer",
                "description": "最大假设数量，默认5，最多10",
                "default": 5,
            },
            "gap_level": {
                "type": "integer",
                "description": "Gap 层级过滤：0=全部，1=矛盾，2=未覆盖，3=过度简化，4=跨尺度",
                "default": 0,
            },
        },
        "required": ["topic"],
    }

    def __init__(
        self,
        llm: LLMInterface,
        search_tool: LiteratureSearchTool | None = None,
        web_tool: WebSearchTool | None = None,
    ):
        """构造器注入 LLM 实例和可选的检索工具。

        Args:
            llm: LLM 接口，用于 Gap 分析和假设生成
            search_tool: 本地文献检索工具，None 则内部创建
            web_tool: OpenAlex 外部检索工具，None 则内部创建
        """
        # 假设生成需要更长的输出，创建专用 LLM 实例（max_tokens=4096）
        from core.llm import LLMConfig
        self.llm = llm
        hyp_config = LLMConfig(
            base_url=llm.config.base_url,
            api_key=llm.config.api_key,
            model=llm.config.model,
            temperature=llm.config.temperature,
            max_tokens=8192,  # 假设生成 JSON 较长，需要充足空间
            timeout=llm.config.timeout,
        )
        self._hypothesis_llm = LLMInterface(hyp_config)
        self.search_tool = search_tool or LiteratureSearchTool()
        self.web_tool = web_tool or WebSearchTool()
        self.physics = PhysicsConstraintLayer()

    # ── 主入口 ────────────────────────────────────

    async def run(self, topic: str, max_hypotheses: int = 5, gap_level: int = 0) -> str:
        """执行假设生成流程。"""
        max_hypotheses = min(max_hypotheses, 10)
        gap_level = max(0, min(gap_level, 4))

        # Step 1: 本地文献检索
        try:
            lit_results = await self.search_tool.run(query=topic, top_k=10)
        except Exception as e:
            lit_results = f"[文献检索异常] {e}"

        # Step 2: OpenAlex 补充最新研究
        try:
            web_results = await self.web_tool.run(query=topic)
        except Exception as e:
            web_results = f"[OpenAlex 检索异常] {e}"

        # Step 3: 组装文献综述
        literature_review = f"## 本地文献库检索结果\n{lit_results}\n\n## OpenAlex 最新研究\n{web_results}"

        # Step 4: 构建 prompt
        knowledge_boundary = self._build_knowledge_boundary(topic)
        physics_constraints = self.physics.format_constraints_brief()

        prompt = HYPOTHESIS_GENERATION_PROMPT.format(
            literature_review=literature_review,
            knowledge_boundary=knowledge_boundary,
            physics_constraints=physics_constraints,
        )

        # Step 5: LLM 生成假设（使用专用长输出实例）
        try:
            response = await self._hypothesis_llm.chat([Message.user(prompt)])
            raw_content = response.content
        except Exception as e:
            return json.dumps(
                {"error": f"LLM 调用失败: {e}", "literature_review": literature_review},
                indent=2,
                ensure_ascii=False,
            )

        # Step 6: 解析 LLM 输出
        parsed = self._parse_llm_output(raw_content)

        # Step 7: 物理约束验证
        parsed = self._validate_with_physics(parsed)

        # Step 8: Gap 层级过滤
        if gap_level > 0:
            parsed = self._filter_by_gap_level(parsed, gap_level)

        # Step 9: 截断并排序
        parsed = self._rank_and_truncate(parsed, max_hypotheses)

        # Step 10: 格式化输出
        return self._format_output(parsed, topic)

    # ── 内部方法 ──────────────────────────────────

    def _build_knowledge_boundary(self, topic: str) -> str:
        """构建已知知识边界描述（精简版）。"""
        return (
            f"主题：{topic}\n"
            "已知边界：γ ∈ [0,1]; σ_v,σ_T ∈ [0,1]; 连续流 Kn<0.01; "
            "Fay-Riddell 仅适用平衡催化壁面; 高超声速 Ma∈[5,30]; "
            "TPS材料: SiO₂,SiC,Al₂O₃,C-Phenolic,RCG; T>2000K 高温效应显著"
        )

    def _parse_llm_output(self, raw: str) -> dict[str, Any]:
        """解析 LLM 输出为 JSON。支持截断 JSON 修复。"""
        # 尝试提取 JSON 块
        text = raw.strip()

        # 去掉 markdown 代码块包裹
        if text.startswith("```"):
            lines = text.split("\n")
            # 去首尾 ```行
            lines = [l for l in lines if not l.strip().startswith("```")]
            text = "\n".join(lines)

        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        # 尝试找 JSON 花括号范围
        start = text.find("{")
        end = text.rfind("}") + 1
        if start >= 0 and end > start:
            try:
                return json.loads(text[start:end])
            except json.JSONDecodeError:
                pass

        # 尝试修复截断的 JSON：补全未闭合的括号
        if start >= 0:
            snippet = text[start:]
            repaired = self._repair_json(snippet)
            if repaired is not None:
                return repaired

        # 解析失败，返回原始文本
        return {
            "gap_analysis": [],
            "raw_output": text,
            "parse_error": "LLM 输出无法解析为 JSON",
        }

    def _repair_json(self, snippet: str) -> dict[str, Any] | None:
        """尝试修复截断的 JSON（补全括号）。"""
        # 计算未闭合的括号
        open_braces = snippet.count("{") - snippet.count("}")
        open_brackets = snippet.count("[") - snippet.count("]")

        if open_braces < 0 or open_brackets < 0:
            return None  # 括号多了，不是简单截断

        # 补全：先关闭未完成的字符串，再关闭括号
        repaired = snippet.rstrip()

        # 尝试在最后一个完整的值后截断，补全括号
        # 去掉最后一个不完整的键值对
        for trim_pattern in [",\n", ",\r\n", ",", "\n", "\r\n"]:
            idx = repaired.rfind(trim_pattern)
            if idx > 0:
                repaired = repaired[:idx]
                break

        # 补全未闭合的引号
        if repaired.count('"') % 2 != 0:
            repaired += '"'

        # 补全括号
        repaired += "]" * max(0, open_brackets)
        repaired += "}" * max(0, open_braces)

        try:
            return json.loads(repaired)
        except json.JSONDecodeError:
            return None

    def _validate_with_physics(self, parsed: dict[str, Any]) -> dict[str, Any]:
        """用物理约束验证每个假设。"""
        for gap in parsed.get("gap_analysis", []):
            for hyp in gap.get("hypotheses", []):
                # 收集参数
                params = {}
                for p in hyp.get("parameters", []):
                    if p.get("value") is not None:
                        params[p["name"]] = p["value"]

                # 验证
                valid, reason = self.physics.validate_hypothesis(
                    hyp.get("hypothesis", ""), params
                )
                hyp["physics_validation"] = {
                    "valid": valid,
                    "reason": reason,
                }

        return parsed

    def _filter_by_gap_level(self, parsed: dict[str, Any], gap_level: int) -> dict[str, Any]:
        """按 Gap 层级过滤。"""
        filtered = [
            gap for gap in parsed.get("gap_analysis", [])
            if gap.get("level") == gap_level
        ]
        parsed["gap_analysis"] = filtered
        return parsed

    def _rank_and_truncate(self, parsed: dict[str, Any], max_h: int) -> dict[str, Any]:
        """评分排序并截断。"""
        all_hypotheses = []

        for gap_idx, gap in enumerate(parsed.get("gap_analysis", [])):
            for hyp_idx, hyp in enumerate(gap.get("hypotheses", [])):
                # 综合评分 = 加权平均
                inn = hyp.get("innovation_score", 50)
                fea = hyp.get("feasibility_score", 50)
                sci = hyp.get("scientific_value_score", 50)
                # 权重：创新 0.35 + 可行 0.30 + 价值 0.35
                composite = 0.35 * inn + 0.30 * fea + 0.35 * sci

                # 物理验证未通过则降权
                if not hyp.get("physics_validation", {}).get("valid", True):
                    composite *= 0.5

                hyp["composite_score"] = round(composite, 1)
                hyp["_gap_idx"] = gap_idx
                hyp["_hyp_idx"] = hyp_idx
                all_hypotheses.append(hyp)

        # 按综合评分降序
        all_hypotheses.sort(key=lambda h: h.get("composite_score", 0), reverse=True)

        # 截断
        parsed["ranked_hypotheses"] = all_hypotheses[:max_h]

        # 更新 top_hypothesis_index
        if all_hypotheses:
            top = all_hypotheses[0]
            parsed["top_hypothesis_index"] = {
                "gap": top.get("_gap_idx", 0),
                "hypothesis": top.get("_hyp_idx", 0),
                "composite_score": top.get("composite_score", 0),
            }

        return parsed

    def _format_output(self, parsed: dict[str, Any], topic: str) -> str:
        """格式化输出为人类可读 + JSON 混合格式。"""
        # 如果解析失败，返回干净的摘要（不输出截断 JSON，避免污染 LLM 上下文）
        if "parse_error" in parsed:
            raw = parsed.get("raw_output", "")
            # 提取已成功解析的部分做摘要
            preview = raw[:300].replace("\n", " ") if raw else ""
            return (
                f"⚠️ 假设生成遇到问题：{parsed['parse_error']}。LLM 输出可能被截断，"
                f"建议缩小检索范围或减少 max_hypotheses。"
                f"\n\n📋 输出预览（前300字符）：{preview}..."
                f"\n\n🔧 请调整 topic 参数或降低 max_hypotheses 后重试。"
            )

        # 人类可读摘要
        lines = [f"🔬 假设生成报告 —— {topic}\n"]

        gap_analysis = parsed.get("gap_analysis", [])
        lines.append(f"识别到 {len(gap_analysis)} 个研究 Gap：\n")

        for i, gap in enumerate(gap_analysis):
            level = gap.get("level", "?")
            desc = gap.get("description", "无描述")
            evidence = gap.get("evidence", [])
            level_labels = {1: "矛盾点", 2: "未覆盖区域", 3: "过度简化", 4: "跨尺度不一致"}
            level_label = level_labels.get(level, f"Level {level}")

            lines.append(f"### Gap {i+1}（{level_label}）")
            lines.append(f"{desc}")
            if evidence:
                lines.append(f"证据：{'；'.join(evidence[:3])}")
            lines.append("")

            for j, hyp in enumerate(gap.get("hypotheses", [])):
                score = hyp.get("composite_score", "N/A")
                valid = hyp.get("physics_validation", {}).get("valid", True)
                status = "✅" if valid else "⚠️"
                lines.append(f"  {status} 假设 {j+1}（综合评分: {score}）")
                lines.append(f"  {hyp.get('hypothesis', '—')}")
                lines.append(f"  预测：{hyp.get('prediction', '—')}")
                lines.append(f"  验证方法：{hyp.get('validation_method', '—')}")
                if not valid:
                    reason = hyp.get("physics_validation", {}).get("reason", "")
                    lines.append(f"  ⚠️ 物理约束警告：{reason}")
                lines.append("")

        # 排序后的 Top 假设
        ranked = parsed.get("ranked_hypotheses", [])
        if ranked:
            lines.append("---")
            lines.append(f"🏆 Top {len(ranked)} 假设（按综合评分排序）：\n")
            for i, hyp in enumerate(ranked):
                score = hyp.get("composite_score", 0)
                valid = hyp.get("physics_validation", {}).get("valid", True)
                status = "✅" if valid else "⚠️"
                lines.append(f"{i+1}. {status} [{score}] {hyp.get('hypothesis', '—')}")
                lines.append(f"   预测：{hyp.get('prediction', '—')}")
            lines.append("")

        # 追加原始 JSON（供下游解析）
        lines.append("---")
        lines.append("📊 结构化数据（JSON）：")
        # 清理内部字段
        clean = self._clean_for_output(parsed)
        lines.append(json.dumps(clean, indent=2, ensure_ascii=False))

        return "\n".join(lines)

    def _clean_for_output(self, parsed: dict[str, Any]) -> dict[str, Any]:
        """清理内部字段，输出干净 JSON。"""
        clean = {
            "gap_analysis": [],
            "ranked_hypotheses": [],
        }

        for gap in parsed.get("gap_analysis", []):
            gap_clean = {
                "level": gap.get("level"),
                "description": gap.get("description"),
                "evidence": gap.get("evidence", []),
                "hypotheses": [],
            }
            for hyp in gap.get("hypotheses", []):
                hyp_clean = {k: v for k, v in hyp.items() if not k.startswith("_")}
                gap_clean["hypotheses"].append(hyp_clean)
            clean["gap_analysis"].append(gap_clean)

        for hyp in parsed.get("ranked_hypotheses", []):
            hyp_clean = {k: v for k, v in hyp.items() if not k.startswith("_")}
            clean["ranked_hypotheses"].append(hyp_clean)

        if "top_hypothesis_index" in parsed:
            clean["top_hypothesis_index"] = parsed["top_hypothesis_index"]

        return clean
