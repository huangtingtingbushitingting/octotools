# Category-specific repair LoRA

The LoRA adapters in this project are used only after the initial CodeV-R1
candidate fails deterministic EDA verification. They do not replace the initial
generator.

## Data contract

Each accepted sample is:

- input: design specification + failed RTL + Icarus/Yosys feedback + category;
- output: a complete repaired RTL module that passes Icarus simulation and Yosys;
- split: grouped by problem ID so variants from different source models cannot
  leak across train, validation, and test.

Prepare the first pilot category:

```bash
export OCTOVERILOG_IVERILOG_PATH=/usr/local/bin/iverilog
export OCTOVERILOG_VVP_PATH=/usr/local/bin/vvp

python -m octotools.verilog.training.cli from-rtl-error-analysis \
  --source /home/htt/projects/RTLErrorAnalysis/error_analysis \
  --category wire_in_always_block \
  --output-dir /home/htt/OctoVerilog/datasets/repair/wire_in_always_block
```

Only pairs whose failed RTL is rejected and whose repaired RTL passes
`iverilog`, `vvp`, and `yosys` are written to `train.sft.jsonl`.

## LLaMA-Factory registration

Register `train.sft.jsonl` in LLaMA-Factory `data/dataset_info.json`:

```json
"octoverilog_wire_repair": {
  "file_name": "/home/htt/OctoVerilog/datasets/repair/wire_in_always_block/train.sft.jsonl",
  "columns": {
    "system": "system",
    "prompt": "prompt",
    "response": "response"
  }
}
```

Copy `configs/codev_r1_wire_repair_lora.yaml` into the LLaMA-Factory examples
directory and start training with `llamafactory-cli train`.

If LLaMA-Factory is not installed, use the built-in PEFT trainer from a
dedicated environment. `--dry-run` loads only the tokenizer and reports whether
any records would be truncated.

```bash
octoverilog-train-repair-lora \
  --model /home/datasets/huggingface/hub/CodeV-R1-RL-Qwen-7B \
  --train-file datasets/repair/wire_in_always_block/train.sft.jsonl \
  --validation-file datasets/repair/wire_in_always_block/validation.sft.jsonl \
  --output-dir adapters/wire_in_always_block \
  --max-length 4096 \
  --dry-run
```

Remove `--dry-run` only after the report is acceptable. This trainer masks the
system and user tokens, so loss is computed only on the verified repaired RTL.

## Serve base model and repair expert together

```bash
vllm serve /home/datasets/huggingface/hub/CodeV-R1-RL-Qwen-7B \
  --served-model-name codev-r1 \
  --enable-lora \
  --lora-modules codev-r1-wire-in-always=/home/htt/OctoVerilog/adapters/wire_in_always_block
```

Set `OCTOVERILOG_EXPERT_REGISTRY` to the deployed registry JSON. The control
layer will use CodeV-R1 for initial generation and call the expert model only
after the error classifier selects `wire_in_always_block`.

## Paired held-out comparison

Use the test split produced before training. Both branches receive the same
specification, failed RTL, EDA feedback, temperature, and token budget. The
expert branch runs with strict routing, so an unavailable adapter cannot be
counted as an expert result.

```bash
octoverilog-repair-data evaluate-held-out \
  --dataset datasets/repair/wire_in_always_block/test.evaluation.jsonl \
  --model vllm-codev-r1 \
  --expert-registry configs/expert_loras.json \
  --temperature 0 \
  --output-dir runs/eval/wire_in_always_block
```

`summary.json` reports baseline accuracy, expert accuracy, and the absolute
accuracy gain. `paired_results.jsonl` keeps both generated repairs and complete
EDA evidence for every held-out sample.
