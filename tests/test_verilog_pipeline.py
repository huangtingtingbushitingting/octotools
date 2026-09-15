from octotools.verilog.generator import VerilogGenerator
from octotools.verilog.pipeline import VerilogPipeline


class StubVerifier:
    def __init__(self):
        self.calls = 0

    def verify(self, code, testbench=None, **kwargs):
        self.calls += 1
        return {
            "compile_success": self.calls > 1,
            "functionally_verified": self.calls > 1,
            "output": "syntax error" if self.calls == 1 else "PASS",
        }


def test_pipeline_retries_with_deterministic_feedback():
    prompts = []

    def engine(prompt, **kwargs):
        prompts.append(prompt)
        return "```verilog\nmodule TopModule; endmodule\n```"

    pipeline = VerilogPipeline(
        VerilogGenerator(engine=engine), verifier=StubVerifier(), attempts=3
    )
    result = pipeline.run("Build a module", "module tb; endmodule")
    assert result.verified is True
    assert len(result.attempts) == 2
    assert "syntax error" in prompts[1]
