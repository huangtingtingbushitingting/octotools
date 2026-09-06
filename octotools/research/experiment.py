from __future__ import annotations

import argparse
import json
import os
import platform
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Sequence

from octotools.research.multi_attempt import (
    AttemptBudget,
    MemorySharingPolicy,
    MultiAttemptController,
)
from octotools.research.usage import collect_usage


@dataclass(frozen=True)
class ExperimentGroup:
    name: str
    max_attempts: int
    sharing_policy: MemorySharingPolicy
    enable_plan_cache: bool
    plan_cache_mode: str = "off"
    plan_cache_use_evidence: bool = False


EXPERIMENT_GROUPS: dict[str, ExperimentGroup] = {
    "B0": ExperimentGroup(
        "B0", 1, MemorySharingPolicy(False, False, False), False
    ),
    "B1": ExperimentGroup(
        "B1", 3, MemorySharingPolicy(False, False, False), False
    ),
    "M1": ExperimentGroup(
        "M1", 3, MemorySharingPolicy(True, False, False), False
    ),
    "M2": ExperimentGroup(
        "M2", 3, MemorySharingPolicy(True, True, True), False
    ),
    "P0": ExperimentGroup(
        "P0",
        3,
        MemorySharingPolicy(True, False, False),
        True,
        "assist",
        False,
    ),
    "P1": ExperimentGroup(
        "P1",
        3,
        MemorySharingPolicy(True, False, False),
        True,
        "assist",
        True,
    ),
    "C1": ExperimentGroup(
        "C1",
        3,
        MemorySharingPolicy(True, True, True),
        True,
        "assist",
        True,
    ),
}


def get_experiment_group(name: str) -> ExperimentGroup:
    normalized = name.upper()
    try:
        return EXPERIMENT_GROUPS[normalized]
    except KeyError as error:
        raise ValueError(
            f"Unknown experiment group {name!r}; choose from "
            f"{sorted(EXPERIMENT_GROUPS)}"
        ) from error


def _normalize_answer(value: Any) -> str:
    return " ".join(str(value or "").strip().lower().split())


def summarize_result(result: dict[str, Any]) -> dict[str, Any]:
    attempts = result.get("attempts", [])
    cache_records = [
        attempt.get("result", {}).get("plan_cache")
        for attempt in attempts
        if isinstance(attempt, dict)
    ]
    cache_records = [item for item in cache_records if isinstance(item, dict)]
    return {
        "success": result.get("selected_attempt") is not None,
        "attempts_used": len(attempts),
        "tool_steps": sum(
            int(attempt.get("step_count", 0) or 0)
            for attempt in attempts
            if isinstance(attempt, dict)
        ),
        "wall_time_seconds": result.get("budget", {}).get(
            "wall_time_seconds", 0.0
        ),
        "plan_cache_lookups": len(cache_records),
        "plan_cache_hits": sum(bool(item.get("hit")) for item in cache_records),
        "plan_cache_errors": sum(bool(item.get("error")) for item in cache_records),
    }


def run_experiment(args: argparse.Namespace) -> dict[str, Any]:
    # Imported lazily so group/config tests do not import optional image tools.
    from octotools.solver import construct_solver

    group = get_experiment_group(args.group)
    max_attempts = args.attempts or group.max_attempts
    if group.name == "B0":
        max_attempts = 1

    def solver_factory(attempt_index: int, remaining_steps: int):
        del attempt_index
        return construct_solver(
            llm_engine_name=args.model,
            enabled_tools=args.tools,
            output_types=args.output_types,
            max_steps=min(args.steps_per_attempt, remaining_steps),
            max_time=args.seconds_per_attempt,
            max_tokens=args.max_tokens,
            root_cache_dir=args.solver_cache_dir,
            verbose=args.verbose,
            enable_plan_cache=group.enable_plan_cache,
            plan_cache_mode=group.plan_cache_mode,
            cheap_llm_engine_name=args.cache_model,
            plan_cache_path=args.plan_cache_path,
            plan_cache_max_size=args.plan_cache_max_size,
            plan_cache_use_evidence=group.plan_cache_use_evidence,
        )

    controller = MultiAttemptController(
        solver_factory,
        budget=AttemptBudget(
            max_attempts=max_attempts,
            max_total_steps=args.total_steps,
            max_total_seconds=args.total_seconds,
        ),
        stop_on_success=(group.name == "B0"),
        sharing_policy=group.sharing_policy,
    )

    started_at = time.time()
    with collect_usage() as ledger:
        result = controller.solve(args.query, args.image)

    record: dict[str, Any] = {
        "schema_version": 1,
        "run_id": f"{int(started_at)}-{group.name}",
        "created_at_unix": started_at,
        "group": asdict(group),
        "configuration": {
            "model": args.model,
            "cache_model": args.cache_model,
            "tools": args.tools,
            "output_types": args.output_types,
            "total_steps": args.total_steps,
            "steps_per_attempt": args.steps_per_attempt,
            "total_seconds": args.total_seconds,
            "seconds_per_attempt": args.seconds_per_attempt,
            "plan_cache_path": args.plan_cache_path,
        },
        "environment": {
            "python": platform.python_version(),
            "platform": platform.platform(),
        },
        "result": result,
        "metrics": summarize_result(result),
        "usage": ledger.snapshot(),
    }
    if args.expected_answer is not None:
        record["evaluation"] = {
            "expected_answer": args.expected_answer,
            "exact_match": _normalize_answer(result["selected_answer"])
            == _normalize_answer(args.expected_answer),
        }
    return record


def append_jsonl(path: str | Path, record: dict[str, Any]) -> Path:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(record, ensure_ascii=False, default=str))
        stream.write("\n")
    return output_path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run a budget-matched OctoTools memory experiment."
    )
    parser.add_argument("--query", required=True)
    parser.add_argument("--group", choices=sorted(EXPERIMENT_GROUPS), required=True)
    parser.add_argument(
        "--model",
        default=os.getenv("OCTOTOOLS_MODEL", "gpt-4o"),
    )
    parser.add_argument("--cache-model", default=None)
    parser.add_argument("--tools", default="generalist_solution_generator")
    parser.add_argument("--output-types", default="direct")
    parser.add_argument("--image", default=None)
    parser.add_argument("--expected-answer", default=None)
    parser.add_argument("--attempts", type=int, default=None)
    parser.add_argument("--total-steps", type=int, default=12)
    parser.add_argument("--steps-per-attempt", type=int, default=4)
    parser.add_argument("--total-seconds", type=float, default=900.0)
    parser.add_argument("--seconds-per-attempt", type=int, default=300)
    parser.add_argument("--max-tokens", type=int, default=4000)
    parser.add_argument(
        "--plan-cache-path",
        default="solver_cache/apc_experiment.json",
    )
    parser.add_argument("--plan-cache-max-size", type=int, default=128)
    parser.add_argument("--solver-cache-dir", default="solver_cache")
    parser.add_argument(
        "--output",
        default="experiment_runs/results.jsonl",
    )
    parser.add_argument("--verbose", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    args.tools = [item.strip() for item in args.tools.split(",") if item.strip()]
    args.output_types = ",".join(
        item.strip() for item in args.output_types.split(",") if item.strip()
    )
    record = run_experiment(args)
    output_path = append_jsonl(args.output, record)
    print(json.dumps(record, indent=2, ensure_ascii=False, default=str))
    print(f"Experiment appended to {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
