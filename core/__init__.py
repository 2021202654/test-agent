"""
AeroThermal Agent 核心框架
============================

仿 MetaGPT Role-Action-Memory 三元组的最小 Agent 框架，
面向高超声速气固界面耦合领域。

结构：
    Agent              顶层入口，组装一切
    ├── Role           身份/目标/约束 + 工具注册
    ├── LLMInterface   OpenAI 兼容 API 封装
    ├── Memory         短期 + 工作 + 长期记忆
    │   ├── ShortTermMemory   滑动窗口对话
    │   ├── WorkingMemory     研究上下文状态
    │   └── Memory            统一接口
    ├── Action          工具基类 + 注册表
    │   └── ActionRegistry
    ├── Orchestrator    运行模式
    │   ├── ReActOrchestrator       推理-行动-观察循环
    │   └── PlanExecuteOrchestrator  先规划后执行
    └── Message         消息体

用法：
    from core import Agent, LLMConfig

    agent = Agent(
        llm_config=LLMConfig(base_url="http://localhost:8000/v1", model="expert"),
        name="AeroThermalExpert",
        profile="高超声速气固界面耦合研究专家",
        goal="辅助研究者进行文献检索、多步推理、证据合成",
        constraints=["引用必须可溯源", "不确定时明确标注"],
    )
    agent.equip(your_search_tool)
    reply = await agent.run("你的问题")
"""

from .action import Action, ActionRegistry
from .agent import Agent
from .llm import LLMConfig, LLMInterface
from .memory import Memory, ShortTermMemory, WorkingMemory
from .message import Message
from .orchestrator import PlanExecuteOrchestrator, ReActOrchestrator
from .role import Role

__all__ = [
    # 顶层
    "Agent",
    # LLM
    "LLMConfig",
    "LLMInterface",
    # 角色
    "Role",
    # 工具
    "Action",
    "ActionRegistry",
    # 记忆
    "Memory",
    "ShortTermMemory",
    "WorkingMemory",
    # 编排
    "ReActOrchestrator",
    "PlanExecuteOrchestrator",
    # 消息
    "Message",
]
