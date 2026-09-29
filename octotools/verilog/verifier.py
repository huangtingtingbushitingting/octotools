"""Safe fixed-command Verilog compilation, simulation, and synthesis."""

from __future__ import annotations

import re
import shutil
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any


class VerificationGate:
    """Aggregate tool-level EDA evidence into one delivery decision."""

    @staticmethod
    def assess(
        checks: dict[str, Any], *, has_testbench: bool, has_reference: bool
    ) -> dict[str, Any]:
        required = {"compile": checks.get("compile", {}).get("compile_success") is True}
        required["synthesis"] = checks.get("synthesis", {}).get("synthesis_success") is True
        if has_testbench:
            required["simulation"] = checks.get("simulation", {}).get("simulation_success") is True
        if has_reference:
            required["equivalence"] = checks.get("equivalence", {}).get("equivalence_success") is True
        passed = all(required.values())
        return {"passed": passed, "required": required, "failed": [name for name, ok in required.items() if not ok]}


class VerilogVerifier:
    def __init__(
        self,
        iverilog_path: str | None = None,
        vvp_path: str | None = None,
        yosys_path: str | None = None,
    ) -> None:
        self.iverilog_path = iverilog_path or shutil.which("iverilog")
        self.vvp_path = vvp_path or shutil.which("vvp")
        self.yosys_path = yosys_path or shutil.which("yosys")

    @staticmethod
    def _run(command: list[str], timeout: float) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=timeout,
            shell=False,
            check=False,
        )

    @staticmethod
    def _text(process: subprocess.CompletedProcess[str]) -> str:
        return "\n".join(x for x in (process.stdout, process.stderr) if x).strip()

    def verify(
        self,
        code: str,
        testbench: str | None = None,
        *,
        top_module: str = "TopModule",
        timeout: float = 20.0,
        synthesize: bool = False,
    ) -> dict[str, Any]:
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_$]*", top_module):
            raise ValueError("top_module is not a valid Verilog identifier")
        if not code.strip():
            raise ValueError("code must not be empty")
        if timeout <= 0:
            raise ValueError("timeout must be positive")

        started = time.monotonic()
        result: dict[str, Any] = {
            "tools": {
                "iverilog": bool(self.iverilog_path),
                "vvp": bool(self.vvp_path),
                "yosys": bool(self.yosys_path),
            },
            "compile_success": None,
            "simulation_success": None,
            "synthesis_success": None,
            "functionally_verified": False,
            "output": "",
        }
        try:
            with tempfile.TemporaryDirectory(prefix="octoverilog-") as temp:
                root = Path(temp)
                design = root / "design.sv"
                design.write_text(code, encoding="utf-8")
                outputs: list[str] = []

                if self.iverilog_path:
                    executable = root / "simulation.vvp"
                    command = [self.iverilog_path, "-g2012"]
                    if testbench is None:
                        command.extend(["-s", top_module])
                    command.extend(["-o", str(executable), str(design)])
                    if testbench is not None:
                        bench = root / "testbench.sv"
                        bench.write_text(testbench, encoding="utf-8")
                        command.append(str(bench))
                    compiled = self._run(command, timeout)
                    result["compile_success"] = compiled.returncode == 0
                    outputs.append(self._text(compiled))
                    if compiled.returncode == 0 and testbench is not None and self.vvp_path:
                        simulated = self._run([self.vvp_path, str(executable)], timeout)
                        result["simulation_success"] = simulated.returncode == 0
                        result["functionally_verified"] = simulated.returncode == 0
                        outputs.append(self._text(simulated))

                if synthesize and self.yosys_path:
                    script = (
                        f"read_verilog -sv {design.as_posix()}; "
                        f"hierarchy -check -top {top_module}; proc; check"
                    )
                    synthesized = self._run([self.yosys_path, "-p", script], timeout)
                    result["synthesis_success"] = synthesized.returncode == 0
                    outputs.append(self._text(synthesized))

                result["output"] = "\n".join(x for x in outputs if x)[-12000:]
        except subprocess.TimeoutExpired as error:
            result["error"] = "timeout"
            result["output"] = str(error)
        finally:
            result["elapsed_seconds"] = round(time.monotonic() - started, 6)
        return result
