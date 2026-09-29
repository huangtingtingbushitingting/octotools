"""Train a PEFT LoRA used exclusively by VerilogExpertRepairTool."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Sequence


def _load_rows(path: Path) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    with path.open("r", encoding="utf-8-sig") as stream:
        for line_number, line in enumerate(stream, start=1):
            if not line.strip():
                continue
            row = json.loads(line)
            missing = {"system", "prompt", "response"} - set(row)
            if missing:
                raise ValueError(f"line {line_number} is missing {sorted(missing)}")
            rows.append({key: str(row[key]) for key in ("system", "prompt", "response")})
    if not rows:
        raise ValueError("training dataset is empty")
    return rows


def _encode_rows(tokenizer: Any, rows: list[dict[str, str]], max_length: int):
    import torch

    encoded = []
    lengths = []
    for row in rows:
        prompt_messages = [
            {"role": "system", "content": row["system"]},
            {"role": "user", "content": row["prompt"]},
        ]
        prompt_text = tokenizer.apply_chat_template(
            prompt_messages, add_generation_prompt=True, tokenize=False
        )
        prompt_ids = tokenizer(prompt_text, add_special_tokens=False)["input_ids"]
        response_ids = tokenizer(
            row["response"] + tokenizer.eos_token, add_special_tokens=False
        )["input_ids"]
        original_length = len(prompt_ids) + len(response_ids)
        lengths.append(original_length)
        if len(response_ids) >= max_length:
            response_ids = response_ids[: max_length - 1] + [tokenizer.eos_token_id]
            prompt_ids = []
        else:
            prompt_ids = prompt_ids[-(max_length - len(response_ids)) :]
        input_ids = prompt_ids + response_ids
        labels = [-100] * len(prompt_ids) + response_ids.copy()
        encoded.append(
            {
                "input_ids": torch.tensor(input_ids, dtype=torch.long),
                "attention_mask": torch.ones(len(input_ids), dtype=torch.long),
                "labels": torch.tensor(labels, dtype=torch.long),
            }
        )
    return encoded, lengths


class _ListDataset:
    def __init__(self, rows):
        self.rows = rows

    def __len__(self):
        return len(self.rows)

    def __getitem__(self, index):
        return self.rows[index]


class _RepairCollator:
    def __init__(self, pad_token_id: int):
        self.pad_token_id = pad_token_id

    def __call__(self, features):
        import torch

        width = max(len(item["input_ids"]) for item in features)
        batch = {"input_ids": [], "attention_mask": [], "labels": []}
        for item in features:
            padding = width - len(item["input_ids"])
            batch["input_ids"].append(
                torch.cat(
                    [
                        item["input_ids"],
                        torch.full((padding,), self.pad_token_id, dtype=torch.long),
                    ]
                )
            )
            batch["attention_mask"].append(
                torch.cat(
                    [item["attention_mask"], torch.zeros(padding, dtype=torch.long)]
                )
            )
            batch["labels"].append(
                torch.cat([item["labels"], torch.full((padding,), -100, dtype=torch.long)])
            )
        return {key: torch.stack(value) for key, value in batch.items()}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="octoverilog-train-repair-lora")
    parser.add_argument("--model", required=True)
    parser.add_argument("--train-file", type=Path, required=True)
    parser.add_argument("--validation-file", type=Path)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--max-length", type=int, default=4096)
    parser.add_argument("--epochs", type=float, default=8.0)
    parser.add_argument("--learning-rate", type=float, default=1e-4)
    parser.add_argument("--gradient-accumulation-steps", type=int, default=4)
    parser.add_argument("--lora-rank", type=int, default=16)
    parser.add_argument("--lora-alpha", type=int, default=32)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--dry-run", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        import torch
        from peft import LoraConfig, get_peft_model
        from transformers import (
            AutoModelForCausalLM,
            AutoTokenizer,
            Trainer,
            TrainingArguments,
        )
    except ImportError as error:
        raise SystemExit(
            "repair-LoRA training requires torch, transformers, peft, and accelerate"
        ) from error

    train_rows = _load_rows(args.train_file)
    validation_rows = _load_rows(args.validation_file) if args.validation_file else []
    tokenizer = AutoTokenizer.from_pretrained(args.model, trust_remote_code=True)
    if tokenizer.pad_token_id is None:
        tokenizer.pad_token = tokenizer.eos_token
    train_data, train_lengths = _encode_rows(tokenizer, train_rows, args.max_length)
    validation_data, validation_lengths = _encode_rows(
        tokenizer, validation_rows, args.max_length
    ) if validation_rows else ([], [])
    length_report = {
        "train_examples": len(train_data),
        "validation_examples": len(validation_data),
        "max_length": args.max_length,
        "train_original_token_min": min(train_lengths),
        "train_original_token_max": max(train_lengths),
        "train_truncated": sum(length > args.max_length for length in train_lengths),
        "validation_truncated": sum(
            length > args.max_length for length in validation_lengths
        ),
    }
    print(json.dumps(length_report, ensure_ascii=False, indent=2))
    if args.dry_run:
        return 0

    model = AutoModelForCausalLM.from_pretrained(
        args.model,
        trust_remote_code=True,
        torch_dtype=torch.bfloat16,
    )
    model.config.use_cache = False
    model.gradient_checkpointing_enable()
    model.enable_input_require_grads()
    lora_config = LoraConfig(
        r=args.lora_rank,
        lora_alpha=args.lora_alpha,
        lora_dropout=0.05,
        bias="none",
        task_type="CAUSAL_LM",
        target_modules=[
            "q_proj",
            "k_proj",
            "v_proj",
            "o_proj",
            "gate_proj",
            "up_proj",
            "down_proj",
        ],
    )
    model = get_peft_model(model, lora_config)
    model.print_trainable_parameters()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    training_args = TrainingArguments(
        output_dir=str(args.output_dir),
        num_train_epochs=args.epochs,
        per_device_train_batch_size=1,
        per_device_eval_batch_size=1,
        gradient_accumulation_steps=args.gradient_accumulation_steps,
        learning_rate=args.learning_rate,
        warmup_ratio=0.05,
        lr_scheduler_type="cosine",
        bf16=True,
        logging_steps=1,
        save_strategy="epoch",
        eval_strategy="epoch" if validation_data else "no",
        report_to="none",
        remove_unused_columns=False,
        gradient_checkpointing=True,
        ddp_find_unused_parameters=False,
        seed=args.seed,
    )
    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=_ListDataset(train_data),
        eval_dataset=_ListDataset(validation_data) if validation_data else None,
        data_collator=_RepairCollator(tokenizer.pad_token_id),
    )
    trainer.train()
    trainer.save_model(str(args.output_dir))
    tokenizer.save_pretrained(str(args.output_dir))
    (args.output_dir / "training_metadata.json").write_text(
        json.dumps(
            {
                **length_report,
                "purpose": "repair_only",
                "base_model": args.model,
                "lora_rank": args.lora_rank,
                "lora_alpha": args.lora_alpha,
                "learning_rate": args.learning_rate,
                "epochs": args.epochs,
                "seed": args.seed,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
