"""Paired held-out evaluation of base repair versus category LoRA repair."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from octotools.tools.verilog_expert_repair.tool import VerilogExpertRepairTool
from octotools.tools.verilog_repair.tool import VerilogRepairTool

from .collector import read_jsonl, write_jsonl
from .rtl_error_analysis import verify_code


def _evaluate_output(
    result: dict[str, Any], testbench: str, top_module: str, support_code: str | None
) -> dict[str, Any]:
    code = str(result.get("code") or "")
    if not result.get("success") or not code:
        return {
            "gate_passed": False,
            "generation_error": result.get("error") or "empty repaired RTL",
        }
    return verify_code(code, testbench, top_module, support_code=support_code)


def evaluate_held_out(
    dataset_path: str | Path,
    output_dir: str | Path,
    base_model: str,
    expert_registry: str | Path,
    *,
    temperature: float = 0.0,
    max_tokens: int = 4096,
    limit: int | None = None,
) -> dict[str, Any]:
    rows = read_jsonl(dataset_path)
    if limit is not None:
        rows = rows[:limit]
    baseline_tool = VerilogRepairTool(model_string=base_model)
    expert_tool = VerilogExpertRepairTool(model_string=base_model)
    results: list[dict[str, Any]] = []

    for row in rows:
        common = {
            "specification": str(row["specification"]),
            "candidate_code": str(row["incorrect_code"]),
            "verification_feedback": str(row["error_feedback"]),
            "top_module": str(row["top_module"]),
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        baseline = baseline_tool.execute(**common)
        expert = expert_tool.execute(
            **common,
            error_category=str(row["error_category"]),
            registry_path=str(expert_registry),
            strict_expert=True,
        )
        baseline_verification = _evaluate_output(
            baseline,
            str(row["testbench"]),
            str(row["top_module"]),
            row.get("reference_module"),
        )
        expert_verification = _evaluate_output(
            expert,
            str(row["testbench"]),
            str(row["top_module"]),
            row.get("reference_module"),
        )
        results.append(
            {
                "task_id": row["task_id"],
                "source_model": row.get("source_model"),
                "error_category": row["error_category"],
                "baseline": {
                    **baseline,
                    "verification": baseline_verification,
                },
                "expert": {
                    **expert,
                    "verification": expert_verification,
                },
            }
        )

    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    write_jsonl(output / "paired_results.jsonl", results)
    baseline_passed = sum(
        item["baseline"]["verification"].get("gate_passed") is True
        for item in results
    )
    expert_passed = sum(
        item["expert"]["verification"].get("gate_passed") is True
        for item in results
    )
    total = len(results)
    summary = {
        "dataset": str(Path(dataset_path).resolve()),
        "total": total,
        "base_model": base_model,
        "baseline_passed": baseline_passed,
        "baseline_accuracy": baseline_passed / total if total else 0.0,
        "expert_passed": expert_passed,
        "expert_accuracy": expert_passed / total if total else 0.0,
        "absolute_accuracy_gain": (
            (expert_passed - baseline_passed) / total if total else 0.0
        ),
        "strict_expert": True,
    }
    (output / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return summary
