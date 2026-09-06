from __future__ import annotations

import json
import time
from copy import deepcopy
from dataclasses import asdict, dataclass, field
from typing import Any, Callable, Mapping, Protocol


class SolverProtocol(Protocol):
    def solve(
        self,
        question: str,
        image_path: str | None = None,
        shared_context: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]: ...


SolverFactory = Callable[[int, int], SolverProtocol]


@dataclass(frozen=True)
class AttemptBudget:
    """Global test-time budget shared by all attempts for one query."""

    max_attempts: int = 3
    max_total_steps: int = 30
    max_total_seconds: float = 900.0

    def __post_init__(self) -> None:
        if self.max_attempts < 1:
            raise ValueError("max_attempts must be at least 1")
        if self.max_total_steps < 1:
            raise ValueError("max_total_steps must be at least 1")
        if self.max_total_seconds <= 0:
            raise ValueError("max_total_seconds must be positive")


@dataclass(frozen=True)
class MemorySharingPolicy:
    """Ablation switches for information transferred between attempts."""

    share_observations: bool = True
    share_failures: bool = True
    share_attempt_summaries: bool = True


def _contains_error(value: Any) -> bool:
    if isinstance(value, str):
        lowered = value.strip().lower()
        return lowered.startswith("error") or "traceback" in lowered
    if isinstance(value, Mapping):
        if any(
            str(key).lower() in {"error", "exception"}
            and item not in (None, False, "")
            for key, item in value.items()
        ):
            return True
        return any(_contains_error(item) for item in value.values())
    if isinstance(value, (list, tuple)):
        return any(_contains_error(item) for item in value)
    return False


def _bounded(value: Any, max_chars: int) -> Any:
    try:
        serialized = json.dumps(value, ensure_ascii=False, default=str)
    except (TypeError, ValueError):
        serialized = str(value)
    if len(serialized) <= max_chars:
        return deepcopy(value)
    return serialized[:max_chars] + "...<truncated>"


@dataclass
class SharedEvidenceMemory:
    """Cross-attempt memory that preserves observations, not inferred facts."""

    max_observations: int = 24
    max_failures: int = 12
    max_result_chars: int = 2000
    observations: list[dict[str, Any]] = field(default_factory=list)
    failures: list[dict[str, Any]] = field(default_factory=list)
    attempt_summaries: list[dict[str, Any]] = field(default_factory=list)

    def clear(self) -> None:
        """Discard evidence before the controller starts a different query."""
        self.observations.clear()
        self.failures.clear()
        self.attempt_summaries.clear()

    def ingest_attempt(
        self,
        attempt_index: int,
        result: Mapping[str, Any],
        *,
        success: bool,
        answer: Any,
    ) -> None:
        actions = result.get("memory", {})
        if isinstance(actions, Mapping):
            for step_name, action in actions.items():
                if not isinstance(action, Mapping):
                    continue
                evidence = {
                    "evidence_id": f"attempt-{attempt_index}:{step_name}",
                    "attempt": attempt_index,
                    "step": str(step_name),
                    "tool_name": action.get("tool_name"),
                    "sub_goal": action.get("sub_goal"),
                    "command": action.get("command"),
                    "result": _bounded(
                        action.get("result"),
                        self.max_result_chars,
                    ),
                }
                if _contains_error(action.get("result")):
                    self.failures.append(evidence)
                else:
                    self.observations.append(evidence)

        self.observations = self.observations[-self.max_observations :]
        self.failures = self.failures[-self.max_failures :]
        self.attempt_summaries.append(
            {
                "attempt": attempt_index,
                "success": success,
                "conclusion": result.get("conclusion"),
                "step_count": int(result.get("step_count", 0) or 0),
                "answer": _bounded(answer, self.max_result_chars),
            }
        )

    def as_prompt_context(
        self,
        policy: MemorySharingPolicy | None = None,
    ) -> dict[str, Any]:
        active_policy = policy or MemorySharingPolicy()
        return {
            "evidence_policy": (
                "Tool results are observations, not verified conclusions. "
                "Revalidate observations when they conflict or are stale."
            ),
            "observations": (
                deepcopy(self.observations)
                if active_policy.share_observations
                else []
            ),
            "failures_to_avoid": (
                deepcopy(self.failures)
                if active_policy.share_failures
                else []
            ),
            "prior_attempts": (
                deepcopy(self.attempt_summaries)
                if active_policy.share_attempt_summaries
                else []
            ),
        }


