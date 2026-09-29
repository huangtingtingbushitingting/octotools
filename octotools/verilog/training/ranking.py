"""EDA-grounded candidate scoring and deterministic ranking.候选者排序器"""

from __future__ import annotations

from typing import Any


def _simulation_credit(result: dict[str, Any]) -> float:
    if result.get("simulation_success") is True:#判断仿真是否通过
        return 1.0
    failures = result.get("reported_failure_counts") or []
    if failures and all(isinstance(value, int) for value in failures):
        return 0.0
    return 0.0


def score_candidate(
    candidate: dict[str, Any], *, has_testbench: bool, has_reference: bool
) -> float:
    code = str(candidate.get("code") or candidate.get("extracted_code") or "")
    if not code.strip():
        return -2.0
    checks = candidate.get("verification") or {}
    compile_result = checks.get("compile", checks)
    if compile_result.get("compile_success") is not True:#判断编译是否通过
        return -1.0

    credits = [1.0]
    synthesis = checks.get("synthesis", {})
    credits.append(1.0 if synthesis.get("synthesis_success") is True else 0.0)#判断综合检测是否通过
    if has_testbench:
        credits.append(_simulation_credit(checks.get("simulation", {})))
    if has_reference:
        equivalence = checks.get("equivalence", {})
        credits.append(1.0 if equivalence.get("equivalence_success") is True else 0.0)#判断等价性是否通过
    return round(sum(credits) / len(credits), 6)


def rank_candidates(#进行候选者排序
    candidates: list[dict[str, Any]], *, has_testbench: bool, has_reference: bool
) -> list[dict[str, Any]]:
    for candidate in candidates:
        candidate["score"] = score_candidate(
            candidate,
            has_testbench=has_testbench,
            has_reference=has_reference,
        )
    ranked = sorted(
        candidates,
        key=lambda item: (
            -float(item["score"]),
            len(str(item.get("code") or "")),#同时考虑代码长度
            str(item.get("candidate_id") or ""),
        ),
    )
    for position, candidate in enumerate(ranked, start=1):
        candidate["rank"] = position
        candidate["selected"] = position == 1
    return ranked
