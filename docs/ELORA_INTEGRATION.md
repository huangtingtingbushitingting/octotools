# ELORA integration boundary

## Current status

OctoVerilog's inference-time Agent loop is implemented. ELORA itself is not
installed: neither this repository nor the server contains an ELORA runtime,
and no public implementation was identified during the integration audit.

ELORA is a multi-LoRA **serving** design that jointly manages LoRA adapters and
their dependent KV-cache entries. It does not replace SFT or RL optimization
and must not be reported as an RL training accelerator without measurements of
the rollout-serving path.

## Existing CodeV-R1 insertion points

- SFT already exposes PEFT LoRA parameters in
  `verl/verl/trainer/config/sft_trainer.yaml` and constructs `LoraConfig` in
  `verl/verl/trainer/fsdp_sft_trainer.py`.
- The RL rollout engine contains vLLM LoRA configuration and request support in
  `verl/verl/third_party/vllm/`.
- The standalone vLLM 0.8.5 server supports multiple named adapters, but its
  normal LoRA manager is not ELORA's dependency-aware unified LoRA/KV cache.

## Intended adapter roles

Use one compatible base checkpoint and independently train/export adapters for:

1. `verilog-generator`: initial specification-to-RTL generation.
2. `verilog-repair`: compiler/simulation/equivalence-feedback repair.
3. `verilog-critic`: optional proposal ranking; it never overrides tool gates.

OctoVerilog selects these by served model name while retaining the same
mandatory Icarus, VVP, Yosys, and formal-equivalence gates.

## Conditions required before claiming ELORA deployment

1. Obtain or implement the ELORA cache manager and swapper against a pinned
   serving engine commit.
2. Maintain a dependency tree linking every resident LoRA with all reusable KV
   entries produced under that adapter.
3. Use a unified GPU-memory budget and measured swap cost model for both LoRA
   and KV nodes.
4. Prove eviction never leaves reusable KV entries whose required adapter is
   absent.
5. Benchmark TTFT, TPOT, throughput, cache hit rate, swap traffic, and peak load
   against the unmodified vLLM/SGLang baseline.
6. Run SFT and RL quality regression tests to show that serving changes do not
   alter rewards or generated RTL correctness.

Until all six conditions pass, configuration with `--enable-lora`,
`--max-loras`, and `--max-cpu-loras` is described as standard vLLM multi-LoRA,
not ELORA.
