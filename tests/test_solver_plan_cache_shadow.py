from types import SimpleNamespace

from apc.models import PlanTemplate, TemplateStep
from octotools.models.memory import Memory
from octotools.solver import Solver


class FakePlanner:
    available_tools = ["Calculator"]
    toolbox_metadata = {"Calculator": {}}

    def __init__(self, conclusion: str = "STOP") -> None:
        self.conclusion = conclusion
        self.seen_prompt_context = None

    def analyze_query(self, question, image):
        return "Use a calculator"

    def generate_next_step(
        self,
        question,
        image,
        query_analysis,
        memory,
        step_count,
        max_steps,
    ):
        self.seen_prompt_context = memory.get_prompt_context()
        return "fake next step"

    def extract_context_subgoal_and_tool(self, response):
        return (
            "Numbers: 12 and 12",
            "Add the numbers",
            "Calculator",
        )

    def verificate_context(
        self,
        question,
        image,
        query_analysis,
        memory,
    ):
        return "verification result"

    def extract_conclusion(self, response):
        return "verification complete", self.conclusion

    def generate_direct_output(self, question, image, memory):
        return "24"


class FakeExecutor:
    def set_query_cache_dir(self, path):
        pass

    def generate_tool_command(
        self,
        question,
        image,
        context,
        sub_goal,
        tool_name,
        metadata,
    ):
        return "fake command"

    def extract_explanation_and_command(self, response):
        return (
            "analysis",
            "explanation",
            'execution = tool.execute(expression="12+12")',
        )

    def execute_tool_command(self, tool_name, command):
        return {"value": 24}


class FakeCacheManager:
    def __init__(
        self,
        *,
        hit: bool = False,
        raise_on_lookup: bool = False,
        raise_on_store: bool = False,
    ) -> None:
        self.hit = hit
        self.raise_on_lookup = raise_on_lookup
        self.raise_on_store = raise_on_store
        self.store_calls = 0
        self._size = 1 if hit else 0

    @property
    def size(self):
        return self._size

    def lookup(self, query, available_tools, *, has_image):
        if self.raise_on_lookup:
            raise RuntimeError("lookup unavailable")

        template = None
        if self.hit:
            template = PlanTemplate(
                source_query=query,
                category="arithmetic",
                steps=[
                    TemplateStep(
                        index=1,
                        description="Add the numbers",
                        tool_name="Calculator",
                    ),
                ],
            )

        return SimpleNamespace(
            query=query,
            keyword="arithmetic addition",
            cache_key=(
                "arithmetic addition"
                "|tools=fake"
                "|modality=text"
                "|schema=v1"
            ),
            template=template,
            hit=self.hit,
        )

    def store_successful_trace(
        self,
        lookup,
        actions,
        available_tools,
    ):
        self.store_calls += 1

        if self.raise_on_store:
            raise RuntimeError("storage unavailable")

        self._size = 1
        return object()


def make_solver(
    manager: FakeCacheManager,
    *,
    conclusion: str = "STOP",
) -> Solver:
    return Solver(
        planner=FakePlanner(conclusion=conclusion),
        memory=Memory(),
        executor=FakeExecutor(),
        output_types="direct",
        max_steps=1,
        verbose=False,
        plan_cache_manager=manager,
        plan_cache_mode="shadow",
    )


def make_solver_without_cache() -> Solver:
    return Solver(
        planner=FakePlanner(conclusion="STOP"),
        memory=Memory(),
        executor=FakeExecutor(),
        output_types="direct",
        max_steps=1,
        verbose=False,
        plan_cache_mode="off",
    )


def test_cache_off_still_runs_original_solver():
    result = make_solver_without_cache().solve("What is 12 plus 12?")

    assert result["direct_output"] == "24"
    assert result["conclusion"] == "STOP"
    assert "plan_cache" not in result


