import json

from octotools.verilog.training.errors import classify_failure
from octotools.verilog.training.pairs import build_pairs
from octotools.verilog.training.ranking import rank_candidates


def test_wire_in_always_error_is_routed_to_expert():
    checks = {
        "compile": {
            "compile_success": False,
            "stderr": "out is not a valid l-value; out is declared here as wire",
        }
    }
    assert classify_failure(checks, "module TopModule; endmodule") == "wire_in_always_block"


def test_ranking_prefers_fully_verified_then_shorter_candidate():
    candidates = [
        {
            "candidate_id": "bad",
            "code": "module TopModule; endmodule",
            "verification": {
                "compile": {"compile_success": True},
                "simulation": {"simulation_success": False},
                "synthesis": {"synthesis_success": True},
            },
        },
        {
            "candidate_id": "good",
            "code": "module TopModule; endmodule",
            "verification": {
                "compile": {"compile_success": True},
                "simulation": {"simulation_success": True},
                "synthesis": {"synthesis_success": True},
            },
        },
    ]
    ranked = rank_candidates(candidates, has_testbench=True, has_reference=False)
    assert ranked[0]["candidate_id"] == "good"
    assert ranked[0]["score"] == 1.0


def test_only_verified_child_becomes_repair_pair(tmp_path):
    trace = tmp_path / "trace.jsonl"
    rows = [
        {
            "run_id": "run",
            "task_id": "task",
            "candidate_id": "failed",
            "parent_candidate_id": None,
            "model_name": "base",
            "extracted_code": "module TopModule; bad endmodule",
            "verification": {"compile": {"compile_success": False}},
            "gate_passed": False,
            "error_category": "compile_error",
            "metadata": {"specification": "Build a module"},
        },
        {
            "run_id": "run",
            "task_id": "task",
            "candidate_id": "fixed",
            "parent_candidate_id": "failed",
            "model_name": "expert",
            "extracted_code": "module TopModule; endmodule",
            "verification": {"compile": {"compile_success": True}},
            "gate_passed": True,
            "error_category": "unclassified",
            "metadata": {"specification": "Build a module"},
        },
    ]
    trace.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
    pairs = build_pairs(trace)
    assert len(pairs) == 1
    assert pairs[0].incorrect_code.endswith("bad endmodule")
    assert pairs[0].repaired_code.endswith("endmodule")
