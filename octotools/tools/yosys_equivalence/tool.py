from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

from octotools.tools.base import BaseTool


class YosysEquivalenceTool(BaseTool):#进行参考RTL与候选RTL的等价性检查
    def __init__(self):
        super().__init__(
            tool_name="YosysEquivalenceTool",
            tool_description="Formally compare candidate RTL with reference RTL using Yosys equivalence passes.",
            tool_version="1.0.0",
            input_types={"candidate_code": "str, required", "reference_code": "str, required", "top_module": "str, required", "timeout": "float"},
            output_type="dict containing formal-equivalence evidence",
            demo_commands=[],
        )

    def check_availability(self):
        return shutil.which("yosys") is not None

    def execute(self, candidate_code: str, reference_code: str, top_module: str = "TopModule", timeout: float = 120.0):#调用Yosys执行等价性检查
        executable = shutil.which("yosys")
        if not executable:
            return {"success": False, "equivalence_success": False, "error": "yosys not found"}
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_$]*", top_module):
            return {"success": False, "equivalence_success": False, "error": "invalid top module"}
        root = Path(self.output_dir or "runs/agent-work").resolve()
        root.mkdir(parents=True, exist_ok=True)
        candidate = root / "equiv_candidate.sv"
        reference = root / "equiv_reference.sv"
        candidate.write_text(candidate_code, encoding="utf-8")
        reference.write_text(reference_code, encoding="utf-8")
        script = "; ".join([
            f"read_verilog -sv {reference.as_posix()}", f"prep -top {top_module}", f"rename {top_module} gold", "design -stash gold", "design -reset",
            f"read_verilog -sv {candidate.as_posix()}", f"prep -top {top_module}", f"rename {top_module} gate", "design -stash gate", "design -reset",
            "design -copy-from gold -as gold gold", "design -copy-from gate -as gate gate", "equiv_make gold gate equiv", "hierarchy -top equiv", "equiv_simple", "equiv_induct -undef", "equiv_status -assert",
        ])#进行Yosys等价性检查的脚本
        try:
            process = subprocess.run([executable, "-q", "-p", script], capture_output=True, text=True, timeout=timeout, check=False)
            passed = process.returncode == 0
            return {"success": passed, "equivalence_success": passed, "returncode": process.returncode, "stdout": process.stdout[-8000:], "stderr": process.stderr[-8000:]}
        except subprocess.TimeoutExpired as error:
            return {"success": False, "equivalence_success": False, "error": f"timeout: {error}"}
