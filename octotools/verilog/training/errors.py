"""Deterministic error routing from EDA evidence to repair experts.错误分类器"""

from __future__ import annotations

import json
import re
from typing import Any

from octotools.verilog.error_taxonomy import classify_error


WIRE_LVALUE_PATTERNS = (
    r"not a valid l-value",
    r"declared here as wire",
    r"wire/reg/memory.*cannot be driven",
    r"net .* cannot be assigned",
)


def _evidence_text(value: Any) -> str:
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False, default=str)


def _wire_assigned_in_always(code: str) -> bool:
    wire_names: set[str] = set()
    for declaration in re.findall(
        r"\b(?:wire|output\s+wire)\b(?:\s*\[[^]]+\])?\s+([^;]+);",
        code,
        flags=re.IGNORECASE,
    ):
        for item in declaration.split(","):
            match = re.search(r"([A-Za-z_][A-Za-z0-9_$]*)\s*$", item.strip())
            if match:
                wire_names.add(match.group(1))
    always_blocks = re.findall(
        r"\balways\b.*?(?=\balways\b|\bendmodule\b)",
        code,
        flags=re.IGNORECASE | re.DOTALL,
    )
    return any(
        re.search(rf"\b{re.escape(name)}\b\s*(?:<=|=)", block)
        for name in wire_names
        for block in always_blocks
    )


def classify_failure(checks: dict[str, Any], code: str = "") -> str:
    """Return one conservative category used to route the next repair."""
    text = _evidence_text(checks).lower()
    compile_result = checks.get("compile", checks)
    simulation = checks.get("simulation", checks)
    synthesis = checks.get("synthesis", checks)
    equivalence = checks.get("equivalence", checks)

    if not code.strip():
        return "generation_or_extraction_error"
    if any(re.search(pattern, text) for pattern in WIRE_LVALUE_PATTERNS):
        return "wire_in_always_block"
    if _wire_assigned_in_always(code):
        return "wire_in_always_block"
    if compile_result.get("compile_success") is False:
        return "compile_error"
    if simulation.get("simulation_success") is False:
        return "simulation_functional_error"
    if synthesis.get("synthesis_success") is False:
        return "synthesis_error"
    if equivalence.get("equivalence_success") is False:
        return "equivalence_error"
    return "unclassified"


def classify_failure_details(checks: dict[str, Any], code: str = "") -> dict[str, Any]:
    """Return the legacy leaf label plus the four-family multi-label route."""
    leaf = classify_failure(checks, code)
    details = classify_error(checks, code)
    details["leaf_category"] = leaf
    if leaf == "wire_in_always_block":
        details["primary"] = "structural"
        details["labels"] = list(dict.fromkeys(["structural", *details.get("labels", [])]))
        details["top2"] = list(dict.fromkeys(["structural", *details.get("top2", [])]))[:2]
    return details
