"""Directional error injection for repair-LoRA training data.

Only samples that pass before injection and fail after injection should be
written by the caller; this module creates mutations and leaves EDA gating to
the existing Verifier/tools.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any, Iterable


INJECTION_FAMILIES = ("structural", "temporal_fsm", "numeric_vector")


def _first_match(pattern: str, code: str):
    return re.search(pattern, code, flags=re.IGNORECASE | re.MULTILINE)


def inject_structural(code: str) -> list[dict[str, str]]:
    mutations: list[dict[str, str]] = []
    match = _first_match(r"\breg\b", code)
    if match:
        mutations.append({"variant": "reg_to_wire", "code": code[:match.start()] + "wire" + code[match.end():]})
    match = _first_match(r"\b(?:reg|logic|wire)\b(?:\s*\[[^]]+\])?\s+([A-Za-z_]\w*)\s*;", code)
    if match:
        mutations.append({"variant": "delete_declaration", "code": code[:match.start()] + code[match.end():]})
        declaration = code[match.start():match.end()]
        mutations.append({"variant": "duplicate_declaration", "code": code[:match.end()] + declaration + code[match.end():]})
    match = _first_match(r"\[([0-9]+):([0-9]+)\]", code)
    if match:
        high, low = int(match.group(1)), int(match.group(2))
        bad = f"[{high + 1}:{low}]"
        mutations.append({"variant": "out_of_bounds_slice", "code": code[:match.start()] + bad + code[match.end():]})
    return mutations


def inject_temporal_fsm(code: str) -> list[dict[str, str]]:
    mutations: list[dict[str, str]] = []
    match = _first_match(r"posedge", code)
    if match:
        mutations.append({"variant": "posedge_to_negedge", "code": code[:match.start()] + "negedge" + code[match.end():]})
    match = _first_match(r"\b<=\b", code)
    if match:
        mutations.append({"variant": "nonblocking_to_blocking", "code": code[:match.start()] + "=" + code[match.end():]})
    match = _first_match(r"if\s*\(\s*!\s*([A-Za-z_]\w*)\s*\)", code)
    if match:
        signal = match.group(1)
        replacement = f"if ({signal})"
        mutations.append({"variant": "reset_polarity_flip", "code": code[:match.start()] + replacement + code[match.end():]})
    return mutations


def inject_numeric_vector(code: str) -> list[dict[str, str]]:
    mutations: list[dict[str, str]] = []
    match = _first_match(r"\b(?:logic|reg|wire)\s*\[([0-9]+):([0-9]+)\]", code)
    if match:
        high, low = int(match.group(1)), int(match.group(2))
        bad = f"[{max(low, high - 1)}:{low}]"
        mutations.append({"variant": "width_reduction", "code": code[:match.start(1) - 1] + bad + code[match.end(2) + 1:]})
    match = _first_match(r"<<", code)
    if match:
        mutations.append({"variant": "left_to_right_shift", "code": code[:match.start()] + ">>" + code[match.end():]})
    match = _first_match(r"\[([0-9]+):([0-9]+)\]", code)
    if match:
        mutations.append({"variant": "slice_direction_flip", "code": code[:match.start()] + f"[{match.group(2)}:{match.group(1)}]" + code[match.end():]})
    return mutations


def inject_errors(code: str, family: str) -> list[dict[str, str]]:
    if family == "structural":
        return inject_structural(code)
    if family == "temporal_fsm":
        return inject_temporal_fsm(code)
    if family == "numeric_vector":
        return inject_numeric_vector(code)
    raise ValueError(f"unsupported injection family: {family}")


def build_injected_records(rows: Iterable[dict[str, Any]], family: str) -> list[dict[str, Any]]:
    output = []
    for row in rows:
        code = str(row.get("code") or row.get("reference_code") or row.get("rtl") or "")
        if not code.strip():
            continue
        for mutation in inject_errors(code, family):
            output.append({
                "task_id": f"{row.get('task_id', 'task')}/{mutation['variant']}",
                "specification": row.get("specification", ""),
                "correct_code": code,
                "incorrect_code": mutation["code"],
                "error_category": family,
                "injection_variant": mutation["variant"],
                "source": "directional_injection",
                "requires_eda_gate": True,
            })
    return output


def main() -> int:
    parser = argparse.ArgumentParser(prog="octoverilog-inject-errors")
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--family", choices=INJECTION_FAMILIES, required=True)
    args = parser.parse_args()
    rows = [json.loads(line) for line in args.input.read_text(encoding="utf-8").splitlines() if line.strip()]
    records = build_injected_records(rows, args.family)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text("\n".join(json.dumps(row, ensure_ascii=False) for row in records) + "\n", encoding="utf-8")
    print(json.dumps({"family": args.family, "records": len(records), "output": str(args.output)}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
