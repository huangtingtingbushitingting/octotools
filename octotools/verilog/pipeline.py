"""Generate, verify, and repair Verilog candidates."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from .generator import VerilogGenerator
from .verifier import VerilogVerifier


@dataclass(frozen=True)
class PipelineResult:
    code: str
    verified: bool
    attempts: list[dict[str, Any]]
    model: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class VerilogPipeline:
    def __init__(
        self,
        generator: VerilogGenerator,
        verifier: VerilogVerifier | None = None,
        *,
        attempts: int = 1,
    ) -> None:
        if attempts < 1:
            raise ValueError("attempts must be at least 1")
        self.generator = generator
        self.verifier = verifier or VerilogVerifier()
        self.attempts = attempts

    @classmethod
    def from_model(cls, model: str, *, attempts: int = 1) -> "VerilogPipeline":
        return cls(VerilogGenerator(model=model), attempts=attempts)

    def run(
        self,
        specification: str,
        testbench: str | None = None,
        *,
        top_module: str = "TopModule",
        synthesize: bool = False,
        temperature: float = 0.2,
        max_tokens: int = 4096,
    ) -> PipelineResult:
        if not specification.strip():
            raise ValueError("specification must not be empty")
        history: list[dict[str, Any]] = []
        feedback: str | None = None
        selected = ""

        for number in range(1, self.attempts + 1):
            try:
                code, raw = self.generator.generate(
                    specification,
                    feedback,
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
            except ValueError as error:
                history.append({"attempt": number, "generation_error": str(error)})
                feedback = str(error)
                continue

            selected = code
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
            if evidence["functionally_verified"]:
                break
            if testbench is None and evidence["compile_success"] is True:
                break
            feedback = evidence.get("output") or "No verifier is installed. Review syntax and interface."

        if not selected:
            raise RuntimeError("all model responses failed Verilog extraction")
        verified = bool(history[-1].get("verification", {}).get("functionally_verified"))
        return PipelineResult(selected, verified, history, self.generator.model)
