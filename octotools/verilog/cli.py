"""Command-line interface for focused Verilog generation.是OctoVerilog的命令行接口，把底层的verilog生成流水线包装成用户友好的命令行工具"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Sequence

from .dataset import iter_dataset
from .pipeline import VerilogPipeline
from .progress import ConsoleProgress, PipelineEvent


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
    parser.add_argument(
        "--candidates-per-round",
        type=int,
        default=1,
        help="number of candidates verified and ranked in each generation/repair round",
    )
    parser.add_argument(
        "--trace-file",
        type=Path,
        help="append every candidate, EDA result, score, model, and token count as JSONL",
    )
    parser.add_argument(
        "--expert-registry",
        type=Path,
        help="JSON registry mapping error categories to repair-only LoRA models",
    )
    parser.add_argument(
        "--strict-expert",
        action="store_true",
        help="fail a repair instead of falling back when the selected expert is unavailable",
    )
    parser.add_argument("--synthesize", action="store_true")
    parser.add_argument(
        "--reference-file",
        type=Path,
        help="reference RTL for mandatory Yosys formal-equivalence checking",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="hide the OctoTools-style task progress display",
    )


def _saved_message(path: Path) -> None:
    print(f"\n==> 💾 Saved Verilog: {path.resolve()}", flush=True)


def _interactive_help() -> None:
    print(
        "\nEnter a natural-language RTL request and press Enter.\n"
        "Commands:\n"
        "  /help             show this help\n"
        "  /module NAME      change the required top-module name\n"
        "  /quit              leave interactive mode\n"
    )
#打印交互式模式的帮助工具，列出可用的命令

def _run_chat(
    args: argparse.Namespace,
    pipeline: VerilogPipeline,
    reporter: ConsoleProgress,
) -> int:
    args.output_dir.mkdir(parents=True, exist_ok=True)
    testbench = (
        args.testbench.read_text(encoding="utf-8") if args.testbench else None
    )
    reference_code = (
        args.reference_file.read_text(encoding="utf-8")
        if args.reference_file
        else None
    )
    top_module = args.top_module
    sequence = 1
    while (args.output_dir / f"design_{sequence:03d}.sv").exists():
        sequence += 1

    print("\n🐙 OctoVerilog interactive RTL generator")
    print(f"Model: {args.model}")
    print(f"Output directory: {args.output_dir.resolve()}")
    print(f"Top module: {top_module}")
    _interactive_help()

    while True:
        try:
            specification = input("octoverilog> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nLeaving OctoVerilog.")
            return 0

        if not specification:
            continue
        if specification in {"/quit", "/exit"}:
            print("Leaving OctoVerilog.")
            return 0
        if specification == "/help":
            _interactive_help()
            continue
        if specification.startswith("/module "):
            candidate = specification.removeprefix("/module ").strip()
            if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_$]*", candidate):
                print("Invalid Verilog module name.")
                continue
            top_module = candidate
            print(f"Top module changed to {top_module}.")
            continue
        if specification.startswith("/"):
            print("Unknown command. Enter /help for available commands.")
            continue

        try:
            result = pipeline.run(
                specification,
                testbench,
                reference_code=reference_code,
                top_module=top_module,
                synthesize=args.synthesize,
                temperature=args.temperature,
                max_tokens=args.max_tokens,
                task_id=f"interactive_{sequence:03d}",
                progress=reporter,
            )
        except Exception as error:  # keep the interactive session available
            reporter(PipelineEvent("error", f"Generation failed: {error}"))
            continue

        if not result.code.strip():
            print("No complete Verilog module was produced; enter a new request.")
            continue

        output = args.output_dir / f"design_{sequence:03d}.sv"
        report = args.output_dir / f"design_{sequence:03d}.report.json"
        output.write_text(result.code + "\n", encoding="utf-8")
        _write_json(report, result.to_dict())
        _saved_message(output)
        print("\n```verilog")
        print(result.code)
        print("```\n")
        sequence += 1


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
#生成单个verilog设计
    batch = commands.add_parser("batch", help="generate designs from JSON/JSONL")
    batch.add_argument("--dataset", type=Path, required=True)
    batch.add_argument("--output-dir", type=Path, required=True)
    batch.add_argument("--limit", type=int)
    _add_generation_options(batch)
#从json数据集中批量生成代码
    chat = commands.add_parser(
        "chat",
        aliases=["interactive"],
        help="interactively turn natural-language requests into Verilog",
    )
    chat.add_argument(
        "--output-dir",
        type=Path,
        default=Path("runs/interactive"),
    )
    chat.add_argument("--testbench", type=Path)
    _add_generation_options(chat)
    return parser
#交互式生成verilog

def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command in {"chat", "interactive", "batch"}:
        workspace = args.output_dir / ".agent-work"
    else:
        workspace = args.output.parent / ".agent-work"
    pipeline = VerilogPipeline.from_model(
        args.model,
        attempts=args.attempts,
        workspace_dir=str(workspace),
        verbose=not args.quiet,
        candidates_per_round=args.candidates_per_round,
        trace_file=str(args.trace_file or (workspace.parent / "candidates.jsonl")),
        expert_registry=str(args.expert_registry) if args.expert_registry else None,
        strict_expert=args.strict_expert,
    )
    reporter = ConsoleProgress(enabled=not args.quiet)

    if args.command in {"chat", "interactive"}:
        return _run_chat(args, pipeline, reporter)

    if args.command == "generate":
        specification = args.spec or args.spec_file.read_text(encoding="utf-8")
        testbench = (
            args.testbench.read_text(encoding="utf-8") if args.testbench else None
        )
        reference_code = (
            args.reference_file.read_text(encoding="utf-8")
            if args.reference_file
            else None
        )
        result = pipeline.run(
            specification,
            testbench,
            reference_code=reference_code,
            top_module=args.top_module,
            synthesize=args.synthesize,
            temperature=args.temperature,
            max_tokens=args.max_tokens,
            task_id=args.output.stem,
            progress=reporter,
        )
        if args.report:
            _write_json(args.report, result.to_dict())
        if not result.code.strip():
            print("\n==> 🚫 Delivery blocked: no candidate passed all mandatory checks.")
            return 2
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(result.code + "\n", encoding="utf-8")
        _saved_message(args.output)
        return 0

    args.output_dir.mkdir(parents=True, exist_ok=True)
    result_path = args.output_dir / "results.jsonl"
    with result_path.open("w", encoding="utf-8") as report:
        for index, record in enumerate(iter_dataset(args.dataset), start=1):
            if args.limit is not None and index > args.limit:
                break
            reporter(
                PipelineEvent(
                    "start",
                    f"Dataset task {index}: {record.task_id}",
                )
            )
            result = pipeline.run(
                record.specification,
                record.testbench,
                reference_code=record.reference_code,
                top_module=record.top_module or args.top_module,
                synthesize=args.synthesize,
                temperature=args.temperature,
                max_tokens=args.max_tokens,
                task_id=record.task_id,
                progress=reporter,
            )
            output = args.output_dir / f"{_safe_name(record.task_id)}.sv"
            output_value = None
            if result.code.strip():
                output.write_text(result.code + "\n", encoding="utf-8")
                output_value = str(output)
                _saved_message(output)
            row = {"task_id": record.task_id, "output": output_value, **result.to_dict()}
            report.write(json.dumps(row, ensure_ascii=False) + "\n")
            report.flush()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
