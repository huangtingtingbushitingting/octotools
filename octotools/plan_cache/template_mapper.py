from __future__ import annotations

import json
import re
from collections.abc import Mapping, Sequence
from typing import Any

from apc.models import Plan, PlanStep


_ERROR_PREFIXES = (
    "error",
    "execution timed out",
    "no result",
    "no execution captured",
)


def _serialize_result(result: Any) -> str:
    """Convert arbitrary OctoTools results into text APC can persist."""
    if isinstance(result, str):
        return result

    try:
        return json.dumps(result, ensure_ascii=False, default=str)
    except (TypeError, ValueError):
        return str(result)


def _contains_error(result: Any) -> bool:
    """Detect errors inside strings, lists, and dictionaries."""
    if result is None:
        return True

    if isinstance(result, str):
        normalized = result.strip().lower()
        return any(normalized.startswith(prefix) for prefix in _ERROR_PREFIXES)

    if isinstance(result, Mapping):
        for key, value in result.items():
            normalized_key = str(key).strip().lower()
            if normalized_key in {"error", "exception"} and value not in {
                None,
                False,
                "",
            }:
                return True

            if _contains_error(value):
                return True

        return False

    if isinstance(result, Sequence) and not isinstance(
        result,
        (str, bytes, bytearray),
    ):
        return any(_contains_error(item) for item in result)

    return False


def _extract_step_index(step_name: str, fallback: int) -> int:
    """Read the numeric suffix from names such as 'Action Step 2'."""
    match = re.search(r"(\d+)$", step_name)
    return int(match.group(1)) if match else fallback


def memory_actions_to_plan(
    query: str,
    actions: Mapping[str, Mapping[str, Any]],
) -> Plan:
    """Convert OctoTools Memory actions into an APC concrete Plan."""
    steps: list[PlanStep] = []

    for fallback_index, (step_name, action) in enumerate(
        actions.items(),
        start=1,
    ):
        tool_name = str(action.get("tool_name") or "")
        sub_goal = str(action.get("sub_goal") or step_name)
        command = str(action.get("command") or "")
        raw_result = action.get("result")
        serialized_result = _serialize_result(raw_result)

        failed = (
            not tool_name
            or not command
            or _contains_error(raw_result)
        )

        steps.append(
            PlanStep(
                index=_extract_step_index(step_name, fallback_index),
                description=sub_goal,
                tool_name=tool_name,
                tool_args={"command": command},
                status="failed" if failed else "completed",
                result=serialized_result,
            )
        )

    return Plan(
        query=query,
        steps=steps,
        source="planner",
    )