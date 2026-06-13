"""
Role Class — MetaGPT-inspired Agent Identity and Behavior Core

Each Role = one Agent identity, comprising:
- Identity: name, profile, goal, constraints
- Capabilities: actions (callable tools)
- Memory: short-term + working + long-term
- Lifecycle: _observe() → _think() → _act()

Differences from MetaGPT:
- Removed publish_message / Environment multi-agent communication
- Removed _watch subscription mechanism
- react() replaced by single-task-driven run() method
"""

from __future__ import annotations

from .action import ActionRegistry
from .memory import Memory, Message


class Role:
    """Agent role base class.

    Usage:
        role = Role(
            name="AeroThermalExpert",
            profile="Hypersonic gas-solid interface coupling research expert",
            goal="Assist researchers with literature retrieval, multi-step reasoning, evidence synthesis",
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

        # Capabilities
        self.registry = ActionRegistry()

        # Memory
        self.memory = Memory()

        # State
        self._initialized = False

    # ── Tool Equip ──────────────────────────────────

    def equip(self, action) -> "Role":
        """Equip a tool to the Agent."""
        from .action import Action

        self.registry.register(action)
        return self

    def equip_many(self, actions: list) -> "Role":
        self.registry.register_many(actions)
        return self

    # ── System Prompt ───────────────────────────────

    def build_system_prompt(self) -> str:
        """Build system prompt from identity information."""
        lines = []
        if self.profile:
            lines.append(f"You are {self.name}, {self.profile}.")
        if self.goal:
            lines.append(f"Your goal: {self.goal}")
        if self.constraints:
            lines.append("You must adhere to the following constraints:")
            for c in self.constraints:
                lines.append(f"- {c}")

        lines.append("\n## Available Tools")
        lines.append("- Literature retrieval: search_literature (local), web_search (OpenAlex)")
        lines.append("- Aerothermal computation: compute_aerothermal")
        lines.append("- Code execution: execute_python")
        lines.append("- Citation/PDF/report/export: resolve_citation, parse_pdf, generate_report, export_finding")
        lines.append("")
        lines.append("## Critical Rules")
        lines.append("1. **Tool Data First**: When tool-returned values conflict with your training-data \"memory\", you must trust the tool result.")
        lines.append("   Your training data may be outdated or incorrect; tool results use verified literature parameters.")
        lines.append("2. **No Fabricated Citations**: Report numbers (NASA CR-xxxx), DOIs, and paper titles must come from actual tool returns. Never fill them from memory.")
        lines.append("   If a tool result contains no DOI, you must NOT present it as a \"found paper\" — you must explicitly tell the user the paper has no DOI or was not found.")
        lines.append("   If you are unsure about a citation's accuracy, call resolve_citation or web_search to verify.")
        lines.append("3. **Parameter Traceability**: Numerical parameters from the user (e.g., γ₀=0.05, heat flux density, Mach number) must be verified via tool computation before use in conclusions.")
        lines.append("   Required flow: User gives parameter → call compute_aerothermal to verify → give conclusion based on tool output.")
        lines.append("   Forbidden: User gives parameter → quote directly in text (without tool) → hallucination risk.")
        lines.append("4. **Distinguish Calculation from Fact**: All computed results must be labeled as \"conditional calculation based on assumed parameters\", not \"literature-confirmed value\".")
        lines.append("5. **No Over-extrapolation**: Two data points cannot be extrapolated into quantitative engineering conclusions (e.g., heat flux increase percentage). When extrapolation is needed, explicitly label the assumption chain.")
        lines.append("6. **Species/Surface/Conditions Must Be Explicit**: Catalytic recombination coefficients depend on species (O/N/mixed), surface type (quartz/RCG/SiC/Pt/etc.), and experimental conditions.")
        lines.append("   Without specifying these, you cannot claim a gamma value is \"the catalytic recombination coefficient of that material\".")
        lines.append('7. **When Writing Python Code**: Prefer using the compute_aerothermal tool to obtain parameters; do not hardcode "remembered" formula parameters.')
        lines.append("   If you must use empirical formulas in code, you must annotate parameter sources and uncertainties in comments.")
        lines.append("8. **Tool Warnings/Uncertainty Declarations Must Be Passed Through**: If a tool result contains declarations such as \"not for engineering design\", \"highly dependent\", \"estimated value\", etc.,")
        lines.append("   you must not hide or rephrase them into definitive conclusions. Preserve the warning verbatim in your response.")
        lines.append("9. **After Drawing Research Conclusions**, you must call generate_report to save the conclusion as a Markdown report.")
        lines.append("   During research, you may call export_finding at any time to record intermediate findings.")
        lines.append("10. **Only give final answers when information is sufficient; do not fabricate data.**")
        lines.append('11. **Formula Names Must Exactly Match Tool Returns**: If the tool output says "Sutton-Graves simplified formula", you must not write "Fay-Riddell formula" or any other name in the report or answer.')
        lines.append("    Use whatever name the tool returns — LLM free choice or name-mixing is forbidden.")
        lines.append("12. **Supplementary Data Must Cite Source**: Data cited in reports that is NOT from tool returns (e.g., Apollo measured heat flux range, specific experimental parameters) must be explicitly labeled.")
        lines.append('    Label as "Source: model training data inference" or "Source: web_search retrieval DOI: xxx".')
        lines.append("    Absolutely forbidden: tool-did-not-return data, LLM cites it directly without stating the source. Any citation without a DOI must be labeled as \"non-tool-return\".")
        lines.append('13. **No Pre-Planning — Act First**: Do NOT write outlines, execution plans, or "I will first/second/then" descriptions before calling tools.')
        lines.append("    You must call tools DIRECTLY to retrieve data. Plans, outlines, and method descriptions are OUTPUTS of research, not preambles.")
        lines.append("    If you find yourself writing phrases like 'First I will...', 'Step 1:', or 'Let me outline', stop — you are stalling. Call a tool immediately.")
        lines.append("    The ONLY exception: when all necessary data is already in the conversation history and you are ready to synthesize the final answer.")

        return "\n".join(lines)

    def system_message(self) -> Message:
        return Message.system(self.build_system_prompt())

    # ── Description ─────────────────────────────────

    def describe(self) -> str:
        return (
            f"Role: {self.name}\n"
            f"Profile: {self.profile}\n"
            f"Goal: {self.goal}\n"
            f"Actions: {self.registry.list_names()}\n"
            f"Constraints: {self.constraints}"
        )
