"""Build EDA-gated directional repair data from known-good RTL."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

from octotools.verilog.training.inject_errors import inject_errors
from octotools.verilog.training.pairs import REPAIR_SYSTEM_PROMPT, repair_prompt, verification_feedback
from octotools.verilog.training.rtl_error_analysis import _read_first, _rename_first_module, verify_code


FAMILIES = ("structural", "temporal_fsm", "numeric_vector", "general_complex")


def _trim_after_last_module(code: str) -> str:
    """Discard corpus annotations after RTL, without altering module bodies."""
    end = code.rfind("endmodule")
    if end < 0:
        raise ValueError("reference RTL has no endmodule")
    return code[: end + len("endmodule")].strip()


def _mixed_mutation(code: str) -> list[dict[str, str]]:
    for structural in inject_errors(code, "structural"):
        for temporal in inject_errors(structural["code"], "temporal_fsm"):
            if temporal["code"] != structural["code"]:
                return [{
                    "variant": f"mixed_{structural['variant']}_{temporal['variant']}",
                    "code": temporal["code"],
                }]
    return []


def _split_groups(rows: list[dict[str, Any]]) -> None:
    """Keep all variants and source models of one problem in one split."""
    groups = sorted(
        {str(row["problem_id"]) for row in rows},
        key=lambda key: hashlib.sha256(key.encode()).hexdigest(),
    )
    size = len(groups)
    if size >= 3:
        train_end = min(size - 2, max(1, round(size * 0.70)))
        valid_end = min(size - 1, max(train_end + 1, round(size * 0.85)))
    elif size == 2:
        train_end, valid_end = 1, 1
    else:
        train_end = valid_end = size
    mapping = {
        group: "train" if index < train_end else "validation" if index < valid_end else "test"
        for index, group in enumerate(groups)
    }
    for row in rows:
        row["split"] = mapping[row["problem_id"]]


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
        encoding="utf-8",
    )


def build(source_root: str | Path, output_root: str | Path, *, limit: int = 60) -> dict[str, Any]:
    source_root, output_root = Path(source_root), Path(output_root)
    accepted: dict[str, list[dict[str, Any]]] = {family: [] for family in FAMILIES}
    scanned = 0
    for case in sorted(source_root.glob("*/*")):
        if not case.is_dir() or not (case / "ref_design.sv").is_file() or not (case / "testbench.sv").is_file():
            continue
        if all(len(values) >= limit for values in accepted.values()):
            break
        scanned += 1
        try:
            reference = _trim_after_last_module(_read_first(case, ("ref.sv", "ref_design.sv")))
            testbench = _read_first(case, ("test.sv", "testbench.sv"))
            specification = _read_first(case, ("description.txt", "design_description.txt"))
            correct = _rename_first_module(reference, "TopModule")
            before = verify_code(correct, testbench, "TopModule", support_code=reference)
            if not before["gate_passed"]:
                continue
            for family in FAMILIES:
                if len(accepted[family]) >= limit:
                    continue
                mutations = _mixed_mutation(correct) if family == "general_complex" else inject_errors(correct, family)
                for mutation in mutations:
                    if len(accepted[family]) >= limit:
                        break
                    failed = verify_code(mutation["code"], testbench, "TopModule", support_code=reference)
                    if failed["gate_passed"]:
                        continue
                    row = {
                        "task_id": f"{case.parent.name}/{case.name}/{mutation['variant']}",
                        "problem_id": case.name,
                        "source": "directional_injection",
                        "specification": specification,
                        "incorrect_code": mutation["code"],
                        "repaired_code": correct,
                        "error_category": family,
                        "injection_variant": mutation["variant"],
                        "testbench": testbench,
                        "reference_module": reference,
                        "top_module": "TopModule",
                        "before_verification": failed,
                        "after_verification": before,
                    }
                    row["error_feedback"] = verification_feedback(failed)
                    row["system"] = REPAIR_SYSTEM_PROMPT
                    row["prompt"] = repair_prompt(specification, mutation["code"], row["error_feedback"], family)
                    row["response"] = correct
                    accepted[family].append(row)
        except (OSError, ValueError, KeyError):
            continue
    for family, rows in accepted.items():
        _split_groups(rows)
        directory = output_root / family
        directory.mkdir(parents=True, exist_ok=True)
        _write_jsonl(directory / "repair_pairs.audit.jsonl", rows)
        for split in ("train", "validation", "test"):
            subset = [row for row in rows if row["split"] == split]
            _write_jsonl(directory / f"{split}.sft.jsonl", [
                {"system": row["system"], "prompt": row["prompt"], "response": row["response"]}
                for row in subset
            ])
            _write_jsonl(directory / f"{split}.evaluation.jsonl", subset)
        summary = {
            "family": family,
            "accepted": len(rows),
            "scanned": scanned,
            "source": "directional_injection",
            "accepted_by_split": dict(Counter(row["split"] for row in rows)),
            "problem_groups_by_split": {
                split: len({row["problem_id"] for row in rows if row["split"] == split})
                for split in ("train", "validation", "test")
            },
            "acceptance_rule": "known-good RTL passes, injected RTL fails, known-good RTL is repair target",
        }
        (directory / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return {family: len(rows) for family, rows in accepted.items()}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--limit", type=int, default=60)
    args = parser.parse_args()
    print(json.dumps(build(args.source_root, args.output_root, limit=args.limit), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
