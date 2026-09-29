"""Append-only JSONL collection for every generated repair candidate."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Iterable

from .schema import CandidateRecord


class CandidateCollector:#追啊候选者修复记录与轨迹
    def __init__(self, path: str | Path | None) -> None:#追加候选者完整生命周期
        self.path = Path(path).expanduser().resolve() if path else None

    def append(self, record: CandidateRecord | dict[str, Any]) -> None:
        if self.path is None:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        value = record.to_dict() if isinstance(record, CandidateRecord) else record
        with self.path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(value, ensure_ascii=False) + "\n")
            stream.flush()
            os.fsync(stream.fileno())


def read_jsonl(path: str | Path) -> list[dict[str, Any]]:#读取候选者的使用记录与轨迹
    rows: list[dict[str, Any]] = []
    with Path(path).open("r", encoding="utf-8-sig") as stream:
        for line_number, line in enumerate(stream, start=1):
            if not line.strip():
                continue
            value = json.loads(line)
            if not isinstance(value, dict):
                raise ValueError(f"line {line_number} is not a JSON object")
            rows.append(value)
    return rows


def write_jsonl(path: str | Path, rows: Iterable[dict[str, Any]]) -> None:#对文件进行覆盖式批量写入
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8") as stream:
        for row in rows:
            stream.write(json.dumps(row, ensure_ascii=False) + "\n")
