import pytest

from octotools.verilog.generator import VerilogGenerator, extract_verilog


def test_extracts_fenced_and_codev_begin_done_formats():
    assert extract_verilog("```verilog\nmodule A; endmodule\n```") == "module A; endmodule"
    assert extract_verilog("[BEGIN]\nmodule B; endmodule\n[DONE]") == "module B; endmodule"


def test_rejects_incomplete_response():
    with pytest.raises(ValueError, match="complete Verilog module"):
        extract_verilog("always_comb begin x = y; end")


def test_generator_includes_verifier_feedback():
    prompts = []

    def engine(prompt, **kwargs):
        prompts.append((prompt, kwargs))
        return "```sv\nmodule TopModule; endmodule\n```"

    generator = VerilogGenerator(engine=engine)
    code, _ = generator.generate("Build it", "syntax error", temperature=0.1)
    assert code == "module TopModule; endmodule"
    assert "syntax error" in prompts[0][0]
    assert prompts[0][1]["temperature"] == 0.1
