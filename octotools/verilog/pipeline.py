"""Generate, verify, and repair Verilog candidates."""

from __future__ import annotations

import time
from dataclasses import asdict, dataclass
from typing import Any

from .agent import VerilogAgentSolver
from .generator import VerilogGenerator
from .progress import PipelineEvent, ProgressCallback
from .verifier import VerilogVerifier


@dataclass(frozen=True)
class PipelineResult:
    code: str
    verified: bool
    attempts: list[dict[str, Any]]
    model: str
    plan: list[str] | None = None
    memory: dict[str, Any] | None = None
    last_candidate: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class VerilogPipeline:
    def __init__(
        self,
        generator: VerilogGenerator | None,
        verifier: VerilogVerifier | None = None,
        *,
        attempts: int = 1,
        agent_solver: VerilogAgentSolver | None = None,
    ) -> None:
        if attempts < 1:
            raise ValueError("attempts must be at least 1")
        if generator is None and agent_solver is None:
            raise ValueError("generator or agent_solver is required")
        self.generator = generator
        self.verifier = verifier or VerilogVerifier()
        self.attempts = attempts
        self.agent_solver = agent_solver

    @classmethod
    def from_model(
        cls,
        model: str,
        *,
        attempts: int = 1,
        workspace_dir: str = "runs/agent-work",
        verbose: bool = True,
    ) -> "VerilogPipeline":
        agent = VerilogAgentSolver(model, attempts, workspace_dir, verbose)
        return cls(None, attempts=attempts, agent_solver=agent)

    def run(
        self,
        specification: str,
        testbench: str | None = None,
        *,
        reference_code: str | None = None,
        top_module: str = "TopModule",
        synthesize: bool = False,
        temperature: float = 0.2,
        max_tokens: int = 4096,
        progress: ProgressCallback | None = None,
    ) -> PipelineResult:
        if not specification.strip():
            raise ValueError("specification must not be empty")

        if self.agent_solver is not None:
            result = self.agent_solver.solve_verilog(
                specification,
                testbench,
                reference_code=reference_code,
                top_module=top_module,
                temperature=temperature,
                max_tokens=max_tokens,
                progress=progress,
            )
            return PipelineResult(
                code=result.get("code", ""),
                verified=bool(result.get("verified")),
                attempts=result.get("attempts", []),
                model=result.get("model", self.agent_solver.model),
                plan=result.get("plan"),
                memory=result.get("memory"),
                last_candidate=result.get("last_candidate"),
            )

        def emit(
            stage: str,
            message: str,
            *,
            attempt: int | None = None,
            **details: Any,
        ) -> None:
            if progress is not None:
                progress(
                    PipelineEvent(
                        stage=stage,
                        message=message,
                        attempt=attempt,
                        details=details,
                    )
                )

        history: list[dict[str, Any]] = []
        feedback: str | None = None
        selected = ""
        pipeline_started = time.monotonic()
        emit(
            "start",
            f"Received RTL specification for top module {top_module}.",
            attempts=self.attempts,
        )

        for number in range(1, self.attempts + 1):
            attempt_started = time.monotonic()
            emit(
                "generate",
                "Generating a synthesizable Verilog candidate...",
                attempt=number,
            )
            try:
                code, raw = self.generator.generate(  # type: ignore[union-attr]
                    specification,
                    feedback,
                    top_module=top_module,
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
            except ValueError as error:
                history.append({"attempt": number, "generation_error": str(error)})
                feedback = str(error)
                emit("error", str(error), attempt=number)
                continue

            selected = code
            emit(
                "generated",
                (
                    f"Extracted {len(code)} characters of Verilog code "
                    f"in {time.monotonic() - attempt_started:.2f}s."
                ),
                attempt=number,
                raw_characters=len(raw),
                code_characters=len(code),
            )
            checks = ["compile"]
            if testbench is not None:
                checks.append("simulation")
            if synthesize:
                checks.append("synthesis")
            emit(
                "verify",
                "Running deterministic " + ", ".join(checks) + " checks...",
                attempt=number,
            )
            evidence = self.verifier.verify(
                code,
                testbench,
                top_module=top_module,
                synthesize=synthesize,
            )
            history.append(
                {
                    "attempt": number,
                    "code": code,
                    "raw_response": raw,
                    "verification": evidence,
                }
            )
            summary = (
                f"compile={evidence.get('compile_success')}, "
                f"simulation={evidence.get('simulation_success')}, "
                f"synthesis={evidence.get('synthesis_success')}, "
                f"functional={evidence.get('functionally_verified')} "
                f"[{float(evidence.get('elapsed_seconds') or 0):.2f}s]"
            )
            emit("verified", summary, attempt=number, evidence=evidence)
            if evidence["functionally_verified"]:
                break
            if testbench is None and evidence["compile_success"] is True:
                break
            feedback = evidence.get("output") or "No verifier is installed. Review syntax and interface."
            if number < self.attempts:
                emit(
                    "retry",
                    "Verification did not pass; feeding tool evidence back to the model.",
                    attempt=number,
                )

        if not selected:
            emit("error", "All model responses failed Verilog extraction.")
            return PipelineResult(
                code="",
                verified=False,
                attempts=history,
                model=self.generator.model,  # type: ignore[union-attr]
            )
        verified = bool(history[-1].get("verification", {}).get("functionally_verified"))
        final_evidence = history[-1].get("verification", {})
        if verified:
            message = "Generation completed and passed functional verification."
        elif final_evidence.get("compile_success") is True and testbench is None:
            message = "Generation completed and passed syntax compilation."
        else:
            message = "Generation completed; inspect the verification report for failures."
        message += f" Total time: {time.monotonic() - pipeline_started:.2f}s."
        emit("complete", message, verified=verified)
        return PipelineResult(selected, verified, history, self.generator.model)  # type: ignore[union-attr]
