"""Two-stage RTL error localization, adapted from RTLerror-analysis.RTL错误定位第一阶段-让模型根据设计描述、错误 RTL 和验证反馈，标记出可疑的 RTL 语句"""

from __future__ import annotations

import re

from octotools.tools.base import BaseTool
from octotools.engine.factory import create_llm_engine


class VerilogLocalizerTool(BaseTool):
    """Ask the model to mark suspicious RTL statements before repair."""

    require_llm_engine = True

    def __init__(self, model_string=None):#初始化工具和创建LLM 引擎
        super().__init__(
            tool_name="VerilogLocalizerTool",
            tool_description=(
                "First stage of RTLerror-analysis: annotate suspicious RTL lines "
                "using compiler, simulation, or synthesis feedback."
            ),
            tool_version="1.0.0",
            input_types={
                "specification": "str, required",
                "candidate_code": "str, required",
                "verification_feedback": "str, required",
                "top_module": "str",
                "temperature": "float",
                "max_tokens": "int",
            },
            output_type="dict containing localized RTL and raw response",
            demo_commands=[],
            model_string=model_string,
        )
        self.model = model_string
        self.engine = create_llm_engine(
            model_string=model_string, use_cache=False, is_multimodal=False
        )

    def execute(
        self,
        specification: str,#设计描述
        candidate_code: str,#错误RTL
        verification_feedback: str,#编译和仿真反馈
        top_module: str = "TopModule",
        temperature: float = 0.1,
        max_tokens: int = 2048,
    ):
        prompt = f"""You are an RTL debugging expert. Perform the localization stage only.
Mark suspicious statements in the candidate with // ERROR: <short reason> comments.
Preserve the complete module and ports. Do not propose a replacement yet.

Design specification:
{specification}

Verifier feedback:
{verification_feedback[-8000:]}

Candidate RTL:
```verilog
{candidate_code}
```
Return the complete annotated Verilog module in one code block."""
        try:
            raw = str(self.engine(prompt, temperature=temperature, max_tokens=max_tokens))#标出可疑的RTL语句
            match = re.findall(r"```(?:systemverilog|verilog|sv)?\s*(.*?)```", raw, re.I | re.S)
            localized = (match[-1] if match else raw).strip()
            return {
                "success": bool(localized),
                "localized_code": localized,
                "raw_response": raw,
                "model": self.model,
                "model_input": prompt,
                "usage": dict(getattr(self.engine, "last_usage", {}) or {}),
            }
        except Exception as error:
            return {"success": False, "localized_code": "", "error": f"{type(error).__name__}: {error}"}
