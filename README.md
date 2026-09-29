# OctoVerilog

OctoVerilog is a Verilog/SystemVerilog Agent built on the complete OctoTools
control chain: `Solver -> Planner -> Executor -> Tool -> Memory`. It turns a
natural-language RTL specification or JSONL benchmark into synthesizable code
and enforces `generation -> verification -> repair` before delivery.

The dataset reader supports the common record layouts used by CodeV-R1's
VerilogEval and RTLLM benchmarks (`detail_description`, `fullprompt`, `prompt`,
and related fields), but this repository does not import or depend on a local
CodeV-R1 checkout.

## Installation

```bash
conda create -n octoverilog python=3.10
conda activate octoverilog
pip install -e .
```

Install Icarus Verilog and Yosys. They are mandatory Agent tools: missing tools
block delivery instead of silently returning an unverified design.

Configure the model provider as required by OctoTools. For a CodeV-compatible
model served through vLLM's OpenAI API, start the server separately and use the
`vllm-` model prefix expected by OctoTools.

The endpoint defaults to `http://localhost:8888/v1`. Set `VLLM_BASE_URL` and,
when required, `VLLM_API_KEY` to connect to another OpenAI-compatible endpoint.

## Generate one module

```bash
octoverilog generate \
  --model vllm-QiMeng-CodeV-R1 \
  --spec "Create a 2-to-1 multiplexer named TopModule." \
  --output build/TopModule.sv
```

During generation, OctoVerilog prints an OctoTools-style trace showing the
feedback retry, and final status. These messages now describe real Planner,
Executor, Tool, and Memory actions rather than a look-alike display. Pass
`--quiet` when machine-readable output without the trace is preferred.

## Interactive natural-language generation

Start an interactive session when you want to describe one circuit after
another in natural language:

```bash
octoverilog chat \
  --model vllm-codev-r1 \
  --attempts 3 \
  --max-tokens 16384 \
  --output-dir runs/interactive
```

Then enter requests directly at the prompt:

```text
octoverilog> 设计一个带同步复位的 8 位递增计数器，模块名为 TopModule。

==> 🔍 Planner created mandatory plan: VerilogGeneratorTool -> IverilogTool -> YosysTool -> repair or STOP
==> 🐙 [Attempt 1] Executor is calling VerilogGeneratorTool.
==> 📝 [Attempt 1] Extracted Verilog code.
==> ✅ [Attempt 1] Mandatory verification gate passed=True.
==> 🎯 Closed loop completed.
==> 💾 Saved Verilog: .../runs/interactive/design_001.sv
```

Use `/module NAME` to change the required top module for later requests,
`/help` to show commands, and `/quit` to leave the session. Each request saves
both `design_NNN.sv` and `design_NNN.report.json`; the report retains raw model
responses, the mandatory plan, Agent Memory, verification evidence, and retry
history.

To compile against a self-checking testbench and retry with compiler feedback:

```bash
octoverilog generate \
  --model vllm-QiMeng-CodeV-R1 \
  --spec-file problem.txt \
  --testbench tb.sv \
  --attempts 3 \
  --output build/TopModule.sv \
  --report build/report.json
```

When golden RTL is available, add formal equivalence to the mandatory gate:

```bash
octoverilog generate \
  --model vllm-codev-r1 \
  --spec-file problem.txt \
  --reference-file golden.sv \
  --attempts 3 \
  --output build/TopModule.sv \
  --report build/report.json
```

Without reference RTL, OctoVerilog reports compile/simulation/synthesis
verification and does not mislabel those checks as formal equivalence.

## Run a JSONL dataset

```bash
octoverilog batch \
  --model vllm-QiMeng-CodeV-R1 \
  --dataset path/to/VerilogDescription_Human.jsonl \
  --output-dir runs/verilogeval \
  --limit 10
```

Each batch item produces a `.sv` file. `results.jsonl` records its source task
ID, selected candidate, attempts, and verification evidence. Dataset files are
read-only; answers are always written under `--output-dir`.

## Repair data and category experts

Use `--candidates-per-round N` to generate, verify, and rank multiple candidates
at every round. OctoVerilog appends every model input/output, model name, token
usage, EDA evidence, category, score, rank, and parent repair link to
`candidates.jsonl` (or `--trace-file`). Only a failed candidate followed by a
child that passes every mandatory gate can become a repair-training pair.

```bash
octoverilog batch \
  --model vllm-codev-r1 \
  --dataset datasets/tasks.jsonl \
  --attempts 3 \
  --candidates-per-round 3 \
  --trace-file runs/repair-collection/candidates.jsonl \
  --output-dir runs/repair-collection

octoverilog-repair-data from-traces \
  --trace runs/repair-collection/candidates.jsonl \
  --output-dir datasets/repair/from-runs
```

Category LoRAs are repair-only tools. The initial candidate always comes from
the configured CodeV-R1 model. After EDA failure classification, the control
layer consults `--expert-registry` and invokes `VerilogExpertRepairTool`; it
then repeats the same compile, simulation, synthesis, and optional equivalence
gate. See `docs/repair_lora.md` for the verified public-data conversion and
LLaMA-Factory configuration.

Each failed repair round also runs `VerilogLocalizerTool` and
`VerilogRagTool`. The localizer marks suspicious RTL statements from EDA
feedback; the RAG tool retrieves similar examples from the deployed
RTLerror-analysis knowledge base. Both outputs are appended to the repair
prompt and recorded in Agent Memory. Plan caching is not used.

## Python API

```python
from octotools.verilog import VerilogPipeline

pipeline = VerilogPipeline.from_model("vllm-QiMeng-CodeV-R1", attempts=2)
result = pipeline.run("Implement a rising-edge D flip-flop named TopModule.")
print(result.code)
```

## Design boundaries

- Plans and LLM responses are never cached or reused. Per-run workspaces only
  hold tool artifacts such as `.sv` and `.vvp` files.
- `IverilogTool`, `VvpTool`, `YosysTool`, and `YosysEquivalenceTool` run fixed
  subprocess argument lists with no model-generated shell command.
- `VerilogGeneratorTool`, `VerilogRepairTool`, `VerilogExpertRepairTool`, and `VerilogSearchTool` are
  registered in the same OctoTools toolbox.
- No runtime dependency on CodeV-R1 source code.
- Generated text is treated as data and never executed through a shell.
- A failed mandatory check returns no deliverable `.sv`; the last rejected
  candidate remains in the JSON report for diagnosis.

ELORA integration status and the required training/serving boundaries are
documented in `docs/ELORA_INTEGRATION.md`.
