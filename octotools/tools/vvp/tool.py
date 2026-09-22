from __future__ import annotations

import shutil
import subprocess
import re
from pathlib import Path

from octotools.tools.base import BaseTool


class VvpTool(BaseTool):
    def __init__(self):
        super().__init__(
            tool_name="VvpTool",
            tool_description="Run an IverilogTool .vvp artifact and return simulation evidence.",
            tool_version="1.0.0",
            input_types={"artifact_path": "str, required", "timeout": "float"},
            output_type="dict containing simulation evidence",
            demo_commands=["execution = tool.execute(artifact_path='candidate.vvp')"],
        )

    def check_availability(self):
        return shutil.which("vvp") is not None

    def execute(self, artifact_path: str, timeout: float = 30.0):
        executable = shutil.which("vvp")
        if not executable:
            return {"success": False, "simulation_success": False, "error": "vvp not found"}
        root = Path(self.output_dir or "runs/agent-work").resolve()
        artifact = Path(artifact_path).resolve()
        if root != artifact and root not in artifact.parents:
            return {"success": False, "simulation_success": False, "error": "artifact is outside the run workspace"}
        if not artifact.is_file():
            return {"success": False, "simulation_success": False, "error": "simulation artifact not found"}
        try:
            process = subprocess.run([executable, "-n", str(artifact)], capture_output=True, text=True, timeout=timeout, check=False)
            combined = "\n".join((process.stdout, process.stderr))
            failure_counts = []
            for pattern in (
                r"(?i)Mismatches?\s*:\s*(\d+)",
                r"(?i)failed\s*:\s*(\d+)\s+out\s+of",
                r"(?i)(\d+)\s+mismatches?",
            ):
                failure_counts.extend(int(value) for value in re.findall(pattern, combined))
            passed = process.returncode == 0 and not any(failure_counts)
            return {
                "success": passed,
                "simulation_success": passed,
                "returncode": process.returncode,
                "reported_failure_counts": failure_counts,
                "stdout": process.stdout[-6000:],
                "stderr": process.stderr[-6000:],
            }
        except subprocess.TimeoutExpired as error:
            return {"success": False, "simulation_success": False, "error": f"timeout: {error}"}
