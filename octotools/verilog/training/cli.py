"""CLI for collecting and preparing repair-LoRA data."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence

from .evaluate import evaluate_held_out
from .pairs import build_pairs, write_pair_outputs
from .rtl_error_analysis import CATEGORY_CASES, prepare_category


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="octoverilog-repair-data")
    commands = parser.add_subparsers(dest="command", required=True)

    traces = commands.add_parser("from-traces")
    traces.add_argument("--trace", type=Path, required=True)
    traces.add_argument("--output-dir", type=Path, required=True)

    public = commands.add_parser("from-rtl-error-analysis")
    public.add_argument("--source", type=Path, required=True)
    public.add_argument("--output-dir", type=Path, required=True)
    public.add_argument(
        "--category", choices=sorted(CATEGORY_CASES), default="wire_in_always_block"
    )

    evaluate = commands.add_parser("evaluate-held-out")
    evaluate.add_argument("--dataset", type=Path, required=True)
    evaluate.add_argument("--output-dir", type=Path, required=True)
    evaluate.add_argument("--model", required=True)
    evaluate.add_argument("--expert-registry", type=Path, required=True)
    evaluate.add_argument("--temperature", type=float, default=0.0)
    evaluate.add_argument("--max-tokens", type=int, default=4096)
    evaluate.add_argument("--limit", type=int)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "from-traces":
        pairs = build_pairs(args.trace)
        write_pair_outputs(pairs, args.output_dir)
        print(json.dumps({"verified_pairs": len(pairs)}, ensure_ascii=False, indent=2))
        return 0
    if args.command == "evaluate-held-out":
        summary = evaluate_held_out(
            args.dataset,
            args.output_dir,
            args.model,
            args.expert_registry,
            temperature=args.temperature,
            max_tokens=args.max_tokens,
            limit=args.limit,
        )
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        return 0
    summary = prepare_category(args.source, args.output_dir, args.category)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
