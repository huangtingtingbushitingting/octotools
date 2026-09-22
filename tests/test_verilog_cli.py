from pathlib import Path

from octotools.verilog.cli import build_parser


def test_chat_command_accepts_natural_language_runtime_options():
    args = build_parser().parse_args(
        [
            "chat",
            "--model",
            "vllm-codev-r1",
            "--attempts",
            "3",
            "--top-module",
            "MyTop",
            "--output-dir",
            "generated",
        ]
    )

    assert args.command == "chat"
    assert args.model == "vllm-codev-r1"
    assert args.attempts == 3
    assert args.top_module == "MyTop"
    assert args.output_dir == Path("generated")


def test_generate_accepts_reference_for_formal_equivalence():
    args = build_parser().parse_args(
        [
            "generate",
            "--model",
            "vllm-codev-r1",
            "--spec",
            "Build an adder",
            "--reference-file",
            "golden.sv",
            "--output",
            "generated.sv",
        ]
    )

    assert args.reference_file == Path("golden.sv")
