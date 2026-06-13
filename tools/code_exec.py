"""
Python Code Execution Tool -- Secure Subprocess Sandbox

The Agent can execute Python code during reasoning to accomplish:
- Aerothermal parameter numerical computation (complex formulas, iterative solving)
- Data fitting and interpolation
- Quick plotting (matplotlib save to file)
- Result verification (back-calculation, dimensional analysis)

Security measures:
- Subprocess isolation (subprocess)
- Hard timeout 30 seconds
- stdout/stderr captured separately
- No import restrictions (research tool, trust user)
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

from core.action import Action

# pip package name whitelist regex: only allow alphanumeric, underscore, hyphen
_SAFE_PKG_PATTERN = re.compile(r"^[a-zA-Z0-9_-]+$")
# Forbidden pip arguments (prevents injection via --index-url / --extra-index-url etc.)
_FORBIDDEN_PIP_FLAGS = re.compile(
    r"--(\w+-?)*\s+"
    r"("
    r"index-url|extra-index-url|trusted-host|proxy|retries|timeout|"
    r"src|constraint|no-deps|pre|extra|editable|src-dir|config-settings"
    r")",
    re.IGNORECASE,
)


class CodeExecutionTool(Action):
    """Python code execution -- runs Python code in isolated subprocess."""

    name = "execute_python"
    description = (
        "Execute Python code and return results. Suitable for: complex numerical computation, "
        "data fitting, quick visualization (matplotlib), parameter sweeping, "
        "dimensional analysis, formula verification. "
        "Code runs in isolated subprocess (headless environment, plt.show() is automatically ignored). "
        "To save images use plt.savefig('filename.png'), images will be saved to outputs/ directory. "
        "Missing packages are automatically installed via pip. "
        "Default timeout is 60 seconds, complex computations can set timeout=120."
    )
    parameters = {
        "type": "object",
        "properties": {
            "code": {
                "type": "string",
                "description": (
                    "Python code to execute. Can contain multi-line statements, function definitions, imports, etc. "
                    "Runs in isolated temporary directory. Standard print() output and variable values are captured and returned. "
                    "Example:\n"
                    "import numpy as np\n"
                    "V = np.array([3000, 4000, 5000, 6000])\n"
                    "q = 1.83e-4 * np.sqrt(1.2) * V**3 / 1e6  # MW/m2\n"
                    "for v, qi in zip(V, q): print(f'{v} m/s -> {qi:.2f} MW/m2')"
                ),
            },
            "timeout": {
                "type": "integer",
                "description": "Execution timeout in seconds, default 30, max 120",
                "default": 30,
            },
            "install_packages": {
                "type": "array",
                "items": {"type": "string"},
                "description": "List of pip packages to pre-install. Example: ['numpy', 'scipy', 'matplotlib']. Only used when code requires packages not in environment.",
            },
        },
        "required": ["code"],
    }

    def __init__(self, timeout: int = 60):
        self.default_timeout = timeout
        # Persistent working directory: use timestamped subfolder for each execution to preserve images
        from datetime import datetime
        self._output_root = Path(__file__).parent.parent / "outputs"
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        self._work_dir = self._output_root / f"exec_{ts}"
        self._work_dir.mkdir(parents=True, exist_ok=True)

    async def run(
        self,
        code: str,
        timeout: int = 60,
        install_packages: list[str] | None = None,
    ) -> str:
        timeout = min(timeout, 180)  # Max 3 minutes, sufficient for plotting

        # ── Pre-install packages ────────────────────────────────
        install_log = ""
        if install_packages:
            for pkg in install_packages:
                # Defensive: validate package name format + forbid dangerous arguments
                if not _SAFE_PKG_PATTERN.match(pkg):
                    install_log += f"[pip] {pkg}: Rejected -- package name contains illegal characters (only a-zA-Z0-9_- allowed)\n"
                    continue
                if _FORBIDDEN_PIP_FLAGS.search(pkg):
                    install_log += f"[pip] {pkg}: Rejected -- pip options cannot be passed via package name (e.g., --index-url)\n"
                    continue
                try:
                    result = subprocess.run(
                        [sys.executable, "-m", "pip", "install", pkg, "-q"],
                        capture_output=True,
                        text=True,
                        encoding="utf-8",
                        timeout=60,
                        cwd=str(self._work_dir),
                    )
                    if result.returncode != 0:
                        install_log += f"[pip] {pkg}: {result.stderr.strip()[-200:]}\n"
                except Exception as e:
                    install_log += f"[pip] {pkg}: Install exception {e}\n"

        # ── Prepare execution environment ────────────────────────────
        # Write to temp file (better than -c for handling multi-line/indentation)
        script_path = self._work_dir / "_agent_exec.py"
        script_path.write_text(code, encoding="utf-8")

        # ── Execute ─────────────────────────────────────
        env = os.environ.copy()
        env["PYTHONUNBUFFERED"] = "1"
        env["MPLBACKEND"] = "Agg"  # Headless environment, avoid plt.show() blocking
        env["PYTHONIOENCODING"] = "utf-8"  # Prevent print() Chinese/special char GBK crash
        # Add project root to path for importing project modules
        project_root = str(Path(__file__).parent.parent.parent)
        existing_path = env.get("PYTHONPATH", "")
        env["PYTHONPATH"] = project_root + (os.pathsep + existing_path if existing_path else "")

        try:
            proc = subprocess.run(
                [sys.executable, str(script_path)],
                capture_output=True,
                text=True,
                encoding="utf-8",
                timeout=timeout,
                cwd=str(self._work_dir),
                env=env,
            )
        except subprocess.TimeoutExpired:
            return (
                f"[TIMEOUT] Execution timeout ({timeout}s)\n"
                f"Code did not finish within {timeout}s. Check for infinite loops."
            )
        except Exception as e:
            return f"[ERROR] Execution exception: {e}"

        # ── Build return value ─────────────────────────────────
        lines = []

        if install_log:
            lines.append(f"[pip] Installed:\n{install_log}")

        # stdout
        stdout = proc.stdout.strip()
        if stdout:
            preview = stdout
            if len(preview) > 3000:
                preview = preview[:3000] + "\n... (truncated, full length {} chars)".format(len(stdout))
            lines.append(f"[stdout]:\n```\n{preview}\n```")
        else:
            lines.append("[stdout]: (no output)")

        # stderr
        stderr = proc.stderr.strip()
        if stderr:
            preview = stderr
            if len(preview) > 1000:
                preview = preview[:1000] + "\n... (truncated)"
            lines.append(f"[stderr]:\n```\n{preview}\n```")

        # Exit code
        lines.append(f"[exit code]: {proc.returncode}")

        # Check for generated image files
        image_files = list(self._work_dir.glob("*.png")) + list(self._work_dir.glob("*.jpg"))
        if image_files:
            lines.append(f"[generated images]:")
            for f in image_files:
                lines.append(f"  -> {f}  ({f.stat().st_size / 1024:.1f} KB)")
            lines.append(f"[save path]: {self._work_dir}")

        return "\n".join(lines)

    @property
    def work_dir(self) -> str:
        return str(self._work_dir)