def test_assist_hit_injects_advisory_plan_guidance():
    manager = FakeCacheManager(hit=True)
    planner = FakePlanner(conclusion="STOP")
    solver = Solver(
        planner=planner,
        memory=Memory(),
        executor=FakeExecutor(),
        output_types="direct",
        max_steps=1,
        verbose=False,
        plan_cache_manager=manager,
        plan_cache_mode="assist",
    )

    result = solver.solve("What is 12 plus 12?")

    guidance = planner.seen_prompt_context["shared_across_attempts"][
        "plan_cache_guidance"
    ]
    assert result["plan_cache"]["guidance_injected"] is True
    assert result["plan_cache"]["step_decisions"][0]["action"] == "REUSE"
    assert guidance["steps"][0]["tool_name"] == "Calculator"


def test_assist_evidence_gate_can_be_ablated():
    shared_context = {
        "observations": [
            {
                "evidence_id": "attempt-1:Action Step 1",
                "tool_name": "Calculator",
                "sub_goal": "Add the numbers",
                "result": {"value": 24},
            }
        ]
    }

    gated_solver = Solver(
        planner=FakePlanner(conclusion="STOP"),
        memory=Memory(),
        executor=FakeExecutor(),
        output_types="direct",
        max_steps=1,
        verbose=False,
        plan_cache_manager=FakeCacheManager(hit=True),
        plan_cache_mode="assist",
        plan_cache_use_evidence=True,
    )
    ungated_solver = Solver(
        planner=FakePlanner(conclusion="STOP"),
        memory=Memory(),
        executor=FakeExecutor(),
        output_types="direct",
        max_steps=1,
        verbose=False,
        plan_cache_manager=FakeCacheManager(hit=True),
        plan_cache_mode="assist",
        plan_cache_use_evidence=False,
    )

    gated = gated_solver.solve("What is 12 plus 12?", shared_context=shared_context)
    ungated = ungated_solver.solve(
        "What is 12 plus 12?",
        shared_context=shared_context,
    )

    assert gated["plan_cache"]["step_decisions"][0]["action"] == "SKIP"
    assert ungated["plan_cache"]["step_decisions"][0]["action"] == "REUSE"


def test_cache_miss_stores_successful_trace():
    manager = FakeCacheManager(hit=False)
    solver = make_solver(manager)

    result = solver.solve("What is 12 plus 12?")

    assert result["direct_output"] == "24"
    assert result["plan_cache"]["hit"] is False
    assert result["plan_cache"]["template_stored"] is True
    assert result["plan_cache"]["cache_size"] == 1
    assert manager.store_calls == 1


def test_cache_hit_does_not_overwrite_template():
    manager = FakeCacheManager(hit=True)
    solver = make_solver(manager)

    result = solver.solve("What is 20 plus 30?")

    assert result["direct_output"] == "24"
    assert result["plan_cache"]["hit"] is True
    assert result["plan_cache"]["template_tools"] == ["Calculator"]
    assert result["plan_cache"]["template_stored"] is False
    assert manager.store_calls == 0


def test_lookup_error_does_not_break_original_solver():
    manager = FakeCacheManager(raise_on_lookup=True)
    solver = make_solver(manager)

    result = solver.solve("What is 12 plus 12?")

    assert result["direct_output"] == "24"
    assert "lookup failed" in result["plan_cache"]["error"]
    assert manager.store_calls == 0


def test_incomplete_trace_is_not_stored():
    manager = FakeCacheManager(hit=False)
    solver = make_solver(manager, conclusion="CONTINUE")

    result = solver.solve("What is 12 plus 12?")

    assert result["direct_output"] == "24"
    assert result["plan_cache"]["template_stored"] is False
    assert manager.store_calls == 0


def test_storage_error_does_not_break_original_solver():
    manager = FakeCacheManager(
        hit=False,
        raise_on_store=True,
    )
    solver = make_solver(manager)

    result = solver.solve("What is 12 plus 12?")

    assert result["direct_output"] == "24"
    assert "template storage failed" in result["plan_cache"]["error"]


def test_solve_resets_old_memory_actions():
    manager = FakeCacheManager(hit=False)
    solver = make_solver(manager)

    solver.memory.add_action(
        99,
        "OldTool",
        "Old goal",
        "old command",
        "old result",
    )

    result = solver.solve("What is 12 plus 12?")

    assert list(result["memory"]) == ["Action Step 1"]
    assert "Action Step 99" not in result["memory"]
