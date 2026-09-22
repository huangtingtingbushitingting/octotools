from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

from octotools.tools.base import BaseTool


def _name(value: str) -> str:
    value = re.sub(r"[^A-Za-z0-9_.-]+", "_", value).strip("._")
    return value or "candidate"


class IverilogTool(BaseTool):
    """Compile a candidate and optional testbench with fixed safe arguments."""

    def __init__(self):
        super().__init__(
            tool_name="IverilogTool",
            tool_description=(
                "Compile synthesizable Verilog/SystemVerilog. When a testbench is "
                "provided, produce a .vvp simulation artifact for VvpTool."
            ),
            tool_version="1.0.0",
            input_types={
                "source_code": "str, required",
                "top_module": "str, required",
                "testbench": "str | None",
                "candidate_name": "str",
                "timeout": "float",
            },
            output_type="dict containing compile evidence and artifact paths",
            demo_commands=[
                "execution = tool.execute(source_code='module TopModule; endmodule', top_module='TopModule')"
            ],
        )

    def check_availability(self):
        return shutil.which("iverilog") is not None

    def execute(
        self,
        source_code: str,
        top_module: str = "TopModule",
        testbench: str | None = None,
        candidate_name: str = "candidate",
        timeout: float = 30.0,
    ):
        executable = shutil.which("iverilog")
        if not executable:
            return {"success": False, "compile_success": False, "error": "iverilog not found"}
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_$]*", top_module):
            return {"success": False, "compile_success": False, "error": "invalid top module"}
        root = Path(self.output_dir or "runs/agent-work").resolve()
        root.mkdir(parents=True, exist_ok=True)
        stem = _name(candidate_name)
        design = root / f"{stem}.sv"
        artifact = root / f"{stem}.vvp"
        design.write_text(source_code, encoding="utf-8")
        command = [executable, "-g2012"]
        if testbench is None:
            command.extend(["-s", top_module])
        command.extend(["-o", str(artifact), str(design)])
        bench_path = None
        if testbench is not None:
            bench_path = root / f"{stem}_tb.sv"
            bench_path.write_text(testbench, encoding="utf-8")
            command.append(str(bench_path))
        try:
            process = subprocess.run(command, capture_output=True, text=True, timeout=timeout, check=False)
            passed = process.returncode == 0
            return {
                "success": passed,
                "compile_success": passed,
                "returncode": process.returncode,
                "design_path": str(design),
                "testbench_path": str(bench_path) if bench_path else None,
                "artifact_path": str(artifact) if passed else None,
                "stdout": process.stdout[-6000:],
                "stderr": process.stderr[-6000:],
            }
        except subprocess.TimeoutExpired as error:
            return {"success": False, "compile_success": False, "error": f"timeout: {error}"}
