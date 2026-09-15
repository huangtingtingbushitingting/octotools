"""Command-line interface for focused Verilog generation."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Sequence

from .dataset import iter_dataset
from .pipeline import VerilogPipeline


def _safe_name(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_.-]+", "_", value).strip("._")
    return cleaned or "task"


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def _add_generation_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--model", required=True, help="OctoTools model string")
    parser.add_argument("--attempts", type=int, default=1)
    parser.add_argument("--top-module", default="TopModule")
    parser.add_argument("--temperature", type=float, default=0.2)
    parser.add_argument("--max-tokens", type=int, default=4096)
    parser.add_argument("--synthesize", action="store_true")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="octoverilog")
    commands = parser.add_subparsers(dest="command", required=True)

    generate = commands.add_parser("generate", help="generate one Verilog design")
    source = generate.add_mutually_exclusive_group(required=True)
    source.add_argument("--spec")
    source.add_argument("--spec-file", type=Path)
    generate.add_argument("--testbench", type=Path)
    generate.add_argument("--output", type=Path, required=True)
    generate.add_argument("--report", type=Path)
    _add_generation_options(generate)

    batch = commands.add_parser("batch", help="generate designs from JSON/JSONL")
    batch.add_argument("--dataset", type=Path, required=True)
    batch.add_argument("--output-dir", type=Path, required=True)
    batch.add_argument("--limit", type=int)
    _add_generation_options(batch)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    pipeline = VerilogPipeline.from_model(args.model, attempts=args.attempts)

    if args.command == "generate":
        specification = args.spec or args.spec_file.read_text(encoding="utf-8")
        testbench = (
            args.testbench.read_text(encoding="utf-8") if args.testbench else None
        )
        result = pipeline.run(
            specification,
            testbench,
            top_module=args.top_module,
            synthesize=args.synthesize,
            temperature=args.temperature,
            max_tokens=args.max_tokens,
        )
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(result.code + "\n", encoding="utf-8")
        if args.report:
            _write_json(args.report, result.to_dict())
        return 0

    args.output_dir.mkdir(parents=True, exist_ok=True)
    result_path = args.output_dir / "results.jsonl"
    with result_path.open("w", encoding="utf-8") as report:
        for index, record in enumerate(iter_dataset(args.dataset), start=1):
            if args.limit is not None and index > args.limit:
                break
            result = pipeline.run(
                record.specification,
                record.testbench,
                top_module=args.top_module,
                synthesize=args.synthesize,
                temperature=args.temperature,
                max_tokens=args.max_tokens,
            )
            output = args.output_dir / f"{_safe_name(record.task_id)}.sv"
            output.write_text(result.code + "\n", encoding="utf-8")
            row = {"task_id": record.task_id, "output": str(output), **result.to_dict()}
            report.write(json.dumps(row, ensure_ascii=False) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
