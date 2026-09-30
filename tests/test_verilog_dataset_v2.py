from octotools.verilog.training.injected_dataset import _mixed_mutation, _split_groups, _trim_after_last_module
from octotools.verilog.training.pairs import verification_feedback


def test_split_keeps_same_problem_across_source_models_together():
    rows = [
        {"problem_id": problem, "model": model}
        for problem, model in (
            ("Prob001", "gpt-3.5"),
            ("Prob001", "gpt-4"),
            ("Prob002", "gpt-4"),
            ("Prob003", "qwen"),
            ("Prob004", "qwen"),
            ("Prob005", "qwen"),
        )
    ]
    _split_groups(rows)
    assert rows[0]["split"] == rows[1]["split"]
    assert {row["split"] for row in rows} == {"train", "validation", "test"}


def test_mixed_injection_changes_structure_and_clock_edge():
    original = "module TopModule(input clk, output reg q); always @(posedge clk) q <= 1'b1; endmodule"
    mutated = _mixed_mutation(original)
    assert len(mutated) == 1
    assert mutated[0]["code"] != original
    assert "negedge clk" in mutated[0]["code"]
    assert "output wire q" in mutated[0]["code"]


def test_feedback_keeps_errors_without_temporary_paths():
    checks = {
        "compile": {
            "compile_success": False,
            "design_path": "/tmp/private/candidate.sv",
            "stderr": "/tmp/octoverilog-private/candidate.sv:7: error: signal not declared",
        },
        "gate_passed": False,
    }
    feedback = verification_feedback(checks)
    assert "signal not declared" in feedback
    assert "/tmp/private" not in feedback
    assert len(feedback) <= 3000


def test_reference_annotations_are_not_training_targets():
    code = "module TopModule; endmodule\n/* compile error in original model */"
    assert _trim_after_last_module(code) == "module TopModule; endmodule"
