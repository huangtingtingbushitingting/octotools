"""Prepare verified repair-LoRA data from the public RTLErrorAnalysis corpus.

This module extracts verified bad-RTL to repaired-RTL pairs from the
public error-analysis corpus.
"""
from __future__ import annotations

import hashlib
import json
import re
import tempfile
from pathlib import Path
from typing import Any

from octotools.tools.iverilog.tool import IverilogTool
from octotools.tools.vvp.tool import VvpTool
from octotools.tools.yosys.tool import YosysTool

from .collector import write_jsonl
from .pairs import REPAIR_SYSTEM_PROMPT, repair_prompt, verification_feedback


WIRE_IN_ALWAYS_CASES = {
    "qwen2.5-coder-32b-instruct": {68, 79, 88, 100, 119, 138, 140, 144, 156},
    "gpt-3.5-turbo": {79, 100, 107, 111, 139, 140, 143, 146},
    "gpt-4-turbo": {68},
}#定义wire_in_always_block错误类别下，各个模型对应的RTLErrorAnalysis 公开语料库中“问题（Problem）”的序号
    ##不同模型在不同问题上烦的错误类型不同，这里的指的是不同模型在该编号下犯了wire_in_always_block错误
CATEGORY_CASES = {"wire_in_always_block": WIRE_IN_ALWAYS_CASES}


def _read_first(root: Path, names: tuple[str, ...]) -> str:
    for name in names:
        path = root / name
        if path.is_file():
            return path.read_text(encoding="utf-8-sig").strip()
    raise FileNotFoundError(f"none of {names} exists in {root}")


def _top_module(code: str) -> str:#提取模块的模块名
    match = re.search(r"\bmodule\s+([A-Za-z_][A-Za-z0-9_$]*)", code)
    if not match:
        raise ValueError("reference RTL has no module declaration")
    return match.group(1)


def _rename_first_module(code: str, module_name: str) -> str:#重命名模块名
    renamed, count = re.subn(
        r"(\bmodule\s+)([A-Za-z_][A-Za-z0-9_$]*)",
        rf"\g<1>{module_name}",
        code,
        count=1,
    )
    if count != 1:
        raise ValueError("reference RTL has no module declaration")
    return renamed


def verify_code(
    code: str,
    testbench: str,
    top_module: str,
    support_code: str | None = None,#参考代码，用于和源代码拼接在一起进行编译
) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="octoverilog-repair-data-") as temp:
        compiler = IverilogTool()
        compiler.set_custom_output_dir(temp)
        compile_source = f"{support_code}\n\n{code}" if support_code else code
        compile_result = compiler.execute(#对verilog进行编译
            source_code=compile_source,
            top_module=top_module,
            testbench=testbench,
            candidate_name="candidate",
        )
        simulation: dict[str, Any] = {
            "success": False,
            "simulation_success": False,
            "error": "compile failed",
        }
        if compile_result.get("artifact_path"):
            simulator = VvpTool()
            simulator.set_custom_output_dir(temp)
            simulation = simulator.execute(compile_result["artifact_path"])#进行仿真
        synthesis_tool = YosysTool()
        synthesis_tool.set_custom_output_dir(temp)
        synthesis = synthesis_tool.execute(#综合检查
            source_code=code,
            top_module=top_module,
            candidate_name="candidate",
        )
        passed = (
            compile_result.get("compile_success") is True
            and simulation.get("simulation_success") is True
            and synthesis.get("synthesis_success") is True
        )#判断三个阶段是否都通过
        return {
            "compile": compile_result,
            "simulation": simulation,
            "synthesis": synthesis,
            "gate_passed": passed,
        }


def _split_map(task_ids: set[str]) -> dict[str, str]:
    ordered = sorted(
        task_ids,
        key=lambda value: hashlib.sha256(value.encode()).hexdigest(),
    )
    train_end = max(1, round(len(ordered) * 0.70))
    valid_end = max(train_end + 1, round(len(ordered) * 0.85))
    return {
        task_id: "train" if index < train_end else "validation" if index < valid_end else "test"
        for index, task_id in enumerate(ordered)
    }


def prepare_category(
    source_root: str | Path,
    output_dir: str | Path,
    category: str = "wire_in_always_block",
) -> dict[str, Any]:
    if category not in CATEGORY_CASES:
        raise ValueError(f"unsupported category: {category}")
    root = Path(source_root)
    cases: list[tuple[str, Path, str]] = []
    for model, numbers in CATEGORY_CASES[category].items():
        model_root = root / model
        for number in sorted(numbers):
            matches = sorted(model_root.glob(f"Prob{number:03d}_*"))
            if len(matches) != 1:
                raise FileNotFoundError(
                    f"expected one Prob{number:03d}_* directory under {model_root}"
                )
            task_id = matches[0].name
            cases.append((model, matches[0], task_id))
    splits = _split_map({task_id for _, _, task_id in cases})
    accepted: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []

    for model, case_dir, task_id in cases:
        specification = _read_first(case_dir, ("description.txt", "design_description.txt"))
        incorrect = _read_first(case_dir, ("design.sv",))
        reference_module = _read_first(case_dir, ("ref.sv", "ref_design.sv"))
        testbench = _read_first(case_dir, ("test.sv", "testbench.sv"))
        top_module = _top_module(incorrect)
        repaired = _rename_first_module(reference_module, top_module)
        before = verify_code(
            incorrect, testbench, top_module, support_code=reference_module
        )
        after = verify_code(
            repaired, testbench, top_module, support_code=reference_module
        )
        base = {
            "task_id": task_id,
            "source_model": model,
            "error_category": category,
            "split": splits[task_id],
            "specification": specification,
            "incorrect_code": incorrect,
            "repaired_code": repaired,
            "testbench": testbench,
            "reference_module": reference_module,
            "top_module": top_module,
            "before_verification": before,
            "after_verification": after,
            "source_path": str(case_dir),
        }
        if before["gate_passed"] or not after["gate_passed"]:
            base["rejection_reason"] = (
                "incorrect RTL unexpectedly passed" if before["gate_passed"]
                else "reference RTL did not pass all gates"
            )
            rejected.append(base)
            continue
        feedback = verification_feedback(before)
        pair_id = hashlib.sha256(f"{model}:{task_id}:{category}".encode()).hexdigest()[:20]
        base.update(
            {
                "pair_id": pair_id,
                "system": REPAIR_SYSTEM_PROMPT,
                "prompt": repair_prompt(
                    specification, incorrect, feedback, category
                ),
                "response": repaired,
                "error_feedback": feedback,
            }
        )
        accepted.append(base)

    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    write_jsonl(output / "repair_pairs.audit.jsonl", accepted)
    write_jsonl(output / "rejected.audit.jsonl", rejected)
    for split in ("train", "validation", "test"):
        rows = [
            {"system": row["system"], "prompt": row["prompt"], "response": row["response"]}
            for row in accepted
            if row["split"] == split
        ]
        write_jsonl(output / f"{split}.sft.jsonl", rows)
        write_jsonl(
            output / f"{split}.evaluation.jsonl",
            (row for row in accepted if row["split"] == split),
        )
    summary = {
        "category": category,
        "source_cases": len(cases),
        "accepted": len(accepted),
        "rejected": len(rejected),
        "accepted_by_split": {
            split: sum(row["split"] == split for row in accepted)
            for split in ("train", "validation", "test")
        },
        "grouped_by_task_id": True,
        "acceptance_rule": "failed source RTL and reference RTL passing iverilog, vvp, and yosys",
    }
    (output / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return summary
