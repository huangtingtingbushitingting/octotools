from octotools.tools.base import BaseTool
from octotools.verilog.generator import VerilogGenerator


class VerilogRepairTool(BaseTool):
    require_llm_engine = True

    def __init__(self, model_string=None):
        super().__init__(
            tool_name="VerilogRepairTool",
            tool_description="Repair a Verilog candidate using deterministic compiler, simulation, synthesis, or equivalence evidence from Memory.",
            tool_version="1.0.0",
            input_types={"specification": "str, required", "candidate_code": "str, required", "verification_feedback": "str, required", "top_module": "str", "temperature": "float", "max_tokens": "int"},
            output_type="dict containing corrected code and raw model response",
            demo_commands=[],
            model_string=model_string,
        )
        self.generator = VerilogGenerator(model=model_string)

    def execute(self, specification: str, candidate_code: str, verification_feedback: str, top_module: str = "TopModule", temperature: float = 0.2, max_tokens: int = 4096):
        feedback = f"Previous candidate:\n{candidate_code}\n\nTool evidence from Memory:\n{verification_feedback}"
        try:
            code, raw = self.generator.generate(specification, feedback, top_module=top_module, temperature=temperature, max_tokens=max_tokens)
            return {"success": True, "code": code, "raw_response": raw}
        except Exception as error:
            return {"success": False, "code": "", "error": f"{type(error).__name__}: {error}"}
