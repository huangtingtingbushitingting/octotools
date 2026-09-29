"""OctoTools Agent control layer for closed-loop Verilog generation."""

from __future__ import annotations

import json
import time
import uuid
from pathlib import Path
from typing import Any

from octotools.models.executor import Executor
from octotools.models.initializer import Initializer
from octotools.models.memory import Memory
from octotools.models.planner import Planner
from octotools.solver import Solver

from .progress import PipelineEvent, ProgressCallback
from .training.collector import CandidateCollector
from .training.errors import classify_failure, classify_failure_details
from .training.ranking import rank_candidates
from .training.schema import CandidateRecord
from .error_taxonomy import ordered_categories
from .selector import select_best_candidate
from .verifier import VerificationGate


TOOLS = [
    "verilog_generator",
    "verilog_localizer",
    "verilog_rag",
    "verilog_repair",
    "verilog_expert_repair",
    "iverilog",
    "vvp",
    "yosys",
    "yosys_equivalence",
    "verilog_search",
]


class VerilogAgentPlanner(Planner):
    """强制定义闭环流程计划，明确顺序和“只所有必需工具成功才算成功，进行stop”"""

    def closed_loop_plan(self, *, has_testbench: bool, has_reference: bool) -> list[str]:
        plan = ["VerilogGeneratorTool", "IverilogTool"]
        if has_testbench:
            plan.append("VvpTool")
        plan.append("YosysTool")
        if has_reference:
            plan.append("YosysEquivalenceTool")
        plan.extend(["VerilogLocalizerTool", "VerilogRagTool", "VerilogRepairTool"])
        plan.append("STOP only when every required tool reports success; otherwise VerilogRepairTool and repeat")
        return plan


