"""Build EDA-gated directional repair data from known-good RTL."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any

from octotools.verilog.training.inject_errors import inject_errors
from octotools.verilog.training.pairs import REPAIR_SYSTEM_PROMPT, repair_prompt, verification_feedback
from octotools.verilog.training.rtl_error_analysis import _read_first, _rename_first_module, verify_code


TEMPORAL_HINTS = re.compile(r"fsm|state|counter|lfsr|uart|ps2|traffic|timer|clock|edge|sequence|handshake|gshare", re.I)
NUMERIC_HINTS = re.compile(r"adder|mult|divider|vector|shifter|mux|kmap|circuit|alu|bit|width|carry|comparator", re.I)


def _family_for(case_name: str) -> str:
    if TEMPORAL_HINTS.search(case_name):
        return "temporal_fsm"
    if NUMERIC_HINTS.search(case_name):
        return "numeric_vector"
    return "general_complex"


def _mixed_mutation(code: str) -> list[dict[str, str]]:
    first = inject_errors(code, "structural")
    second = inject_errors(code, "temporal_fsm")
    if not first or not second:
        return []
    return [{"variant": "mixed_structural_temporal", "code": second[0]["code"].replace("posedge", "negedge", 1)}]


def _split(task_id: str) -> str:
    value = int(hashlib.sha256(task_id.encode()).hexdigest()[:8], 16) % 100
    return "train" if value < 70 else "validation" if value < 85 else "test"


def build(source_root: str | Path, output_root: str | Path, *, limit: int = 60) -> dict[str, Any]:
    source_root, output_root = Path(source_root), Path(output_root)
    accepted: dict[str, list[dict[str, Any]]] = {"temporal_fsm": [], "numeric_vector": [], "general_complex": []}
    scanned = 0
    for case in sorted(source_root.glob("*/*")):
        if not case.is_dir() or not (case / "ref_design.sv").is_file() or not (case / "testbench.sv").is_file():
            continue
        family = _family_for(case.name)
        if len(accepted[family]) >= limit:
            if all(len(values) >= limit for values in accepted.values()):
                break
            continue
        scanned += 1
        try:
            reference = _read_first(case, ("ref.sv", "ref_design.sv"))
            testbench = _read_first(case, ("test.sv", "testbench.sv"))
            specification = _read_first(case, ("description.txt", "design_description.txt"))
            correct = _rename_first_module(reference, "TopModule")
            before = verify_code(correct, testbench, "TopModule", support_code=reference)
            if not before["gate_passed"]:
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
                    "split": _split(f"{case.parent.name}/{case.name}"),
                }
                row["error_feedback"] = verification_feedback(failed)
                row["system"] = REPAIR_SYSTEM_PROMPT
                row["prompt"] = repair_prompt(specification, mutation["code"], row["error_feedback"], family)
                row["response"] = correct
                accepted[family].append(row)
        except (OSError, ValueError, KeyError):
            continue
    for family, rows in accepted.items():
        directory = output_root / family
        directory.mkdir(parents=True, exist_ok=True)
        directory.joinpath("repair_pairs.audit.jsonl").write_text("\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n", encoding="utf-8")
        for split in ("train", "validation", "test"):
            subset = [row for row in rows if row["split"] == split]
            directory.joinpath(f"{split}.sft.jsonl").write_text("\n".join(json.dumps({"system": row["system"], "prompt": row["prompt"], "response": row["response"]}, ensure_ascii=False) for row in subset) + "\n", encoding="utf-8")
            directory.joinpath(f"{split}.evaluation.jsonl").write_text("\n".join(json.dumps(row, ensure_ascii=False) for row in subset) + "\n", encoding="utf-8")
        directory.joinpath("summary.json").write_text(json.dumps({"family": family, "accepted": len(rows), "scanned": scanned, "source": "directional_injection", "acceptance_rule": "known-good RTL passes, injected RTL fails, known-good RTL is repair target"}, ensure_ascii=False, indent=2), encoding="utf-8")
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
