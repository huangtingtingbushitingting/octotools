from __future__ import annotations

import shutil
import subprocess
import re
import os
from pathlib import Path

from octotools.tools.base import BaseTool


class VvpTool(BaseTool):#运行由lcarus verilog编译生成的.vvp仿真输出，判断仿真是否通过，并返回结构化的仿真证据
    def __init__(self):#初始化VvpTool工具，继承父类BaseTool的构造函数
        super().__init__(
            tool_name="VvpTool",
            tool_description="Run an IverilogTool .vvp artifact and return simulation evidence.",
            tool_version="1.0.0",
            input_types={"artifact_path": "str, required", "timeout": "float"},
            output_type="dict containing simulation evidence",
            demo_commands=["execution = tool.execute(artifact_path='candidate.vvp')"],
        )

    def check_availability(self):#检查vvp可执行文件是否可用
        return self._executable() is not None

    @staticmethod
    def _executable() -> str | None:
        configured = os.environ.get("OCTOVERILOG_VVP_PATH")
        if configured:
            path = Path(configured).expanduser()
            return str(path) if path.is_file() else None
        return shutil.which("vvp")

    def execute(self, artifact_path: str, timeout: float = 30.0):#运行.vvp并返回结果，设置仿真时间最大不超30s
        executable = self._executable()
        if not executable:
            return {"success": False, "simulation_success": False, "error": "vvp not found"}
        root = Path(self.output_dir or "runs/agent-work").resolve()
        artifact = Path(artifact_path).resolve()#获取仿真输出路径
        if root != artifact and root not in artifact.parents:
            return {"success": False, "simulation_success": False, "error": "artifact is outside the run workspace"}
        if not artifact.is_file():
            return {"success": False, "simulation_success": False, "error": "simulation artifact not found"}
        try:
            process = subprocess.run([executable, "-n", str(artifact)], capture_output=True, text=True, timeout=timeout, check=False)#运行仿真
            combined = "\n".join((process.stdout, process.stderr))#合并输出，用三种正则模式从输出中提取失败/不匹配的数量
            failure_counts = []
            for pattern in (
                r"(?i)Mismatches?\s*:\s*(\d+)",
                r"(?i)failed\s*:\s*(\d+)\s+out\s+of",
                r"(?i)(\d+)\s+mismatches?",
            ):
                failure_counts.extend(int(value) for value in re.findall(pattern, combined))
            passed = process.returncode == 0 and not any(failure_counts)#要求返回码为0并且没有任何失败计数时判断仿真为通过
            return {
                "success": passed,
                "simulation_success": passed,
                "returncode": process.returncode,
                "reported_failure_counts": failure_counts,
                "stdout": process.stdout[-6000:],#截取指定位置字段，避免返回内容过长
                "stderr": process.stderr[-6000:],
            }
        except subprocess.TimeoutExpired as error:
            return {"success": False, "simulation_success": False, "error": f"timeout: {error}"}
