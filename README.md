# OctoVerilog

OctoVerilog is a focused Verilog/SystemVerilog generation project built on the
OctoTools model-engine abstraction. It turns a natural-language RTL
specification or a JSONL benchmark into synthesizable code, optionally checks
the result with Icarus Verilog and Yosys, and feeds deterministic compiler
feedback into the next generation attempt.

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

Install Icarus Verilog for compile/simulation checks and Yosys for optional
synthesis checks. Generation works without either tool, but the result will be
marked unverified.

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

## Python API

```python
from octotools.verilog import VerilogPipeline

pipeline = VerilogPipeline.from_model("vllm-QiMeng-CodeV-R1", attempts=2)
result = pipeline.run("Implement a rising-edge D flip-flop named TopModule.")
print(result.code)
```

## Design boundaries

- No plan cache or APC dependency.
- No runtime dependency on CodeV-R1 source code.
- Generated text is treated as data and never executed through a shell.
- Functional correctness is only claimed after a supplied self-checking
  testbench passes; compile-only success is reported separately.
