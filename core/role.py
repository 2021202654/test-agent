"""
Role 类 —— 仿 MetaGPT Role，Agent 的身份与行为核心

每个 Role = 一个 Agent 身份，包含：
- 身份定义: name, profile, goal, constraints
- 能力: actions（可调用的工具）
- 记忆: memory（短期 + 工作 + 长期）
- 生命周期: _observe() → _think() → _act()

与 MetaGPT 的差异：
- 去掉了 publish_message / Environment 多 Agent 通信
- 去掉了 _watch 订阅机制
- react() 改为单次任务驱动的 run() 方法
"""

from __future__ import annotations

from .action import ActionRegistry
from .memory import Memory, Message


class Role:
    """Agent 角色基类。

    最简用法：
        role = Role(
            name="AeroThermalExpert",
            profile="高超声速气固界面耦合研究专家",
            goal="辅助研究者进行文献检索、多步推理、证据合成",
        )
        role.equip(SearchAction())
        role.equip(ComputeAction())
    """

    def __init__(
        self,
        name: str,
        profile: str = "",
        goal: str = "",
        constraints: list[str] | None = None,
    ):
        self.name = name
        self.profile = profile
        self.goal = goal
        self.constraints = constraints or []

        # 能力
        self.registry = ActionRegistry()

        # 记忆
        self.memory = Memory()

        # 状态
        self._initialized = False

    # ── 工具装配 ────────────────────────────────────

    def equip(self, action) -> "Role":
        """装备一个工具到 Agent。"""
        from .action import Action

        self.registry.register(action)
        return self

    def equip_many(self, actions: list) -> "Role":
        self.registry.register_many(actions)
        return self

    # ── System Prompt ───────────────────────────────

    def build_system_prompt(self) -> str:
        """根据身份信息构建 system prompt。"""
        lines = []
        if self.profile:
            lines.append(f"你是 {self.name}，{self.profile}。")
        if self.goal:
            lines.append(f"你的目标是：{self.goal}")
        if self.constraints:
            lines.append("你必须遵守以下约束：")
            for c in self.constraints:
                lines.append(f"- {c}")

        lines.append("\n## 可用工具")
        lines.append("- 检索文献: search_literature (本地), web_search (OpenAlex)")
        lines.append("- 气动热参数计算: compute_aerothermal")
        lines.append("- 代码执行: execute_python")
        lines.append("- 引文解析/PDF/报告/导出: resolve_citation, parse_pdf, generate_report, export_finding")
        lines.append("")
        lines.append("## 关键规则")
        lines.append("1. **工具数据优先**: 当工具返回的数值与你训练数据中的\"记忆\"冲突时, 必须信任工具返回的结果。")
        lines.append("   你的训练数据可能过时或错误，而工具内置了经过验证的文献参数。")
        lines.append("2. **不要编造引用**: 报告编号(NASA CR-xxxx)、DOI、论文标题必须来自工具的实际返回结果, 绝对不能凭记忆填写。")
        lines.append("   如果工具返回结果中没有DOI，不允许向用户呈现为\"已找到的文献\"——必须明确告知用户该文献无DOI或未找到。")
        lines.append("   如果你不确定某个引用是否准确, 调用 resolve_citation 或 web_search 验证。")
        lines.append("3. **参数溯源强制规则**: 用户提供的数值参数（如γ₀=0.05、热流密度、Mach数等）必须经过工具计算验证才能用于结论。")
        lines.append("   绝对流程：用户给参数 → 调用 compute_aerothermal 验证 → 基于工具输出给结论。")
        lines.append("   禁止：用户给参数 → 直接在文字中引用（不经工具）→ 幻觉风险。")
        lines.append("4. **区分计算与事实**: 所有的计算结果必须标注为\"基于假设参数的条件计算\", 不能表述为\"文献确认值\"。")
        lines.append("5. **不要过度外推**: 两个数据点不能外推出定量工程结论(如热流增量百分比)。需要外推时必须明确标注假设链。")
        lines.append("6. **物种/表面/条件必须明确**: 催化复合系数依赖复合物种(O/N)、表面类型(石英/RCG/SiC)、实验条件。")
        lines.append("   不指定这些条件就不能声称某个 gamma 值是\"该材料的催化复合系数\"。")
        lines.append("7. **写 Python 代码时**: 优先使用工具 compute_aerothermal 获取参数, 不要直接硬编码你\"记得\"的公式参数。")
        lines.append("   若确需在代码中使用经验公式, 必须在注释中标注参数来源和不确定性。")
        lines.append('8. **工具返回的警告/不确定性声明必须传递给用户**: 如果工具结果包含"不可用于工程设计"、"高度依赖"、"估计值"等声明，')
        lines.append("   你不得将其隐藏或改写为确定结论。必须在回答中原文保留该警告。")
        lines.append("9. **得出研究结论后**, 务必调用 generate_report 保存为 Markdown 报告。")
        lines.append("   研究过程中可随时调用 export_finding 记录中间发现。")
        lines.append("10. **仅在信息充足时给出最终回答, 不要编造数据。**")
        lines.append("11. **公式名称必须与工具返回完全一致**: 如果工具输出写的是「Sutton-Graves 简化式」，报告或回答中不得写成「Fay-Riddell公式」或任何其他名称。")
        lines.append("    工具返回什么名称，报告就用什么名称——禁止 LLM 自由选择或混用公式名称。")
        lines.append("12. **补充性数据必须标注来源**: 报告中引用的工具输出以外的数据（如 Apollo 实测热流范围、具体实验参数等），")
        lines.append("    必须明确标注「来源：模型训练数据推测」或「来源：web_search 检索 DOI: xxx」。")
        lines.append("    绝对禁止：工具未返回的数据，LLM 直接引用但不说明来源。无法提供 DOI 的引用一律标注为「非工具返回」。")

        return "\n".join(lines)

    def system_message(self) -> Message:
        return Message.system(self.build_system_prompt())

    # ── 描述信息 ─────────────────────────────────────

    def describe(self) -> str:
        return (
            f"Role: {self.name}\n"
            f"Profile: {self.profile}\n"
            f"Goal: {self.goal}\n"
            f"Actions: {self.registry.list_names()}\n"
            f"Constraints: {self.constraints}"
        )
