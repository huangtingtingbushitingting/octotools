"""Stable JSON schemas for repair traces and supervised repair pairs."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass
class CandidateRecord:#候选者数据结构，记录候选者的完整生命周期元数据
    run_id: str#本次运行的唯一标识
    task_id: str#任务ID
    round_index: int#表示第几轮生成/修复
    candidate_index: int#本轮中的第几位候选者
    candidate_id: str#候选者的唯一标识
    stage: str#候选者所处的阶段
    model_name: str
    model_input: str#传给模型的完整提示词
    raw_output: str
    extracted_code: str
    verification: dict[str, Any]#各个阶段的验证结果
    score: float
    rank: int#候选者在本轮的排序
    gate_passed: bool#是否通过所有的强制验证门控
    selected: bool#是否被选中作为最后的交付候选者
    error_category: str#失败的错误类别
    parent_candidate_id: str | None = None#当前候选者的父类，修复之前的候选者ID
    usage: dict[str, int | None] = field(default_factory=dict)#token使用量
    metadata: dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    schema_version: int = 1

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class RepairPair:#修复对，记录一次从从错误代码+错误反馈到修复后代码的完整映射，用于SFT
    pair_id: str
    task_id: str
    error_category: str
    system: str#用于SFT的系统提示词
    prompt: str#用户提示词
    response: str#修复之后的原始输出
    specification: str
    incorrect_code: str
    repaired_code: str
    error_feedback: str#验证工具给出的失败候选者的反馈
    source_model: str
    repair_model: str#执行修复的模型
    source_candidate_id: str#等待修复代码的候选ID
    repaired_candidate_id: str#已经修复号之后的候选ID
    before_verification: dict[str, Any]#修复前的验证结果
    after_verification: dict[str, Any]#修复后的验证结果
    provenance: dict[str, Any] = field(default_factory=dict)#候选者和反馈信息来源
    schema_version: int = 1

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_sft_dict(self) -> dict[str, str]:
        return {
            "system": self.system,
            "prompt": self.prompt,
            "response": self.response,
        }
