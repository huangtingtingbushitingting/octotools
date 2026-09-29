from octotools.tools.base import BaseTool
from octotools.verilog.generator import VerilogGenerator


class VerilogGeneratorTool(BaseTool):
    require_llm_engine = True

    def __init__(self, model_string=None):
        super().__init__(
            tool_name="VerilogGeneratorTool",
            tool_description="Generate a complete synthesizable Verilog candidate from an RTL specification using CodeV-R1.",
            tool_version="1.0.0",
            input_types={"specification": "str, required", "top_module": "str", "temperature": "float", "max_tokens": "int"},
            output_type="dict containing extracted code and raw model response",
            demo_commands=[],
            model_string=model_string,
        )
        self.generator = VerilogGenerator(model=model_string)

    def execute(self, specification: str, top_module: str = "TopModule", temperature: float = 0.2, max_tokens: int = 4096):
        try:
            code, raw = self.generator.generate(specification, top_module=top_module, temperature=temperature, max_tokens=max_tokens)
            return {
                "success": True,
                "code": code,
                "raw_response": raw,
                "model": self.generator.model,
                "model_input": self.generator.last_prompt,
                "usage": self.generator.last_usage,
            }
        except Exception as error:
            return {"success": False, "code": "", "error": f"{type(error).__name__}: {error}"}
