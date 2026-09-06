from apc.models import PlanTemplate, TemplateStep

from octotools.research.evidence_plan import (
    EvidencePlanGate,
    PlanStepAction,
    build_plan_guidance,
)


def make_template(tool_name="Search", description="Find company revenue"):
    return PlanTemplate(
        source_query="Find Acme revenue",
        category="financial lookup",
        steps=[
            TemplateStep(
                index=1,
                description=description,
                tool_name=tool_name,
                parameter_hints={"query": "company and year"},
            )
        ],
    )


def test_reuse_when_no_evidence_satisfies_step():
    assessment = EvidencePlanGate(["Search"]).assess(make_template(), {})

    assert assessment.usable is True
    assert assessment.decisions[0].action is PlanStepAction.REUSE


def test_skip_when_trusted_matching_evidence_exists():
    context = {
        "observations": [
            {
                "evidence_id": "attempt-1:step-1",
                "tool_name": "Search",
                "sub_goal": "Find company revenue",
                "result": {"revenue": 42},
            }
        ]
    }

    assessment = EvidencePlanGate(["Search"]).assess(
        make_template(),
        context,
    )

    assert assessment.decisions[0].action is PlanStepAction.SKIP
    assert assessment.decisions[0].evidence_ids == ("attempt-1:step-1",)


def test_reverify_when_matching_observations_conflict():
    context = {
        "observations": [
            {
                "evidence_id": "e1",
                "tool_name": "Search",
                "sub_goal": "Find company revenue",
                "result": 41,
            },
            {
                "evidence_id": "e2",
                "tool_name": "Search",
                "sub_goal": "Find company revenue",
                "result": 42,
            },
        ]
    }

    assessment = EvidencePlanGate(["Search"]).assess(
        make_template(),
        context,
    )

    assert assessment.decisions[0].action is PlanStepAction.REVERIFY


def test_reverify_after_matching_failure():
    context = {
        "failures_to_avoid": [
            {
                "evidence_id": "failure-1",
                "tool_name": "Search",
                "sub_goal": "Find company revenue",
                "result": "Error: unavailable",
            }
        ]
    }

    assessment = EvidencePlanGate(["Search"]).assess(
        make_template(),
        context,
    )

    assert assessment.decisions[0].action is PlanStepAction.REVERIFY


def test_replan_when_cached_tool_is_unavailable():
    assessment = EvidencePlanGate(["Calculator"]).assess(
        make_template(tool_name="Search"),
        {},
    )

    assert assessment.usable is False
    assert assessment.decisions[0].action is PlanStepAction.REPLAN


def test_guidance_preserves_template_and_decision_provenance():
    template = make_template()
    assessment = EvidencePlanGate(["Search"]).assess(template, {})

    guidance = build_plan_guidance(template, assessment)

    assert guidance["source_query"] == "Find Acme revenue"
    assert guidance["steps"][0]["action"] == "REUSE"
    assert guidance["steps"][0]["parameter_hints"] == {
        "query": "company and year"
    }


def test_chinese_subgoals_support_partial_semantic_overlap():
    template = make_template(description="查询公司年度收入")
    context = {
        "observations": [
            {
                "evidence_id": "e-cn",
                "tool_name": "Search",
                "sub_goal": "查询公司收入数据",
                "result": {"收入": 42},
            }
        ]
    }

    assessment = EvidencePlanGate(["Search"]).assess(template, context)

    assert assessment.decisions[0].action is PlanStepAction.SKIP
