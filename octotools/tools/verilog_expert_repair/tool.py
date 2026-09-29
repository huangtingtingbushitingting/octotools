"""Route failed RTL to a category-specific repair LoRA served by vLLM."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from octotools.tools.base import BaseTool
from octotools.verilog.generator import VerilogGenerator


class VerilogExpertRepairTool(BaseTool):
    require_llm_engine = True

    def __init__(self, model_string=None):
        super().__init__(
            tool_name="VerilogExpertRepairTool",
            tool_description=(
                "Repair failed RTL with a category-specific LoRA adapter; use only "
                "after deterministic EDA evidence identifies the error category."
            ),
            tool_version="1.0.0",
            input_types={
                "specification": "str, required",
                "candidate_code": "str, required",
                "verification_feedback": "str, required",
                "error_category": "str, required",
                "expert_family": "str | None",
                "registry_path": "str | None",
                "strict_expert": "bool",
                "top_module": "str",
                "temperature": "float",
                "max_tokens": "int",
            },
            output_type="dict containing corrected code, model routing, and usage",
            demo_commands=[],
            model_string=model_string,
        )
        self.base_model = str(model_string)

    @staticmethod
    def _registry(path: str | None) -> dict[str, Any]:#加载专家注册表
        value = path or os.environ.get("OCTOVERILOG_EXPERT_REGISTRY")#如果path为空，尝试从环境变量OCTOVERILOG_EXPERT_REGISTRY"中读取
        if not value:
            return {}
        registry_path = Path(value).expanduser()
        return json.loads(registry_path.read_text(encoding="utf-8"))

    @staticmethod
    def _model_name(value: str) -> str:#规范化模型名称
        return value if value.startswith("vllm-") else f"vllm-{value}"

    def execute(#核心执行方法，根据错误类型选择对应的lora专家，并处理回退逻辑
        self,
        specification: str,
        candidate_code: str,
        verification_feedback: str,
        error_category: str,
        expert_family: str | None = None,
        registry_path: str | None = None,#专家注册表路径
        strict_expert: bool = False,#是否是严格模式，若严格模式，专家不可用或者失败时不可以退回
        top_module: str = "TopModule",
        temperature: float = 0.2,
        max_tokens: int = 4096,
    ):
        registry = self._registry(registry_path)
        experts = registry.get("experts") or {}
        entry = experts.get(error_category) or experts.get(expert_family or "") or {}#优先具体错误，再回退到四类专家
        expert_model = entry.get("model") if entry.get("enabled", True) else None
        if strict_expert and not expert_model:#如果启动了严格模式，但没有找到可用的专家，直接返回失败
            return {
                "success": False,
                "code": "",
                "error": f"no enabled expert registered for {error_category}",
            "error_category": error_category,
            "expert_family": expert_family,
                "expert_used": False,
            }
        requested_model = self._model_name(str(expert_model)) if expert_model else self.base_model
        feedback = (
            f"Error category: {error_category}\n\n"
            f"Previous candidate:\n{candidate_code}\n\n"
            f"Tool evidence from Memory:\n{verification_feedback}"
        )#充当VerilogGenerator生成代码时的提示词
        try:#正式修复代码，并返回结果
            generator = VerilogGenerator(model=requested_model)
            code, raw = generator.generate(
                specification,
                feedback,
                top_module=top_module,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            return {
                "success": True,
                "code": code,
                "raw_response": raw,
                "model": requested_model,
                "model_input": generator.last_prompt,
                "usage": generator.last_usage,
                "error_category": error_category,
                "expert_used": bool(expert_model),
            }
        except Exception as error:
            if strict_expert or requested_model == self.base_model:#如果指定类别没有专家，可用选择使用基础模型进行修复
                return {
                    "success": False,
                    "code": "",
                    "error": f"{type(error).__name__}: {error}",
                    "model": requested_model,
                    "error_category": error_category,
                    "expert_used": bool(expert_model),
                }
            fallback = VerilogGenerator(model=self.base_model)
            try:
                code, raw = fallback.generate(
                    specification,
                    feedback,
                    top_module=top_module,
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
                return {
                    "success": True,
                    "code": code,
                    "raw_response": raw,
                    "model": self.base_model,
                    "model_input": fallback.last_prompt,
                    "usage": fallback.last_usage,
                    "error_category": error_category,
                    "expert_used": False,
                    "fallback_reason": f"{type(error).__name__}: {error}",
                }
            except Exception as fallback_error:
                return {
                    "success": False,
                    "code": "",
                    "error": f"{type(fallback_error).__name__}: {fallback_error}",
                    "model": self.base_model,
                    "error_category": error_category,
                    "expert_used": False,
                }
