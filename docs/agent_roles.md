# OctoVerilog Agent roles and repair experts

## Runtime roles

| Role | Implementation | Responsibility |
| --- | --- | --- |
| Solver | `octotools/verilog/agent.py` | Owns the complete generate/verify/repair loop and delivery stop condition. |
| Planner | `VerilogAgentPlanner.closed_loop_plan` | Defines the mandatory generator, EDA, localization, RAG and repair stages. |
| Executor | `octotools/models/executor.py` | Loads and executes one registered tool with a run workspace. |
| Tool | `octotools/tools/*/tool.py` | Performs generation, EDA, retrieval, localization or repair. |
| Verifier | `octotools/verilog/verifier.py` | `VerificationGate.assess` aggregates compile, simulation, synthesis and equivalence gates. |
| Memory | `octotools/models/memory.py` | Stores every tool result and feedback item for the current run. |
| Generator | `verilog_generator` | Produces the initial RTL from the natural-language specification. |
| Localizer | `verilog_localizer` | Marks suspicious statements from EDA evidence before repair. |
| RAG | `verilog_rag` | Retrieves similar RTL correction examples from the RTLerror-analysis knowledge base. |
| Repair | `verilog_repair` | Generates a corrected candidate from specification, failed RTL and feedback. |
| Expert LoRA | `verilog_expert_repair` | Routes the failure to a category-specific repair adapter. |

## Role sequence diagrams

Each role has a standalone Mermaid sequence diagram in `docs/roles/`:

| Role | Diagram |
| --- | --- |
| Solver | `docs/roles/solver/README.md` |
| Planner | `docs/roles/planner/README.md` |
| Executor | `docs/roles/executor/README.md` |
| Tool | `docs/roles/tool/README.md` |
| Verifier | `docs/roles/verifier/README.md` |
| Memory | `docs/roles/memory/README.md` |
| Generator | `docs/roles/generator/README.md` |
| Localizer | `docs/roles/localizer/README.md` |
| RAG | `docs/roles/rag/README.md` |
| Repair | `docs/roles/repair/README.md` |
| Expert LoRA | `docs/roles/expert_lora/README.md` |
| Error Classifier | `docs/roles/error_classifier/README.md` |
| Error Order Processor | `docs/roles/order_processor/README.md` |
| Final Selector | `docs/roles/final_selector/README.md` |

## Expert families

* **Lora1 / structural**: wire/reg/logic misuse, undefined or duplicate signals,
  module/port errors, generate/for mistakes, out-of-range selections, incomplete
  RTL, compile/synthesis errors, illegal assignments and syntax/format errors.
* **Lora2 / temporal_fsm**: reset polarity and sync/async reset, blocking versus
  nonblocking assignment, latency and edge errors, state encoding/transitions,
  Moore/Mealy output errors, counters, LFSR and handshake sequencing.
* **Lora3 / numeric_vector**: width, signedness, extension, truncation, overflow,
  carry, LSB/MSB, shifts, slices, case/casez/casex and vector arithmetic.
* **Lora4 / general_complex**: multiple simultaneous errors, long-specification
  omissions, broad functional deviations, or a failed specialist repair.

`error_taxonomy.py` returns multi-label scores, top-2 candidates and a low-
confidence rejection flag. `ordered_categories()` repairs structural issues
first, then temporal/FSM or numeric/vector issues, and finally the general expert.

## Training data

Training records contain the specification, failed RTL, EDA logs, first failing
cycle or waveform summary when available, labels, repaired RTL and final gate
results. `training/inject_errors.py` creates directional structural, temporal/FSM
and numeric/vector mutations from known-good RTL. A sample must pass before
injection and fail after injection before it is admitted to a LoRA dataset.

The intended mixture is 50% real failed candidates, 40% directional injections,
and 10% mixed-error or capability-preservation samples. The EDA gate, rather
than the injector alone, decides whether a mutation is a valid training sample.
