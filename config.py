"""
Agent Unified Configuration
===========================
All tunable parameters are centrally managed to avoid scattering across files.

Usage:
    from config import AgentConfig
    cfg = AgentConfig()
    agent = cfg.build_agent()

Environment Variables:
    Priority is given to loading from 05_AI_Agent/.env; if absent, system environment variables are used.
    Bailian API requires DASHSCOPE_API_KEY=sk-xxxxx
"""

from __future__ import annotations

import os
from pathlib import Path


# ── .env Auto-loading ─────────────────────────────────

def _load_dotenv() -> None:
    """Load environment variables from 05_AI_Agent/.env (zero dependencies)."""
    env_file = Path(__file__).parent / ".env"
    if not env_file.exists():
        return
    with open(env_file, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" not in line:
                continue
            key, _, value = line.partition("=")
            key, value = key.strip(), value.strip()
            # Strip quotes
            if value.startswith('"') and value.endswith('"'):
                value = value[1:-1]
            elif value.startswith("'") and value.endswith("'"):
                value = value[1:-1]
            # Override only if not already set (system env vars take priority)
            if key and key not in os.environ:
                os.environ[key] = value


_load_dotenv()

from core.llm import LLMConfig

# ── Project Root ─────────────────────────────────────

PROJECT_ROOT = Path(__file__).parent.parent


# ── Pre-configured LLM Settings ─────────────────────


def _bailian_config() -> LLMConfig:
    """Alibaba Cloud Bailian API configuration."""
    return LLMConfig(
        base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        api_key=os.getenv("DASHSCOPE_API_KEY", "your-api-key-here"),
        model="qwen3.5-plus",
        temperature=0.3,
        max_tokens=4096,
        preset_name="bailian",
    )


def _vllm_local_config() -> LLMConfig:
    """Local vLLM inference configuration (fine-tuned model)."""
    return LLMConfig(
        base_url="http://localhost:8000/v1",
        api_key="not-needed",
        model="aero-thermal-expert",
        temperature=0.3,
        max_tokens=4096,
        preset_name="vllm_local",
    )


def _ollama_config() -> LLMConfig:
    """Ollama local configuration — WSL2 desktop inference."""
    return LLMConfig(
        base_url="http://localhost:11434/v1",
        api_key="not-needed",
        model="llama3.1:8b",
        temperature=0.3,
        max_tokens=4096,
        preset_name="ollama",
    )


def _siliconflow_config() -> LLMConfig:
    """SiliconFlow API configuration — DeepSeek-V3 / Qwen and other open-source models, excellent cost-performance."""
    return LLMConfig(
        base_url="https://api.siliconflow.cn/v1",
        api_key=os.getenv("SILICONFLOW_API_KEY", "your-api-key-here"),
        model="deepseek-ai/DeepSeek-V3",
        temperature=0.3,
        max_tokens=4096,
        preset_name="siliconflow",
    )


def _custom_config() -> LLMConfig:
    """Load custom LLM configuration from 05_AI_Agent/llm_config.json.

    Configuration file format (JSON):
        {
            "base_url": "https://api.example.com/v1",
            "api_key": "sk-xxxxx",
            "model": "your-model-name",
            "temperature": 0.3,
            "max_tokens": 2048
        }

    No restart required after modifying this file; changes take effect automatically on next conversation.
    """
    import json as _json

    config_file = Path(__file__).parent / "llm_config.json"
    if not config_file.exists():
        raise FileNotFoundError(
            f"Custom LLM config file not found: {config_file}\n"
            f"Please create this file; for format reference see llm_config.example.json"
        )

    with open(config_file, "r", encoding="utf-8") as f:
        cfg = _json.load(f)

    # Support ${ENV_VAR} and $ENV_VAR for environment variable references
    api_key = cfg.get("api_key", "")
    if api_key.startswith("$"):
        if api_key.startswith("${") and api_key.endswith("}"):
            api_key = os.getenv(api_key[2:-1], api_key)
        else:
            api_key = os.getenv(api_key[1:], api_key)

    return LLMConfig(
        base_url=cfg.get("base_url", ""),
        api_key=api_key,  # Use resolved value (includes env var substitution)
        model=cfg.get("model", ""),
        temperature=cfg.get("temperature", 0.3),
        max_tokens=cfg.get("max_tokens", 2048),
        preset_name="custom",
    )


# ── Fallback Chains ────────────────────────────────────────────────────────────

# Preset → fallback order (tried in sequence, user asked before each switch)
FALLBACK_CHAINS: dict[str, list[str]] = {
    "bailian":     ["siliconflow", "ollama"],
    "siliconflow": ["bailian", "ollama"],
    "vllm_local":  ["bailian", "siliconflow"],
    "ollama":      ["bailian", "siliconflow"],
    "custom":      ["bailian", "siliconflow"],
}


# ── Policy Routes ─────────────────────────────────────────────────────────────

# Complexity → preferred preset (balanced cost-quality policy)
POLICY_ROUTES: dict[str, str] = {
    "simple":   "ollama",       # Fast & cheap for trivial tasks
    "moderate": "siliconflow",   # Best cost-performance
    "complex":  "bailian",      # Most capable model for hard tasks
}


# ── Main Configuration ──────────────────────────────


class AgentConfig:
    """Agent master configuration.

    Usage:
        # Use local fine-tuned model
        cfg = AgentConfig(llm="vllm_local")

        # Use Bailian API
        cfg = AgentConfig(llm="bailian")

        # Custom
        cfg = AgentConfig(llm=LLMConfig(base_url="...", model="..."))
    """

    PRESETS = {
        "bailian": _bailian_config,
        "siliconflow": _siliconflow_config,
        "vllm_local": _vllm_local_config,
        "ollama": _ollama_config,
        "custom": _custom_config,
    }

    def __init__(
        self,
        llm: str | LLMConfig = "vllm_local",
        mode: str = "react",
        max_react_steps: int = 15,
        max_plan_steps: int = 6,
        critique_rounds: int = 2,  # Self-critique iterations after ReAct loop
        self_consistency: int = 1,  # 1 = disabled; 3+ enables voting (great for 8B models)
        auto_route: bool = False,  # Enable LLM-based complexity routing + auto-fallback
        verbose: bool = False,
        # Path configuration
        faiss_index_dir: str | Path | None = None,
        literature_csv: str | Path | None = None,
    ):
        # LLM
        if isinstance(llm, str):
            factory = self.PRESETS.get(llm)
            if factory is None:
                raise ValueError(f"Unknown preset: {llm}, available options: {list(self.PRESETS)}")
            self.llm = factory()
        else:
            self.llm = llm

        # Execution mode
        self.mode = mode
        self.max_react_steps = max_react_steps
        self.max_plan_steps = max_plan_steps
        self.critique_rounds = critique_rounds
        self.self_consistency = self_consistency
        self.auto_route = auto_route
        self.verbose = verbose

        # Paths
        self.faiss_index_dir = Path(faiss_index_dir) if faiss_index_dir else (
            PROJECT_ROOT / "03_知识工程" / "05_向量索引" / "faiss_index"
        )
        self.literature_csv = Path(literature_csv) if literature_csv else (
            PROJECT_ROOT / "03_知识工程" / "03_文献库" / "Final_Merged_Literature.csv"
        )

    def build_agent(self):
        """Build an Agent instance based on the configuration."""
        from core.agent import Agent

        return Agent(
            llm_config=self.llm,
            name="AeroThermalScientist",
            profile="Hypersonic gas-solid interface coupling AI Scientist, expert in aerodynamic thermodynamics, catalytic recombination, SBLI, non-equilibrium flow. Capable of proactively identifying research gaps, generating verifiable hypotheses, designing experimental protocols",
            goal="Upgrade from passive Q&A to proactive scientific research: literature gap identification → hypothesis generation → experimental design → results analysis → paper generation",
            constraints=[
                # Data credibility
                "Data returned by tools takes priority over the model's training knowledge — when in conflict, defer to tool results",
                "All citations must come from actual tool-returned results; never fabricate NASA report numbers/DOIs/paper titles from memory",
                "Numerical computation results must specify computation method, assumed conditions, and parameter sources",
                "Computation results must clearly distinguish between 'conditional computation based on assumptions' or 'literature-verified values'",
                "Uncertain or out-of-scope content must be clearly marked as 'to be verified'",
                "Do not fabricate data, invent citations, or make unsupported quantitative extrapolations",
                # Hypothesis generation
                "Generated hypotheses must pass physical constraint verification (parameter bounds, flow regime consistency, conservation laws)",
                "Hypothesis predictions must be specifically verifiable (numerical values or clear trends)",
                # Catalytic recombination coefficient special focus
                "Catalytic recombination coefficients must specify recombination species (O/N/mixed), surface type (quartz/RCG/SiC/Pt, etc.), and reference conditions",
                "Temperature trends for catalytic coefficients must cite verifiable literature or tool computations; cannot rely solely on empirical intuition",
                # Documentation
                "Upon task completion, must call generate_report tool to save conclusions as Markdown report",
                "When key conclusions are discovered during research, call export_finding to record them entry by entry",
            ],
            mode=self.mode,
            max_react_steps=self.max_react_steps,
            max_plan_steps=self.max_plan_steps,
            critique_rounds=self.critique_rounds,
            self_consistency=self.self_consistency,
            auto_route=self.auto_route,
            verbose=self.verbose,
        )

    def __repr__(self) -> str:
        return (
            f"AgentConfig(llm={self.llm.model}@{self.llm.base_url}, "
            f"mode={self.mode}, faiss={self.faiss_index_dir})"
        )
