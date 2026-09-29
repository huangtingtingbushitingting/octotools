"""LLM adapter and response extraction for Verilog generation."""

from __future__ import annotations

import re
from collections.abc import Callable
from typing import Any

from octotools.engine.factory import create_llm_engine


def extract_verilog(response: str) -> str:#提取完整的verilog模块
    """Extract complete Verilog modules from common and malformed formats."""
    if not isinstance(response, str) or not response.strip():
        raise ValueError("model returned an empty response")

    fenced = re.findall(
        r"```(?:systemverilog|verilog|sv)?\s*(.*?)```",
        response,
        flags=re.IGNORECASE | re.DOTALL,
    )
    marked = re.findall(
        r"\[BEGIN\]\s*(.*?)\s*\[(?:DONE|END)\]",
        response,
        flags=re.IGNORECASE | re.DOTALL,
    )

    candidates = [*reversed(fenced), *reversed(marked), response]
    for candidate in candidates:
        source = re.sub(
            r"(?m)^[ \t]*```[^\r\n]*\r?\n?",
            "",
            candidate,
        ).strip()
        modules = list(
            re.finditer(
                r"\bmodule\s+(?:automatic\s+)?[A-Za-z_][A-Za-z0-9_$]*",
                source,
                flags=re.IGNORECASE,
            )
        )
        ends = list(
            re.finditer(
                r"\bendmodule\b",
                source,
                flags=re.IGNORECASE,
            )
        )
        if modules and ends and ends[-1].end() > modules[0].start():
            return source[modules[0].start() : ends[-1].end()].strip()

    raise ValueError("model response does not contain a complete Verilog module")


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
        )#创建生成RTL的LLM实例
        self.last_prompt = ""
        self.last_usage: dict[str, Any] = {}

    def generate(
        self,
        specification: str,
        feedback: str | None = None,#包含编译错误、仿真错误、综合错误、定位结果和 RAG 示例
        *,
        top_module: str = "TopModule",
        temperature: float = 0.2,
        max_tokens: int = 4096,
    ) -> tuple[str, str]:
        prompt = (
            f"{self.SYSTEM_PROMPT}\n\n"
            f"Required top module: {top_module}\n\n"
            f"Specification:\n{specification.strip()}"
        )
        if feedback:
            prompt += (
                "\n\nThe previous candidate failed deterministic verification. "
                "Correct the design using this evidence:\n" + feedback[-6000:]
            )#将前一轮候选代码加入修复提示词中，引导模型基于失败证据进行修复
        kwargs: dict[str, Any] = {
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        self.last_prompt = prompt
        raw = str(self.engine(prompt, **kwargs))#LLM生成RTL
        self.last_usage = dict(getattr(self.engine, "last_usage", {}) or {})
        return extract_verilog(raw), raw
