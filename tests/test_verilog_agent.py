from octotools.models.memory import Memory
from octotools.verilog.agent import VerilogAgentPlanner, VerilogAgentSolver


def test_planner_requires_compile_synthesis_and_optional_dynamic_checks():
    planner = object.__new__(VerilogAgentPlanner)
    plan = planner.closed_loop_plan(has_testbench=True, has_reference=True)
    assert plan[:4] == ["VerilogGeneratorTool", "IverilogTool", "VvpTool", "YosysTool"]
    assert "YosysEquivalenceTool" in plan
    assert "VerilogRepairTool" in plan[-1]


def test_gate_cannot_be_bypassed_by_a_model_claim():
    checks = {
        "compile": {"compile_success": True},
        "simulation": {"simulation_success": False, "stdout": "model says PASS"},
        "synthesis": {"synthesis_success": True},
    }
    assert VerilogAgentSolver._passed(checks, has_testbench=True, has_reference=False) is False


def test_gate_requires_equivalence_when_reference_is_available():
    checks = {
        "compile": {"compile_success": True},
        "synthesis": {"synthesis_success": True},
        "equivalence": {"equivalence_success": False},
    }
    assert VerilogAgentSolver._passed(checks, has_testbench=False, has_reference=True) is False


def test_failed_candidate_is_repaired_from_memory_before_delivery(tmp_path):
    class Planner:
        def closed_loop_plan(self, **kwargs):
            return ["generate", "verify", "repair-or-stop"]

    class Executor:
        def __init__(self):
            self.generation_calls = []

        def set_workspace_dir(self, path):
            pass

        def execute_tool(self, name, **kwargs):
            if name in {"VerilogGeneratorTool", "VerilogRepairTool"}:
                self.generation_calls.append((name, kwargs))
                return {"success": True, "code": "module TopModule; endmodule", "raw_response": "raw"}
            if name == "IverilogTool":
                repaired = len(self.generation_calls) == 2
                return {"success": repaired, "compile_success": repaired, "stderr": "syntax error" if not repaired else ""}
            if name == "YosysTool":
                return {"success": True, "synthesis_success": True}
            raise AssertionError(name)

    solver = object.__new__(VerilogAgentSolver)
    solver.memory = Memory()
    solver.planner = Planner()
    solver.executor = Executor()
    solver.workspace_dir = str(tmp_path)
    solver.model = "stub"
    solver.attempts = 2

    result = solver.solve_verilog("Build it")

    assert result["verified"] is True
    assert [call[0] for call in solver.executor.generation_calls] == [
        "VerilogGeneratorTool",
        "VerilogRepairTool",
    ]
    repair_kwargs = solver.executor.generation_calls[1][1]
    assert "syntax error" in repair_kwargs["verification_feedback"]
    assert len(result["memory"]) == 6
