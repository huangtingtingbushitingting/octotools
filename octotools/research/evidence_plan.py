from __future__ import annotations

import json
import re
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import asdict, dataclass
from enum import Enum
from typing import Any

from apc.models import PlanTemplate, TemplateStep


class PlanStepAction(str, Enum):
    """Permitted actions for a cached plan step."""

    REUSE = "REUSE"
    SKIP = "SKIP"
    REVERIFY = "REVERIFY"
    REPLAN = "REPLAN"


@dataclass(frozen=True)
class PlanStepDecision:
    step_index: int
    tool_name: str
    action: PlanStepAction
    reason: str
    evidence_ids: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["action"] = self.action.value
        data["evidence_ids"] = list(self.evidence_ids)
        return data


@dataclass(frozen=True)
class PlanReuseAssessment:
    usable: bool
    decisions: tuple[PlanStepDecision, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "usable": self.usable,
            "decisions": [decision.to_dict() for decision in self.decisions],
        }


def _normalize_tool_name(tool_name: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(tool_name).casefold())


def _tokens(value: Any) -> set[str]:
    text = str(value).casefold()
    tokens = {
        token
        for token in re.findall(r"[a-z0-9_]+", text)
        if len(token) > 1
    }
    for chunk in re.findall(r"[\u3400-\u4dbf\u4e00-\u9fff]+", text):
        if len(chunk) == 1:
            tokens.add(chunk)
        else:
            tokens.update(
                chunk[index : index + 2]
                for index in range(len(chunk) - 1)
            )
    return tokens


def _result_fingerprint(value: Any) -> str:
    try:
        return json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            default=str,
        )
    except (TypeError, ValueError):
        return str(value)


class EvidencePlanGate:
    """Conservatively reconcile cached plan steps with prior evidence."""

    def __init__(
        self,
        available_tools: Iterable[str],
        *,
        minimum_overlap: float = 0.25,
    ) -> None:
        if not 0 <= minimum_overlap <= 1:
            raise ValueError("minimum_overlap must be between 0 and 1")
        self.available_tools = {
            _normalize_tool_name(tool) for tool in available_tools
        }
        self.minimum_overlap = minimum_overlap

    def assess(
        self,
        template: PlanTemplate,
        evidence_context: Mapping[str, Any] | None,
    ) -> PlanReuseAssessment:
        context = evidence_context or {}
        observations = self._records(context.get("observations"))
        failures = self._records(context.get("failures_to_avoid"))
        decisions = tuple(
            self._assess_step(step, observations, failures)
            for step in template.steps
        )
        return PlanReuseAssessment(
            usable=not any(
                decision.action is PlanStepAction.REPLAN
                for decision in decisions
            ),
            decisions=decisions,
        )

    @staticmethod
    def _records(value: Any) -> list[Mapping[str, Any]]:
        if not isinstance(value, Sequence) or isinstance(
            value,
            (str, bytes, bytearray),
        ):
            return []
        return [item for item in value if isinstance(item, Mapping)]

    def _matches(
        self,
        step: TemplateStep,
        record: Mapping[str, Any],
    ) -> bool:
        if _normalize_tool_name(record.get("tool_name")) != _normalize_tool_name(
            step.tool_name
        ):
            return False

        step_tokens = _tokens(step.description)
        evidence_tokens = _tokens(record.get("sub_goal", ""))
        if not step_tokens or not evidence_tokens:
            return True

        overlap = len(step_tokens & evidence_tokens) / len(step_tokens)
        return overlap >= self.minimum_overlap

    @staticmethod
    def _evidence_ids(records: Sequence[Mapping[str, Any]]) -> tuple[str, ...]:
        return tuple(
            str(record.get("evidence_id") or "unknown") for record in records
        )

    def _assess_step(
        self,
        step: TemplateStep,
        observations: Sequence[Mapping[str, Any]],
        failures: Sequence[Mapping[str, Any]],
    ) -> PlanStepDecision:
        if _normalize_tool_name(step.tool_name) not in self.available_tools:
            return PlanStepDecision(
                step_index=step.index,
                tool_name=step.tool_name,
                action=PlanStepAction.REPLAN,
                reason="The cached step requires an unavailable tool.",
            )

        matching_observations = [
            record for record in observations if self._matches(step, record)
        ]
        matching_failures = [
            record for record in failures if self._matches(step, record)
        ]

        if matching_failures:
            return PlanStepDecision(
                step_index=step.index,
                tool_name=step.tool_name,
                action=PlanStepAction.REVERIFY,
                reason=(
                    "A matching tool operation failed in an earlier attempt; "
                    "do not replay it without verification."
                ),
                evidence_ids=self._evidence_ids(matching_failures),
            )

        if not matching_observations:
            return PlanStepDecision(
                step_index=step.index,
                tool_name=step.tool_name,
                action=PlanStepAction.REUSE,
                reason="No prior evidence satisfies this cached step.",
            )

        if any(
            record.get("stale") is True or record.get("trusted") is False
            for record in matching_observations
        ):
            return PlanStepDecision(
                step_index=step.index,
                tool_name=step.tool_name,
                action=PlanStepAction.REVERIFY,
                reason="Matching evidence is stale or not trusted.",
                evidence_ids=self._evidence_ids(matching_observations),
            )

        fingerprints = {
            _result_fingerprint(record.get("result"))
            for record in matching_observations
        }
        if len(fingerprints) > 1:
            return PlanStepDecision(
                step_index=step.index,
                tool_name=step.tool_name,
                action=PlanStepAction.REVERIFY,
                reason="Matching observations conflict and must be checked again.",
                evidence_ids=self._evidence_ids(matching_observations),
            )

        return PlanStepDecision(
            step_index=step.index,
            tool_name=step.tool_name,
            action=PlanStepAction.SKIP,
            reason="Trusted matching evidence already satisfies this step.",
            evidence_ids=self._evidence_ids(matching_observations),
        )


def build_plan_guidance(
    template: PlanTemplate,
    assessment: PlanReuseAssessment,
) -> dict[str, Any]:
    """Build explicit planner guidance without executing cached commands."""
    decisions_by_index = {
        decision.step_index: decision for decision in assessment.decisions
    }
    steps = []
    for step in template.steps:
        decision = decisions_by_index[step.index]
        steps.append(
            {
                "index": step.index,
                "description": step.description,
                "tool_name": step.tool_name,
                "parameter_hints": dict(step.parameter_hints),
                **decision.to_dict(),
            }
        )

    return {
        "policy": (
            "This cached plan is advisory. Follow each step decision: REUSE "
            "means execute/adapt it, SKIP means use cited evidence, REVERIFY "
            "means collect fresh evidence, and REPLAN means abandon the "
            "cached template."
        ),
        "source_query": template.source_query,
        "category": template.category,
        "usable": assessment.usable,
        "steps": steps,
    }
