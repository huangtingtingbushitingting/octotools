"""LLM adapter and response extraction for Verilog generation."""

from __future__ import annotations

import re
from collections.abc import Callable
from typing import Any

from octotools.engine.factory import create_llm_engine


def extract_verilog(response: str) -> str:
    """Extract the last complete Verilog module from common model formats."""
    if not isinstance(response, str) or not response.strip():
        raise ValueError("model returned an empty response")

    fenced = re.findall(
        r"```(?:systemverilog|verilog|sv)?\s*(.*?)```",
        response,
        flags=re.IGNORECASE | re.DOTALL,
    )
    candidates = fenced or re.findall(
        r"\[BEGIN\]\s*(.*?)\s*\[(?:DONE|END)\]",
        response,
        flags=re.IGNORECASE | re.DOTALL,
    )
    source = candidates[-1].strip() if candidates else response.strip()
    modules = list(re.finditer(r"\bmodule\b", source, re.IGNORECASE))
    ends = list(re.finditer(r"\bendmodule\b", source, re.IGNORECASE))
    if not modules or not ends or ends[-1].end() <= modules[0].start():
        raise ValueError("model response does not contain a complete Verilog module")
    return source[modules[0].start() : ends[-1].end()].strip()


class VerilogGenerator:
    """Generate Verilog through an OctoTools engine or an injected callable."""

    SYSTEM_PROMPT = (
        "You are an expert RTL designer. Return only synthesizable Verilog or "
        "SystemVerilog in one fenced code block. Preserve the requested module "
        "name and port interface exactly. Do not include a testbench unless the "
        "specification explicitly asks for one."
    )

    def __init__(
        self,
        model: str | None = None,
        engine: Callable[..., str] | None = None,
    ) -> None:
        if engine is None and not model:
            raise ValueError("either model or engine is required")
        self.model = model or "injected-engine"
        self.engine = engine or create_llm_engine(
            model_string=str(model), use_cache=False, is_multimodal=False
        )

    def generate(
        self,
        specification: str,
        feedback: str | None = None,
        *,
        temperature: float = 0.2,
        max_tokens: int = 4096,
    ) -> tuple[str, str]:
        prompt = f"{self.SYSTEM_PROMPT}\n\nSpecification:\n{specification.strip()}"
        if feedback:
            prompt += (
                "\n\nThe previous candidate failed deterministic verification. "
                "Correct the design using this evidence:\n" + feedback[-6000:]
            )
        kwargs: dict[str, Any] = {
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        raw = str(self.engine(prompt, **kwargs))
        return extract_verilog(raw), raw
