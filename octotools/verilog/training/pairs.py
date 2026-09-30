"""Convert verified repair transitions into SFT-ready examples.构建用于SFT的代码对"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

from .collector import read_jsonl, write_jsonl
from .schema import RepairPair


REPAIR_SYSTEM_PROMPT = (
    "You are a Verilog repair expert. Return only the complete corrected, "
    "synthesizable RTL module. Preserve the required interface exactly."
)


def verification_feedback(verification: dict[str, Any]) -> str:
    """Keep actionable EDA diagnostics within the model context budget."""
    compact: dict[str, Any] = {"gate_passed": verification.get("gate_passed")}
    for stage in ("compile", "simulation", "synthesis", "equivalence"):
        result = verification.get(stage)
        if not isinstance(result, dict):
            continue
        item: dict[str, Any] = {}
        for key in (
            "compile_success", "simulation_success", "synthesis_success",
            "equivalence_success", "returncode", "error", "reported_failure_counts",
        ):
            if key in result:
                item[key] = result[key]
        diagnostic = "\n".join(
            str(result.get(key) or "") for key in ("stderr", "stdout", "output")
        )
        important = [
            line for line in diagnostic.splitlines()
            if any(word in line.lower() for word in (
                "error", "warning", "mismatch", "first", "failed", "timeout",
            ))
        ]
        diagnostic = "\n".join((important or diagnostic.splitlines())[-8:])[-900:]
        diagnostic = re.sub(r"/tmp/[^\s:]+/", "<temporary>/", diagnostic)
        item["diagnostic"] = diagnostic
        compact[stage] = item
    return json.dumps(compact, ensure_ascii=False, separators=(",", ":"))[:3000]


def repair_prompt(
    specification: str,
    incorrect_code: str,
    feedback: str,
    error_category: str,
) -> str:
    return (
        f"Design specification:\n{specification.strip()}\n\n"
        f"Detected error category: {error_category}\n\n"
        f"Failed RTL:\n```verilog\n{incorrect_code.strip()}\n```\n\n"
        f"EDA compiler/simulation/synthesis feedback:\n{feedback.strip()}\n\n"
        "Repair the failed RTL and return the complete corrected module."
    )


def build_pairs(trace_path: str | Path) -> list[RepairPair]:
    rows = read_jsonl(trace_path)
    by_id = {str(row.get("candidate_id")): row for row in rows}
    pairs: list[RepairPair] = []
    for repaired in rows:
        parent_id = repaired.get("parent_candidate_id")
        if not parent_id or repaired.get("gate_passed") is not True:
            continue
        failed = by_id.get(str(parent_id))
        if not failed or failed.get("gate_passed") is True:
            continue
        specification = str(repaired.get("metadata", {}).get("specification") or "")
        category = str(failed.get("error_category") or "unclassified")
        feedback = verification_feedback(failed.get("verification") or {})
        pair_id = hashlib.sha256(
            f"{failed.get('run_id')}:{parent_id}:{repaired.get('candidate_id')}".encode()
        ).hexdigest()[:20]
        pairs.append(
            RepairPair(
                pair_id=pair_id,
                task_id=str(repaired.get("task_id") or "task"),
                error_category=category,
                system=REPAIR_SYSTEM_PROMPT,
                prompt=repair_prompt(
                    specification,
                    str(failed.get("extracted_code") or ""),
                    feedback,
                    category,
                ),
                response=str(repaired.get("extracted_code") or ""),
                specification=specification,
                incorrect_code=str(failed.get("extracted_code") or ""),
                repaired_code=str(repaired.get("extracted_code") or ""),
                error_feedback=feedback,
                source_model=str(failed.get("model_name") or ""),
                repair_model=str(repaired.get("model_name") or ""),
                source_candidate_id=str(parent_id),
                repaired_candidate_id=str(repaired.get("candidate_id") or ""),
                before_verification=failed.get("verification") or {},
                after_verification=repaired.get("verification") or {},
                provenance={"source": "octoverilog_trace"},
            )
        )
    return pairs


def write_pair_outputs(pairs: list[RepairPair], output_dir: str | Path) -> None:#将提取的修复保存为两种数据结构
    root = Path(output_dir)
    root.mkdir(parents=True, exist_ok=True)
    write_jsonl(root / "repair_pairs.audit.jsonl", (pair.to_dict() for pair in pairs))#保存完整字典，用于审计与查看所有字段
    write_jsonl(root / "repair_pairs.sft.jsonl", (pair.to_sft_dict() for pair in pairs))#直接用于SFT，只包含system,prompt,response
