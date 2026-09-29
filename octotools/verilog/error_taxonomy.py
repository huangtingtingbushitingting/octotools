"""Multi-label RTL error taxonomy and expert routing.

The classifier is deliberately deterministic: EDA logs provide the evidence,
and low-confidence cases can be sent to the general expert or a human.
"""

from __future__ import annotations

import json
import re
from collections import Counter
from typing import Any, Iterable

STRUCTURAL = "structural"
TEMPORAL_FSM = "temporal_fsm"
NUMERIC_VECTOR = "numeric_vector"
GENERAL_COMPLEX = "general_complex"
FAMILIES = (STRUCTURAL, TEMPORAL_FSM, NUMERIC_VECTOR, GENERAL_COMPLEX)

_PATTERNS = {
    STRUCTURAL: (
        r"wire.*(?:l-value|assigned|driven)", r"not found", r"already declared",
        r"port.*(?:does not exist|mismatch)", r"out of bounds", r"syntax error",
        r"generate", r"endmodule", r"unable to bind",
    ),
    TEMPORAL_FSM: (
        r"posedge|negedge|clock|reset|state|fsm|mismatch.*time",
        r"first mismatch occurred at time", r"cycle|latency|handshake",
    ),
    NUMERIC_VECTOR: (
        r"width|bits|part select|signed|unsigned|overflow|truncat",
        r"carry|slice|lsb|msb|casez|casex|shift",
    ),
}


def _text(checks: dict[str, Any], code: str) -> str:
    return (json.dumps(checks, ensure_ascii=False, default=str) + "\n" + code).lower()


def extract_failure_evidence(checks: dict[str, Any]) -> dict[str, Any]:
    """Extract line numbers, first failing cycle and compact waveform summary."""
    text = json.dumps(checks, ensure_ascii=False, default=str)
    line_numbers = sorted({int(value) for value in re.findall(r":(\d+):", text)})
    time_values = [int(value) for value in re.findall(r"(?:time|at)\s+(\d+)", text, re.I)]
    mismatches = [int(value) for value in re.findall(r"(\d+)\s+mismatch", text, re.I)]
    return {
        "error_line_numbers": line_numbers[:20],
        "first_failure_cycle": min(time_values) if time_values else None,
        "waveform_summary": {
            "reported_mismatch_counts": mismatches[:20],
            "simulation_output_tail": str(
                (checks.get("simulation") or {}).get("stdout")
                or (checks.get("simulation") or {}).get("output")
                or ""
            )[-2000:],
        },
    }


def classify_error(
    checks: dict[str, Any], code: str = "", *, threshold: float = 0.20
) -> dict[str, Any]:
    """Return primary label, multi-label scores, top-2 and reject decision."""
    text = _text(checks, code)
    scores = Counter()
    for family, patterns in _PATTERNS.items():
        scores[family] = sum(bool(re.search(pattern, text)) for pattern in patterns)
    if checks.get("generation") or not code.strip():
        scores[STRUCTURAL] += 2
    if checks.get("compile", {}).get("compile_success") is False:
        scores[STRUCTURAL] += 2
    if checks.get("simulation", {}).get("simulation_success") is False:
        scores[TEMPORAL_FSM] += 2
    if checks.get("synthesis", {}).get("synthesis_success") is False:
        scores[STRUCTURAL] += 1
    if checks.get("equivalence", {}).get("equivalence_success") is False:
        scores[GENERAL_COMPLEX] += 2

    total = sum(scores.values()) or 1
    probabilities = {family: round(scores[family] / total, 6) for family in FAMILIES}
    ranked = sorted(FAMILIES, key=lambda family: (-scores[family], FAMILIES.index(family)))
    primary = ranked[0] if scores[ranked[0]] else GENERAL_COMPLEX
    confidence = probabilities.get(primary, 0.0)
    labels = [family for family in ranked if scores[family] > 0]
    return {
        "primary": primary,
        "labels": labels or [GENERAL_COMPLEX],
        "scores": dict(scores),
        "probabilities": probabilities,
        "top2": ranked[:2],
        "confidence": confidence,
        "reject": confidence < threshold,
        "evidence": extract_failure_evidence(checks),
    }


def ordered_categories(labels: Iterable[str]) -> list[str]:
    """Repair structure first, then sequential logic/numeric, then fallback."""
    values = set(labels)
    return [family for family in FAMILIES if family in values]


def classification_metrics(rows: Iterable[dict[str, Any]]) -> dict[str, Any]:
    """Compute accuracy, macro-F1, top-2 recall and low-confidence rejection."""
    rows = list(rows)
    if not rows:
        return {"count": 0, "accuracy": 0.0, "macro_f1": 0.0, "top2_recall": 0.0, "reject_rate": 0.0}
    correct = 0
    top2 = 0
    rejected = 0
    truth = Counter()
    predicted = Counter()
    true_positive = Counter()
    for row in rows:
        expected = row.get("label") or row.get("error_category")
        result = row.get("prediction") or row
        actual = result.get("primary") or result.get("predicted")
        candidates = result.get("top2") or [actual]
        truth[expected] += 1
        predicted[actual] += 1
        correct += actual == expected
        top2 += expected in candidates
        rejected += bool(result.get("reject"))
        true_positive[expected] += actual == expected
    f1_values = []
    for family in FAMILIES:
        precision = true_positive[family] / predicted[family] if predicted[family] else 0.0
        recall = true_positive[family] / truth[family] if truth[family] else 0.0
        f1_values.append(2 * precision * recall / (precision + recall) if precision + recall else 0.0)
    n = len(rows)
    return {
        "count": n,
        "accuracy": correct / n,
        "macro_f1": sum(f1_values) / len(FAMILIES),
        "top2_recall": top2 / n,
        "reject_rate": rejected / n,
    }
