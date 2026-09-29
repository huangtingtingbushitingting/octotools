from octotools.verilog.error_taxonomy import classify_error, classification_metrics, ordered_categories
from octotools.verilog.selector import select_best_candidate
from octotools.verilog.training.inject_errors import inject_errors
from octotools.verilog.verifier import VerificationGate


def test_verifier_gate_requires_all_requested_checks():
    checks = {
        "compile": {"compile_success": True},
        "simulation": {"simulation_success": True},
        "synthesis": {"synthesis_success": False},
    }
    result = VerificationGate.assess(checks, has_testbench=True, has_reference=False)
    assert result["passed"] is False
    assert result["failed"] == ["synthesis"]


def test_taxonomy_returns_top2_and_structural_order():
    result = classify_error(
        {"compile": {"compile_success": False}},
        "wire x; always @* x = a;",
    )
    assert result["primary"] == "structural"
    assert "structural" in ordered_categories(result["labels"])
    assert len(result["top2"]) == 2


def test_selector_prefers_verified_candidate():
    candidates = [
        {"candidate_id": "bad", "score": 0.5, "code": "module TopModule; endmodule", "verification": {}},
        {"candidate_id": "good", "score": 1.0, "code": "module TopModule; assign x = y; endmodule", "verification": {}},
    ]
    assert select_best_candidate(candidates)["candidate_id"] == "good"


def test_directional_injection_produces_targeted_mutations():
    code = "module TopModule(input clk, input a, output reg y); always @(posedge clk) y <= a; endmodule"
    assert any(item["variant"] == "reg_to_wire" for item in inject_errors(code, "structural"))
    assert any(item["variant"] == "posedge_to_negedge" for item in inject_errors(code, "temporal_fsm"))


def test_classification_metrics_reports_accuracy_and_top2():
    rows = [
        {"label": "structural", "prediction": {"primary": "structural", "top2": ["structural", "general_complex"]}},
        {"label": "numeric_vector", "prediction": {"primary": "structural", "top2": ["structural", "numeric_vector"]}},
    ]
    result = classification_metrics(rows)
    assert result["accuracy"] == 0.5
    assert result["top2_recall"] == 1.0
