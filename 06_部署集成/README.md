# 06 部署集成

> Agent 全栈部署方案 — DSW vLLM + Gradio

---

## 部署架构

```
DSW 实例（V100 16GB / A10 24GB）
├── vLLM API Server (localhost:8000)  ← 加载微调模型 aero-thermal-8b
├── Agent Framework                   ← OpenAI 兼容客户端，9 个工具
└── Gradio UI (0.0.0.0:7860)          ← DSW 自动提供公网代理 URL
```

---

## 部署入口

| 入口 | 文件 | 用途 |
|------|------|------|
| CLI | `run_agent.py` | 交互 / 单次问答，`--llm` 选择后端 |
| Gradio | `app.py` | Web UI，`--llm custom` 连 vLLM |

### CLI 示例

```bash
cd 05_AI_Agent

# 百炼 API（即开即用）
python run_agent.py --llm bailian

# DSW vLLM
python run_agent.py --llm custom --base-url http://localhost:8000/v1

# Plan-Execute 模式
python run_agent.py --llm custom --mode plan_execute --task "评估气固界面催化模型跨尺度适用性"

# 自省迭代（默认 2 轮，设为 0 可禁用）
python run_agent.py --llm bailian --critique-rounds 3
```

### Gradio Web UI

```bash
# DSW 部署（自动获取公网链接）
python app.py --llm custom --port 7860

# 本地开发用百炼
python app.py --llm bailian
```

---

## DSW 部署流程

按 `04_LLM微调线/04_推理部署/` 下 4 个 notebook 顺序执行：

| 步骤 | Notebook | 内容 |
|------|----------|------|
| 0 | `0_DSW环境部署.ipynb` | pip 镜像 + PyTorch CUDA + LLaMA-Factory + vLLM + Pandoc + 中文字体 |
| 1 | `1_模型下载与数据注册.ipynb` | ModelScope 下载 Llama-3.1-8B + 数据集注册 + 校验 |
| 2 | `2_训练与导出.ipynb` | QLoRA 4-bit 训练 + LoRA 合并导出 |
| 3 | `3_推理与Agent部署.ipynb` | vLLM 启动 + Agent 配置 + Gradio UI 上线 |

---

## LLM 后端

| 后端 | 配置 | 适用场景 |
|------|------|------|
| vLLM (DSW) | `localhost:8000/v1` | 微调模型推理 |
| 百炼 API | `dashscope.aliyuncs.com` | 开发/调试/QA 生成 |
| Ollama | `localhost:11434/v1` | 本地快速验证 |

`config.py` 提供 4 套预设：`vllm_local` / `bailian` / `ollama` / `custom`

---

# 06 Deployment & Integration

> Full-Stack Agent Deployment — DSW vLLM + Gradio

---

## Deployment Architecture

```
DSW Instance (V100 16GB / A10 24GB)
├── vLLM API Server (localhost:8000)  ← Loads fine-tuned model aero-thermal-8b
├── Agent Framework                   ← OpenAI-compatible client, 9 tools
└── Gradio UI (0.0.0.0:7860)          ← DSW auto-provides public proxy URL
```

---

## Deployment Entry Points

| Entry | File | Purpose |
|------|------|------|
| CLI | `run_agent.py` | Interactive / single Q&A, `--llm` selects backend |
| Gradio | `app.py` | Web UI, `--llm custom` connects to vLLM |

### CLI Examples

```bash
cd 05_AI_Agent

# Bailian API (ready to use)
python run_agent.py --llm bailian

# DSW vLLM
python run_agent.py --llm custom --base-url http://localhost:8000/v1

# Plan-Execute mode
python run_agent.py --llm custom --mode plan_execute --task "Evaluate cross-scale applicability of gas-solid interface catalytic model"

# Self-critique iteration (default 2 rounds, set to 0 to disable)
python run_agent.py --llm bailian --critique-rounds 3
```

### Gradio Web UI

```bash
# DSW deployment (auto gets public link)
python app.py --llm custom --port 7860

# Local development with Bailian
python app.py --llm bailian
```

---

## DSW Deployment Process

Execute the 4 notebooks under `04_LLM微调线/04_推理部署/` in order:

| Step | Notebook | Content |
|------|----------|------|
| 0 | `0_DSW环境部署.ipynb` | pip mirror + PyTorch CUDA + LLaMA-Factory + vLLM + Pandoc + Chinese fonts |
| 1 | `1_模型下载与数据注册.ipynb` | ModelScope downloads Llama-3.1-8B + dataset registration + validation |
| 2 | `2_训练与导出.ipynb` | QLoRA 4-bit training + LoRA merge and export |
| 3 | `3_推理与Agent部署.ipynb` | vLLM startup + Agent config + Gradio UI launch |

---

## LLM Backends

| Backend | Config | Use Case |
|------|------|------|
| vLLM (DSW) | `localhost:8000/v1` | Fine-tuned model inference |
| Bailian API | `dashscope.aliyuncs.com` | Development / Debugging / QA generation |
| Ollama | `localhost:11434/v1` | Local quick validation |

`config.py` provides 4 presets: `vllm_local` / `bailian` / `ollama` / `custom`
