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


def test_pipeline_emits_octotools_style_progress_events():
    events = []
    prompts = []

    def engine(prompt, **kwargs):
        prompts.append(prompt)
        return "```verilog\nmodule NaturalLanguageTop; endmodule\n```"

    class CompileVerifier:
        def verify(self, code, testbench=None, **kwargs):
            return {
                "compile_success": True,
                "simulation_success": None,
                "synthesis_success": None,
                "functionally_verified": False,
                "output": "",
            }

    pipeline = VerilogPipeline(
        VerilogGenerator(engine=engine),
        verifier=CompileVerifier(),
    )
    result = pipeline.run(
        "Create a combinational circuit from this natural-language request.",
        top_module="NaturalLanguageTop",
        progress=events.append,
    )

    assert result.code.startswith("module NaturalLanguageTop")
    assert [event.stage for event in events] == [
        "start",
        "generate",
        "generated",
        "verify",
        "verified",
        "complete",
    ]
    assert "Required top module: NaturalLanguageTop" in prompts[0]


def test_pipeline_returns_empty_result_when_all_extractions_fail():
    pipeline = VerilogPipeline(
        VerilogGenerator(engine=lambda prompt, **kwargs: "thinking without code"),
        attempts=2,
    )

    result = pipeline.run("Build a module")

    assert result.code == ""
    assert result.verified is False
    assert len(result.attempts) == 2