def _extract_answer(result: Mapping[str, Any]) -> Any:
    for key in ("direct_output", "final_output", "base_response"):
        value = result.get(key)
        if value not in (None, ""):
            return value
    return None


def _attempt_succeeded(result: Mapping[str, Any], answer: Any) -> bool:
    if answer is None:
        return False
    conclusion = result.get("conclusion")
    if conclusion not in (None, "STOP"):
        return False
    return not _contains_error(result.get("memory", {}))


class MultiAttemptController:
    """Run independent solver attempts under one budget and shared memory."""

    def __init__(
        self,
        solver_factory: SolverFactory,
        *,
        budget: AttemptBudget | None = None,
        stop_on_success: bool = True,
        selection_strategy: str = "last_successful",
        shared_memory: SharedEvidenceMemory | None = None,
        sharing_policy: MemorySharingPolicy | None = None,
    ) -> None:
        if selection_strategy not in {"first_successful", "last_successful"}:
            raise ValueError(
                "selection_strategy must be 'first_successful' or "
                "'last_successful'"
            )
        self.solver_factory = solver_factory
        self.budget = budget or AttemptBudget()
        self.stop_on_success = stop_on_success
        self.selection_strategy = selection_strategy
        self.shared_memory = shared_memory or SharedEvidenceMemory()
        self.sharing_policy = sharing_policy or MemorySharingPolicy()

    def solve(
        self,
        question: str,
        image_path: str | None = None,
    ) -> dict[str, Any]:
        # Evidence may be reused only by attempts for the same query.
        self.shared_memory.clear()
        started_at = time.monotonic()
        attempts: list[dict[str, Any]] = []
        total_steps = 0

        while len(attempts) < self.budget.max_attempts:
            elapsed = time.monotonic() - started_at
            remaining_steps = self.budget.max_total_steps - total_steps
            if remaining_steps <= 0 or elapsed >= self.budget.max_total_seconds:
                break

            attempt_index = len(attempts) + 1
            solver = self.solver_factory(attempt_index, remaining_steps)
            result = solver.solve(
                question,
                image_path,
                shared_context=self.shared_memory.as_prompt_context(
                    self.sharing_policy
                ),
            )
            answer = _extract_answer(result)
            success = _attempt_succeeded(result, answer)
            step_count = int(result.get("step_count", 0) or 0)
            total_steps += max(0, step_count)

            record = {
                "attempt": attempt_index,
                "success": success,
                "answer": answer,
                "step_count": step_count,
                "execution_time": float(
                    result.get("execution_time", 0.0) or 0.0
                ),
                "result": deepcopy(result),
            }
            attempts.append(record)
            self.shared_memory.ingest_attempt(
                attempt_index,
                result,
                success=success,
                answer=answer,
            )

            if success and self.stop_on_success:
                break

        successful = [item for item in attempts if item["success"]]
        selected = None
        if successful:
            selected = (
                successful[0]
                if self.selection_strategy == "first_successful"
                else successful[-1]
            )

        elapsed = time.monotonic() - started_at
        return {
            "query": question,
            "image": image_path,
            "attempts": attempts,
            "selected_attempt": selected["attempt"] if selected else None,
            "selected_answer": selected["answer"] if selected else None,
            "budget": {
                **asdict(self.budget),
                "attempts_used": len(attempts),
                "steps_used": total_steps,
                "wall_time_seconds": round(elapsed, 6),
            },
            "sharing_policy": asdict(self.sharing_policy),
            "shared_memory": self.shared_memory.as_prompt_context(
                self.sharing_policy
            ),
        }
