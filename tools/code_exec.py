"""
Python 代码执行工具 —— 安全的子进程沙箱

Agent 可以在推理过程中执行 Python 代码来完成：
- 气动热参数数值计算（复杂公式、迭代求解）
- 数据拟合与插值
- 快速出图（matplotlib 保存到文件）
- 结果验证（反算、量纲检查）

安全措施：
- 子进程隔离（subprocess）
- 硬超时 30 秒
- stdout/stderr 分别捕获
- 不限制 import（研究工具，信任用户）
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path

from core.action import Action


class CodeExecutionTool(Action):
    """Python 代码执行 —— 在隔离子进程中运行 Python 代码。"""

    name = "execute_python"
    description = (
        "执行 Python 代码并返回结果。适用于：复杂数值计算、数据拟合、"
        "快速可视化（matplotlib）、参数扫掠、量纲检查、公式验证。"
        "代码在隔离子进程中运行，超时 30 秒自动终止。"
        "如需保存图片，使用 plt.savefig() 指定完整路径。"
        "所需包不存在时会自动 pip install。"
    )
    parameters = {
        "type": "object",
        "properties": {
            "code": {
                "type": "string",
                "description": (
                    "要执行的 Python 代码。可以包含多行语句、函数定义、import 等。"
                    "运行在隔离的临时目录中。标准 print() 输出和变量值会被捕获返回。"
                    "例如：\n"
                    "import numpy as np\n"
                    "V = np.array([3000, 4000, 5000, 6000])\n"
                    "q = 1.83e-4 * np.sqrt(1.2) * V**3 / 1e6  # MW/m²\n"
                    "for v, qi in zip(V, q): print(f'{v} m/s → {qi:.2f} MW/m²')"
                ),
            },
            "timeout": {
                "type": "integer",
                "description": "执行超时秒数，默认 30，最大 120",
                "default": 30,
            },
            "install_packages": {
                "type": "array",
                "items": {"type": "string"},
                "description": "需要预安装的 pip 包列表。如 ['numpy', 'scipy', 'matplotlib']。仅在代码需要且环境中未安装时使用。",
            },
        },
        "required": ["code"],
    }

    def __init__(self, timeout: int = 30):
        self.default_timeout = timeout
        # 创建临时工作目录
        self._work_dir = Path(tempfile.mkdtemp(prefix="agent_exec_"))

    async def run(
        self,
        code: str,
        timeout: int = 30,
        install_packages: list[str] | None = None,
    ) -> str:
        timeout = min(timeout, 120)

        # ── 预安装包 ────────────────────────────────
        install_log = ""
        if install_packages:
            for pkg in install_packages:
                try:
                    result = subprocess.run(
                        [sys.executable, "-m", "pip", "install", pkg, "-q"],
                        capture_output=True,
                        text=True,
                        timeout=60,
                        cwd=str(self._work_dir),
                    )
                    if result.returncode != 0:
                        install_log += f"[pip] {pkg}: {result.stderr.strip()[-200:]}\n"
                except Exception as e:
                    install_log += f"[pip] {pkg}: 安装异常 {e}\n"

        # ── 准备执行环境 ────────────────────────────
        # 写入临时文件（比 -c 更好处理多行/缩进）
        script_path = self._work_dir / "_agent_exec.py"
        script_path.write_text(code, encoding="utf-8")

        # ── 执行 ─────────────────────────────────────
        env = os.environ.copy()
        env["PYTHONUNBUFFERED"] = "1"
        # 把项目根加入 path，方便 import 项目内模块
        project_root = str(Path(__file__).parent.parent.parent)
        existing_path = env.get("PYTHONPATH", "")
        env["PYTHONPATH"] = project_root + (os.pathsep + existing_path if existing_path else "")

        try:
            proc = subprocess.run(
                [sys.executable, str(script_path)],
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=str(self._work_dir),
                env=env,
            )
        except subprocess.TimeoutExpired:
            return (
                f"⏱️ **执行超时**（{timeout}s）\n"
                f"代码未在 {timeout} 秒内完成，已被终止。\n"
                f"建议：检查是否有无限循环，或增加 timeout 参数。"
            )
        except Exception as e:
            return f"❌ **执行异常**：{e}"

        # ── 构建返回 ─────────────────────────────────
        lines = []

        if install_log:
            lines.append(f"📦 **包安装**：\n{install_log}")

        # stdout
        stdout = proc.stdout.strip()
        if stdout:
            preview = stdout
            if len(preview) > 3000:
                preview = preview[:3000] + "\n... (输出截断，完整长度 {} 字符)".format(len(stdout))
            lines.append(f"📤 **stdout**：\n```\n{preview}\n```")
        else:
            lines.append("📤 **stdout**：（无输出）")

        # stderr
        stderr = proc.stderr.strip()
        if stderr:
            preview = stderr
            if len(preview) > 1000:
                preview = preview[:1000] + "\n... (截断)"
            lines.append(f"⚠️ **stderr**：\n```\n{preview}\n```")

        # 退出码
        lines.append(f"🔢 **退出码**：{proc.returncode}")

        # 检查是否有生成的图片文件
        image_files = list(self._work_dir.glob("*.png")) + list(self._work_dir.glob("*.jpg"))
        if image_files:
            lines.append(f"🖼️ **生成图片**：{', '.join(f.name for f in image_files)}")
            lines.append(f"📁 位置：{self._work_dir}")

        return "\n".join(lines)

    @property
    def work_dir(self) -> str:
        return str(self._work_dir)