class VerilogAgentSolver(Solver):#Agent核心控制器
    """Use Solver/Planner/Executor/Memory with deterministic verification gates."""

    def __init__(
        self,
        model: str,
        attempts: int = 3,
        workspace_dir: str = "runs/agent-work",
        verbose: bool = True,
        candidates_per_round: int = 1,
        trace_file: str | None = None,
        expert_registry: str | None = None,
        strict_expert: bool = False,
    ):
        if candidates_per_round < 1:
            raise ValueError("candidates_per_round must be at least 1")
        initializer = Initializer(enabled_tools=TOOLS, model_string=model, verbose=verbose)
        planner = VerilogAgentPlanner(model, initializer.toolbox_metadata, initializer.available_tools, verbose)
        memory = Memory()
        executor = Executor(model, workspace_dir=workspace_dir, verbose=verbose)
        super().__init__(planner, memory, executor, output_types="direct", max_steps=attempts, workspace_dir=workspace_dir, verbose=verbose)
        self.model = model
        self.attempts = attempts
        self.candidates_per_round = candidates_per_round
        self.collector = CandidateCollector(trace_file)
        self.expert_registry = expert_registry
        self.strict_expert = strict_expert

    @staticmethod
    def _feedback(checks: dict[str, Any]) -> str:
        return json.dumps(checks, ensure_ascii=False, indent=2)[-12000:]

    @staticmethod
    def _passed(checks: dict[str, Any], *, has_testbench: bool, has_reference: bool) -> bool:
        return VerificationGate.assess(
            checks, has_testbench=has_testbench, has_reference=has_reference
        )["passed"]

    def solve_verilog(
        self,
        specification: str,
        testbench: str | None = None,
        *,
        reference_code: str | None = None,
        top_module: str = "TopModule",
        temperature: float = 0.2,
        max_tokens: int = 4096,
        task_id: str = "interactive",
        progress: ProgressCallback | None = None,
    ) -> dict[str, Any]:
        self.memory.clear()
        self.memory.set_query(specification)
        Path(self.workspace_dir).mkdir(parents=True, exist_ok=True)
        self.executor.set_workspace_dir(self.workspace_dir)
        plan = self.planner.closed_loop_plan(has_testbench=testbench is not None, has_reference=reference_code is not None)
        history: list[dict[str, Any]] = []
        candidate = ""
        feedback = ""
        error_category = "unclassified"
        route_family = "general_complex"
        parent_candidate_id: str | None = None
        run_id = uuid.uuid4().hex
        candidates_per_round = getattr(self, "candidates_per_round", 1)
        collector = getattr(self, "collector", CandidateCollector(None))
        expert_registry = getattr(self, "expert_registry", None)
        strict_expert = getattr(self, "strict_expert", False)
        step = 0
        started = time.monotonic()

        def emit(stage: str, message: str, attempt: int | None = None, **details):
            if progress:
                progress(PipelineEvent(stage, message, attempt, details))

        emit("start", f"Planner created mandatory plan: {' -> '.join(plan)}")
        for attempt in range(1, self.attempts + 1):
            round_candidates: list[dict[str, Any]] = []
            for candidate_index in range(1, candidates_per_round + 1):
                if attempt == 1:
                    generation_tool = "VerilogGeneratorTool"#生成候选verilog的工具
                elif expert_registry:
                    generation_tool = "VerilogExpertRepairTool"#进行专家修复的lora
                else:
                    generation_tool = "VerilogRepairTool"#进行普通修复的工具
                emit(
                    "generate",
                    f"Executor is calling {generation_tool} for candidate {candidate_index}/{candidates_per_round}.",
                    attempt,
                )
                kwargs = dict(
                    specification=specification,
                    top_module=top_module,
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
                if attempt > 1:#attempt=1表示处于verilog的生成阶段
                    try:
                        localized = self.executor.execute_tool(
                            "VerilogLocalizerTool",
                            specification=specification,
                            candidate_code=candidate,
                            verification_feedback=feedback,
                            top_module=top_module,
                            temperature=temperature,
                            max_tokens=min(max_tokens, 2048),
                        )#候选者测试失败调用定位
                    except Exception as error:
                        localized = {"success": False, "error": f"localizer unavailable: {error}"}
                    if localized.get("success"):
                        step += 1
                        self.memory.add_evidence(
                            step,
                            "VerilogLocalizerTool",
                            "Mark suspicious RTL statements before repair",
                            localized,
                        )
                    try:
                        rag = self.executor.execute_tool(
                            "VerilogRagTool",
                            specification=specification,
                            candidate_code=candidate,
                            error_category=error_category,
                            top_k=3,
                        )#候选测试失败之后检索错误分析/修正实例
                    except Exception as error:
                        rag = {"success": False, "error": f"RAG unavailable: {error}"}
                    if rag.get("success"):
                        step += 1
                        self.memory.add_evidence(
                            step,
                            "VerilogRagTool",
                            "Retrieve RTLerror-analysis correction examples",
                            rag,
                        )
                    diagnostic_feedback = (
                        feedback
                        + "\n\nTwo-stage localization result:\n"
                        + str(localized.get("localized_code") or localized.get("error") or "unavailable")
                        + "\n\nRetrieved correction examples:\n"
                        + str(rag.get("context") or rag.get("error") or "unavailable")
                    )#可以的RLT语句的位置+检索错误分析/修正示例
                    kwargs.update(
                        candidate_code=candidate,
                        verification_feedback=diagnostic_feedback,
                    )
                    if generation_tool == "VerilogExpertRepairTool":
                        kwargs.update(
                            error_category=error_category,
                            expert_family=route_family,
                            registry_path=expert_registry,
                            strict_expert=strict_expert,
                        )#候选测试失败之后调用修复工具
                generated = self.executor.execute_tool(generation_tool, **kwargs)
                step += 1
                self.memory.add_evidence(
                    step,
                    generation_tool,
                    f"Generate round {attempt} candidate {candidate_index}",
                    generated,
                )
                candidate_id = f"{run_id}:r{attempt:02d}c{candidate_index:02d}"
                current = str(generated.get("code") or "")
                checks: dict[str, Any] = {}
                passed = False

                if generated.get("success") and current:
                    emit(
                        "generated",
                        f"Candidate {candidate_index} contains {len(current)} characters.",
                        attempt,
                    )
                    stem = f"round_{attempt:02d}_candidate_{candidate_index:02d}"
                    compile_result = self.executor.execute_tool(
                        "IverilogTool",
                        source_code=current,#源码
                        top_module=top_module,#顶层模块
                        testbench=testbench,#测试平台
                        candidate_name=stem,
                    )#调用iverilog编译
                    checks["compile"] = compile_result
                    step += 1
                    self.memory.add_evidence(
                        step, "IverilogTool", "Compile candidate and testbench", compile_result
                    )

                    artifact = compile_result.get("artifact_path")
                    if testbench is not None and artifact:
                        simulation = self.executor.execute_tool(
                            "VvpTool", artifact_path=artifact
                        )#编译成功之后，如果有测试平台和编译Chanukah，调用vvotool进行仿真
                        checks["simulation"] = simulation#仿真结果记录
                        step += 1
                        self.memory.add_evidence(
                            step, "VvpTool", "Run self-checking testbench", simulation
                        )

                    synthesis = self.executor.execute_tool(
                        "YosysTool",
                        source_code=current,
                        top_module=top_module,
                        candidate_name=stem,
                    )#调用yosys综合检查
                    checks["synthesis"] = synthesis#yosys综合检查结果记录
                    step += 1
                    self.memory.add_evidence(
                        step,
                        "YosysTool",
                        "Synthesize and structurally check candidate",
                        synthesis,
                    )

                    if reference_code is not None:
                        equivalence = self.executor.execute_tool(
                            "YosysEquivalenceTool",
                            candidate_code=current,
                            reference_code=reference_code,
                            top_module=top_module,
                        )#只当提供reference_code时调用yosys_equivalence 进行等价性检查
                        checks["equivalence"] = equivalence#将等价结果写入
                        step += 1
                        self.memory.add_evidence(
                            step,
                            "YosysEquivalenceTool",
                            "Prove candidate equivalent to reference RTL",
                            equivalence,
                        )
                    passed = self._passed(
                        checks,
                        has_testbench=testbench is not None,
                        has_reference=reference_code is not None,
                    )
                else:
                    checks["generation"] = generated

                category = classify_failure(checks, current)
                classification = classify_failure_details(checks, current)
                route_categories = ordered_categories(classification.get("labels", []))
                candidate_family = route_categories[0] if route_categories else "general_complex"
                round_candidates.append(
                    {
                        "attempt": attempt,
                        "candidate_index": candidate_index,
                        "candidate_id": candidate_id,
                        "parent_candidate_id": parent_candidate_id,
                        "stage": "generation" if attempt == 1 else "repair",
                        "generation": generated,
                        "code": current,
                        "raw_response": generated.get("raw_response", ""),
                        "verification": checks,
                        "gate_passed": passed,
                        "error_category": category,
                        "classification": classification,
                        "expert_family": candidate_family,
                    }
                )#收集候选者的代码、验证结果、是否通过门控，错误类别，父亲候选的id，候选者所处的阶段，LLM的原始输出

            ranked = rank_candidates(
                round_candidates,
                has_testbench=testbench is not None,
                has_reference=reference_code is not None,
            )#根据是否有测试平台/参考代码，对候选打分并进行排序
            history.extend(ranked)
            for item in ranked:
                generated = item.get("generation") or {}
                collector.append(
                    CandidateRecord(
                        run_id=run_id,
                        task_id=task_id,
                        round_index=attempt,
                        candidate_index=int(item["candidate_index"]),
                        candidate_id=str(item["candidate_id"]),
                        parent_candidate_id=item.get("parent_candidate_id"),
                        stage=str(item["stage"]),
                        model_name=str(generated.get("model") or self.model),
                        model_input=str(generated.get("model_input") or ""),
                        raw_output=str(item.get("raw_response") or ""),
                        extracted_code=str(item.get("code") or ""),
                        usage=dict(generated.get("usage") or {}),
                        verification=item.get("verification") or {},
                        score=float(item["score"]),
                        rank=int(item["rank"]),
                        gate_passed=bool(item.get("gate_passed")),
                        selected=bool(item.get("selected")),
                        error_category=str(item.get("error_category") or "unclassified"),
                        metadata={
                            "specification": specification,
                            "top_module": top_module,
                            "expert_used": generated.get("expert_used", False),
                            "fallback_reason": generated.get("fallback_reason"),
                            "classification": item.get("classification", {}),
                            "expert_family": item.get("expert_family"),
                        },
                    )#记录候选者的详细信息，用于后期训练与分析
                )

            best = select_best_candidate(ranked, original_code=candidate)
            candidate = str(best.get("code") or "")
            parent_candidate_id = str(best["candidate_id"])
            error_category = str(best.get("error_category") or "unclassified")
            route_family = str(best.get("expert_family") or "general_complex")
            emit(
                "verified",
                f"Selected rank 1 candidate with score={best['score']} and gate_passed={best.get('gate_passed')}.",
                attempt,
                evidence=best.get("verification"),
                rankings=[
                    {"candidate_id": item["candidate_id"], "rank": item["rank"], "score": item["score"]}
                    for item in ranked
                ],
            )
            if best.get("gate_passed"):
                emit(
                    "complete",
                    f"Closed loop completed in {time.monotonic() - started:.2f}s.",
                    attempt,
                    verified=True,
                )
                return {
                    "code": candidate,
                    "verified": True,
                    "attempts": history,
                    "model": self.model,
                    "plan": plan,
                    "memory": self.memory.get_actions(),
                    "run_id": run_id,
                }
            feedback = self._feedback(best.get("verification") or best.get("generation") or {})
            if attempt < self.attempts:
                emit(
                    "retry",
                    f"Verifier rejected the selected candidate ({error_category}); Memory evidence is being sent to the repair tool.",
                    attempt,
                )

        emit("error", "No candidate passed every mandatory verification gate; delivery is blocked.")
        return {"code": "", "last_candidate": candidate, "verified": False, "attempts": history, "model": self.model, "plan": plan, "memory": self.memory.get_actions(), "run_id": run_id}
