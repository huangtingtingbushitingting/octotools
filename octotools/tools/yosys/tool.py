from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

from octotools.tools.base import BaseTool


class YosysTool(BaseTool):
    def __init__(self):
        super().__init__(
            tool_name="YosysTool",
            tool_description="Synthesize and structurally check a Verilog candidate with a fixed Yosys script.",
            tool_version="1.0.0",
            input_types={"source_code": "str, required", "top_module": "str, required", "candidate_name": "str", "timeout": "float"},
            output_type="dict containing synthesis evidence",
            demo_commands=["execution = tool.execute(source_code='module TopModule; endmodule', top_module='TopModule')"],
        )

    def check_availability(self):
        return shutil.which("yosys") is not None

    def execute(self, source_code: str, top_module: str = "TopModule", candidate_name: str = "candidate", timeout: float = 60.0):
        executable = shutil.which("yosys")
        if not executable:
            return {"success": False, "synthesis_success": False, "error": "yosys not found"}
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_$]*", top_module):
            return {"success": False, "synthesis_success": False, "error": "invalid top module"}
        stem = re.sub(r"[^A-Za-z0-9_.-]+", "_", candidate_name).strip("._") or "candidate"
        root = Path(self.output_dir or "runs/agent-work").resolve()
        root.mkdir(parents=True, exist_ok=True)
        design = root / f"{stem}_synth.sv"
        design.write_text(source_code, encoding="utf-8")
        script = f"read_verilog -sv {design.as_posix()}; hierarchy -check -top {top_module}; proc; opt; check"
        try:
            process = subprocess.run([executable, "-q", "-p", script], capture_output=True, text=True, timeout=timeout, check=False)
            passed = process.returncode == 0
            return {
                "success": passed,
                "synthesis_success": passed,
                "returncode": process.returncode,
                "design_path": str(design),
                "stdout": process.stdout[-6000:],
                "stderr": process.stderr[-6000:],
            }
        except subprocess.TimeoutExpired as error:
            return {"success": False, "synthesis_success": False, "error": f"timeout: {error}"}
