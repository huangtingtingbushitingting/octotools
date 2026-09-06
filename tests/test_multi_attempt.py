from octotools.models.memory import Memory
from octotools.research.multi_attempt import (
    AttemptBudget,
    MemorySharingPolicy,
    MultiAttemptController,
)


class FakeSolver:
    def __init__(self, result, received_contexts):
        self.result = result
        self.received_contexts = received_contexts

    def solve(self, question, image_path=None, shared_context=None):
        self.received_contexts.append(shared_context)
        return self.result


def test_memory_separates_shared_evidence_from_current_actions():
    memory = Memory()
    memory.set_shared_context({"observations": [{"result": "prior"}]})
    memory.add_action(1, "Tool", "goal", "command", "current")

    context = memory.get_prompt_context()

    assert context["shared_across_attempts"]["observations"][0]["result"] == "prior"
    assert context["current_attempt_actions"]["Action Step 1"]["result"] == "current"


def test_controller_shares_observations_and_failures_with_next_attempt():
    contexts = []
    results = [
        {
            "memory": {
                "Action Step 1": {
                    "tool_name": "Search",
                    "sub_goal": "find evidence",
                    "command": "search",
                    "result": {"items": ["raw observation"]},
                },
                "Action Step 2": {
                    "tool_name": "Search",
                    "sub_goal": "retry source",
                    "command": "search again",
                    "result": "Error: service unavailable",
                },
            },
            "step_count": 2,
            "execution_time": 1.0,
            "conclusion": "CONTINUE",
        },
        {
            "memory": {},
            "step_count": 1,
            "execution_time": 0.5,
            "conclusion": "STOP",
            "direct_output": "answer",
        },
    ]

    def factory(attempt_index, remaining_steps):
        assert remaining_steps > 0
        return FakeSolver(results[attempt_index - 1], contexts)

    output = MultiAttemptController(
        factory,
        budget=AttemptBudget(max_attempts=2, max_total_steps=5),
    ).solve("question")

    second_context = contexts[1]
    assert second_context["observations"][0]["result"] == {
        "items": ["raw observation"]
    }
    assert second_context["failures_to_avoid"][0]["result"].startswith("Error")
    assert output["selected_attempt"] == 2
    assert output["selected_answer"] == "answer"


def test_controller_stops_when_global_step_budget_is_exhausted():
    contexts = []
    calls = []

    def factory(attempt_index, remaining_steps):
        calls.append((attempt_index, remaining_steps))
        return FakeSolver(
            {
                "memory": {},
                "step_count": 2,
                "execution_time": 0.1,
                "conclusion": "CONTINUE",
            },
            contexts,
        )

    output = MultiAttemptController(
        factory,
        budget=AttemptBudget(max_attempts=5, max_total_steps=2),
    ).solve("question")

    assert calls == [(1, 2)]
    assert output["budget"]["attempts_used"] == 1
    assert output["budget"]["steps_used"] == 2


def test_fixed_attempts_can_select_last_successful_answer():
    contexts = []
    answers = ["candidate one", "candidate two"]

    def factory(attempt_index, remaining_steps):
        return FakeSolver(
            {
                "memory": {},
                "step_count": 1,
                "execution_time": 0.1,
                "conclusion": "STOP",
                "direct_output": answers[attempt_index - 1],
            },
            contexts,
        )

    output = MultiAttemptController(
        factory,
        budget=AttemptBudget(max_attempts=2, max_total_steps=4),
        stop_on_success=False,
        selection_strategy="last_successful",
    ).solve("question")

    assert len(output["attempts"]) == 2
    assert output["selected_attempt"] == 2
    assert output["selected_answer"] == "candidate two"


def test_controller_does_not_share_evidence_between_queries():
    contexts = []

    def factory(attempt_index, remaining_steps):
        return FakeSolver(
            {
                "memory": {
                    "Action Step 1": {
                        "tool_name": "Search",
                        "sub_goal": "find evidence",
                        "command": "search",
                        "result": f"observation {len(contexts) + 1}",
                    }
                },
                "step_count": 1,
                "execution_time": 0.1,
                "conclusion": "STOP",
                "direct_output": "answer",
            },
            contexts,
        )

    controller = MultiAttemptController(
        factory,
        budget=AttemptBudget(max_attempts=1, max_total_steps=1),
    )
    controller.solve("first question")
    controller.solve("second question")

    assert contexts[0]["observations"] == []
    assert contexts[1]["observations"] == []


def test_sharing_policy_supports_no_memory_ablation():
    contexts = []
    results = [
        {
            "memory": {
                "Action Step 1": {
                    "tool_name": "Search",
                    "sub_goal": "find evidence",
                    "command": "search",
                    "result": "observation",
                }
            },
            "step_count": 1,
            "conclusion": "CONTINUE",
        },
        {
            "memory": {},
            "step_count": 1,
            "conclusion": "STOP",
            "direct_output": "answer",
        },
    ]

    def factory(attempt_index, remaining_steps):
        return FakeSolver(results[attempt_index - 1], contexts)

    policy = MemorySharingPolicy(
        share_observations=False,
        share_failures=False,
        share_attempt_summaries=False,
    )
    output = MultiAttemptController(
        factory,
        budget=AttemptBudget(max_attempts=2, max_total_steps=2),
        sharing_policy=policy,
    ).solve("question")

    assert contexts[1]["observations"] == []
    assert contexts[1]["failures_to_avoid"] == []
    assert contexts[1]["prior_attempts"] == []
    assert output["sharing_policy"]["share_observations"] is False
