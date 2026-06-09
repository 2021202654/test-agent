"""
Agent 统一配置
===============
所有可调参数集中管理，避免散落在各处。

使用方式：
    from config import AgentConfig
    cfg = AgentConfig()
    agent = cfg.build_agent()

环境变量：
    优先从 05_AI_Agent/.env 加载，不存在则使用系统环境变量。
    百炼 API 需要 DASHSCOPE_API_KEY=sk-xxxxx
"""

from __future__ import annotations

import os
from pathlib import Path


# ── .env 自动加载 ────────────────────────────────────

def _load_dotenv() -> None:
    """从 05_AI_Agent/.env 加载环境变量（零依赖）。"""
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
            # 去掉引号
            if value.startswith('"') and value.endswith('"'):
                value = value[1:-1]
            elif value.startswith("'") and value.endswith("'"):
                value = value[1:-1]
            # 仅在未设置时覆盖（系统环境变量优先级更高）
            if key and key not in os.environ:
                os.environ[key] = value


_load_dotenv()

from core.llm import LLMConfig

# ── 项目根目录 ──────────────────────────────────────

PROJECT_ROOT = Path(__file__).parent.parent


# ── 预置 LLM 配置 ───────────────────────────────────


def _bailian_config() -> LLMConfig:
    """阿里云百炼 API 配置。"""
    return LLMConfig(
        base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        api_key=os.getenv("DASHSCOPE_API_KEY", "your-api-key-here"),
        model="qwen-plus",
        temperature=0.3,
        max_tokens=2048,
    )


def _vllm_local_config() -> LLMConfig:
    """本地 vLLM 推理配置（微调模型）。"""
    return LLMConfig(
        base_url="http://localhost:8000/v1",
        api_key="not-needed",
        model="aero-thermal-expert",
        temperature=0.3,
        max_tokens=2048,
    )


def _ollama_config() -> LLMConfig:
    """Ollama 本地配置 —— WSL2 桌面推理。"""
    return LLMConfig(
        base_url="http://localhost:11434/v1",
        api_key="not-needed",
        model="llama3.1:8b",
        temperature=0.3,
        max_tokens=2048,
    )


def _siliconflow_config() -> LLMConfig:
    """硅基流动 API 配置 —— DeepSeek-V3 / Qwen 等开源模型，性价比极高。"""
    return LLMConfig(
        base_url="https://api.siliconflow.cn/v1",
        api_key=os.getenv("SILICONFLOW_API_KEY", "your-api-key-here"),
        model="deepseek-ai/DeepSeek-V3",
        temperature=0.3,
        max_tokens=2048,
    )


def _custom_config() -> LLMConfig:
    """从 05_AI_Agent/llm_config.json 读取自定义 LLM 配置。

    配置文件格式（JSON）：
        {
            "base_url": "https://api.example.com/v1",
            "api_key": "sk-xxxxx",
            "model": "your-model-name",
            "temperature": 0.3,
            "max_tokens": 2048
        }

    修改此文件后无需重启，下次对话自动生效。
    """
    import json as _json

    config_file = Path(__file__).parent / "llm_config.json"
    if not config_file.exists():
        raise FileNotFoundError(
            f"未找到自定义 LLM 配置文件：{config_file}\n"
            f"请创建该文件，格式参考 llm_config.example.json"
        )

    with open(config_file, "r", encoding="utf-8") as f:
        cfg = _json.load(f)

    # 支持 ${ENV_VAR} 和 $ENV_VAR 引用环境变量
    api_key = cfg.get("api_key", "")
    if api_key.startswith("$"):
        if api_key.startswith("${") and api_key.endswith("}"):
            api_key = os.getenv(api_key[2:-1], api_key)
        else:
            api_key = os.getenv(api_key[1:], api_key)

    return LLMConfig(
        base_url=cfg.get("base_url", ""),
        api_key=api_key,  # 使用解析后的值（含环境变量替换）
        model=cfg.get("model", ""),
        temperature=cfg.get("temperature", 0.3),
        max_tokens=cfg.get("max_tokens", 2048),
    )


# ── 主配置 ──────────────────────────────────────────


class AgentConfig:
    """Agent 总配置。

    用法：
        # 使用本地微调模型
        cfg = AgentConfig(llm="vllm_local")

        # 使用百炼 API
        cfg = AgentConfig(llm="bailian")

        # 自定义
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
        max_react_steps: int = 12,
        max_plan_steps: int = 6,
        verbose: bool = False,
        # 路径配置
        faiss_index_dir: str | Path | None = None,
        literature_csv: str | Path | None = None,
    ):
        # LLM
        if isinstance(llm, str):
            factory = self.PRESETS.get(llm)
            if factory is None:
                raise ValueError(f"未知预置: {llm}，可选: {list(self.PRESETS)}")
            self.llm = factory()
        else:
            self.llm = llm

        # 运行模式
        self.mode = mode
        self.max_react_steps = max_react_steps
        self.max_plan_steps = max_plan_steps
        self.verbose = verbose

        # 路径
        self.faiss_index_dir = Path(faiss_index_dir) if faiss_index_dir else (
            PROJECT_ROOT / "03_知识工程" / "05_向量索引" / "faiss_index"
        )
        self.literature_csv = Path(literature_csv) if literature_csv else (
            PROJECT_ROOT / "03_知识工程" / "03_文献库" / "Final_Merged_Literature.csv"
        )

    def build_agent(self):
        """根据配置构建 Agent 实例。"""
        from core.agent import Agent

        return Agent(
            llm_config=self.llm,
            name="AeroThermalScientist",
            profile="高超声速气固界面耦合 AI Scientist，精通气动热力学、催化复合、SBLI、非平衡流动。能主动识别研究 Gap、生成可验证假设、设计实验方案",
            goal="从被动问答升级为主动科研：文献 Gap 识别 → 假设生成 → 实验设计 → 结果分析 → 论文生成",
            constraints=[
                "所有引用必须可溯源（提供DOI或论文标题）",
                "数值计算结果必须标注计算方法和假设条件",
                "不确定或超出知识范围的内容必须明确标注为'待验证'",
                "不编造数据，不虚构引用",
                "生成的假设必须通过物理约束验证（参数边界、流态一致性、守恒律）",
                "假设预测必须具体可验证（数值或明确趋势）",
                "任务完成后必须调用 generate_report 工具将结论保存为 Markdown 报告",
                "研究过程中发现关键结论时，调用 export_finding 逐条记录",
            ],
            mode=self.mode,
            max_react_steps=self.max_react_steps,
            max_plan_steps=self.max_plan_steps,
            verbose=self.verbose,
        )

    def __repr__(self) -> str:
        return (
            f"AgentConfig(llm={self.llm.model}@{self.llm.base_url}, "
            f"mode={self.mode}, faiss={self.faiss_index_dir})"
        )
