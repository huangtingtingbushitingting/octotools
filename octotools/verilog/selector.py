"""Final candidate selector using EDA score and minimal-change preferences."""

from __future__ import annotations

from typing import Any


def _edit_distance(left: str, right: str) -> int:
    previous = list(range(len(right) + 1))
    for i, char in enumerate(left, 1):
        current = [i]
        for j, other in enumerate(right, 1):
            current.append(min(current[-1] + 1, previous[j] + 1, previous[j - 1] + (char != other)))
        previous = current
    return previous[-1]


def select_best_candidate(candidates: list[dict[str, Any]], original_code: str = "") -> dict[str, Any]:
    """Select highest EDA score, then fewer warnings/complexity and smaller edit."""
    if not candidates:
        raise ValueError("at least one candidate is required")

    def key(item: dict[str, Any]):
        checks = item.get("verification") or {}
        text = str(checks)
        warnings = text.lower().count("warning")
        complexity = str(item.get("code") or "").count("always") + str(item.get("code") or "").count("case")
        edit = _edit_distance(original_code, str(item.get("code") or "")) if original_code else 0
        return (-float(item.get("score", -2.0)), warnings, complexity, edit, str(item.get("candidate_id", "")))

    return min(candidates, key=key)
