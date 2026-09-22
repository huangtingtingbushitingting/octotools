"""OctoTools Agent control layer for closed-loop Verilog generation."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from octotools.models.executor import Executor
from octotools.models.initializer import Initializer
from octotools.models.memory import Memory
from octotools.models.planner import Planner
from octotools.solver import Solver

from .progress import PipelineEvent, ProgressCallback


TOOLS = [
    "verilog_generator",
    "verilog_repair",
    "iverilog",
    "vvp",
    "yosys",
    "yosys_equivalence",
    "verilog_search",
]


class VerilogAgentPlanner(Planner):
    """Planner with a mandatory, non-skippable hardware verification plan."""

    def closed_loop_plan(self, *, has_testbench: bool, has_reference: bool) -> list[str]:
        plan = ["VerilogGeneratorTool", "IverilogTool"]
        if has_testbench:
            plan.append("VvpTool")
        plan.append("YosysTool")
        if has_reference:
            plan.append("YosysEquivalenceTool")
        plan.append("STOP only when every required tool reports success; otherwise VerilogRepairTool and repeat")
        return plan


class VerilogAgentSolver(Solver):
    """Use Solver/Planner/Executor/Memory with deterministic verification gates."""

    def __init__(self, model: str, attempts: int = 3, workspace_dir: str = "runs/agent-work", verbose: bool = True):
        initializer = Initializer(enabled_tools=TOOLS, model_string=model, verbose=verbose)
        planner = VerilogAgentPlanner(model, initializer.toolbox_metadata, initializer.available_tools, verbose)
        memory = Memory()
        executor = Executor(model, workspace_dir=workspace_dir, verbose=verbose)
        super().__init__(planner, memory, executor, output_types="direct", max_steps=attempts, workspace_dir=workspace_dir, verbose=verbose)
        self.model = model
        self.attempts = attempts

    @staticmethod
    def _feedback(checks: dict[str, Any]) -> str:
        return json.dumps(checks, ensure_ascii=False, indent=2)[-12000:]

    @staticmethod
    def _passed(checks: dict[str, Any], *, has_testbench: bool, has_reference: bool) -> bool:
        if checks.get("compile", {}).get("compile_success") is not True:
            return False
        if checks.get("synthesis", {}).get("synthesis_success") is not True:
            return False
        if has_testbench and checks.get("simulation", {}).get("simulation_success") is not True:
            return False
        if has_reference and checks.get("equivalence", {}).get("equivalence_success") is not True:
            return False
        return True

    def solve_verilog(
        self,
        specification: str,
        testbench: str | None = None,
        *,
        reference_code: str | None = None,
        top_module: str = "TopModule",
        temperature: float = 0.2,
        max_tokens: int = 4096,
        progress: ProgressCallback | None = None,
    ) -> dict[str, Any]:
        self.memory.clear()
        self.memory.set_query(specification)
        Path(self.workspace_dir).mkdir(parents=True, exist_ok=True)
        self.executor.set_workspace_dir(self.workspace_dir)
        plan = self.planner.closed_loop_plan(has_testbench=testbench is not None, has_reference=reference_code is not None)
        history = []
        candidate = ""
        feedback = ""
        step = 0
        started = time.monotonic()

        def emit(stage: str, message: str, attempt: int | None = None, **details):
            if progress:
                progress(PipelineEvent(stage, message, attempt, details))

        emit("start", f"Planner created mandatory plan: {' -> '.join(plan)}")
        for attempt in range(1, self.attempts + 1):
            generation_tool = "VerilogGeneratorTool" if attempt == 1 else "VerilogRepairTool"
            emit("generate", f"Executor is calling {generation_tool}.", attempt)
            kwargs = dict(specification=specification, top_module=top_module, temperature=temperature, max_tokens=max_tokens)
            if attempt > 1:
                kwargs.update(candidate_code=candidate, verification_feedback=feedback)
            generated = self.executor.execute_tool(generation_tool, **kwargs)
            step += 1
            self.memory.add_evidence(step, generation_tool, f"Generate candidate {attempt}", generated)
            if not generated.get("success") or not generated.get("code"):
                history.append({"attempt": attempt, "generation": generated})
                feedback = self._feedback({"generation": generated})
                emit("error", feedback, attempt)
                continue

            candidate = generated["code"]
            emit("generated", f"Candidate {attempt} contains {len(candidate)} characters.", attempt)
            checks = {}
            compile_result = self.executor.execute_tool(
                "IverilogTool", source_code=candidate, top_module=top_module,
                testbench=testbench, candidate_name=f"attempt_{attempt:02d}",
            )
            checks["compile"] = compile_result
            step += 1
            self.memory.add_evidence(step, "IverilogTool", "Compile candidate and testbench", compile_result)

            artifact = compile_result.get("artifact_path")
            if testbench is not None and artifact:
                simulation = self.executor.execute_tool("VvpTool", artifact_path=artifact)
                checks["simulation"] = simulation
                step += 1
                self.memory.add_evidence(step, "VvpTool", "Run self-checking testbench", simulation)

            synthesis = self.executor.execute_tool(
                "YosysTool", source_code=candidate, top_module=top_module,
                candidate_name=f"attempt_{attempt:02d}",
            )
            checks["synthesis"] = synthesis
            step += 1
            self.memory.add_evidence(step, "YosysTool", "Synthesize and structurally check candidate", synthesis)

            if reference_code is not None:
                equivalence = self.executor.execute_tool(
                    "YosysEquivalenceTool", candidate_code=candidate,
                    reference_code=reference_code, top_module=top_module,
                )
                checks["equivalence"] = equivalence
                step += 1
                self.memory.add_evidence(step, "YosysEquivalenceTool", "Prove candidate equivalent to reference RTL", equivalence)

            passed = self._passed(checks, has_testbench=testbench is not None, has_reference=reference_code is not None)
            history.append({
                "attempt": attempt,
                "code": candidate,
                "raw_response": generated.get("raw_response", ""),
                "verification": checks,
                "gate_passed": passed,
            })
            emit("verified", f"Mandatory verification gate passed={passed}.", attempt, evidence=checks)
            if passed:
                emit("complete", f"Closed loop completed in {time.monotonic() - started:.2f}s.", attempt, verified=True)
                return {"code": candidate, "verified": True, "attempts": history, "model": self.model, "plan": plan, "memory": self.memory.get_actions()}
            feedback = self._feedback(checks)
            if attempt < self.attempts:
                emit("retry", "Verifier rejected the candidate; Memory evidence is being sent to VerilogRepairTool.", attempt)

        emit("error", "No candidate passed every mandatory verification gate; delivery is blocked.")
        return {"code": "", "last_candidate": candidate, "verified": False, "attempts": history, "model": self.model, "plan": plan, "memory": self.memory.get_actions()}
