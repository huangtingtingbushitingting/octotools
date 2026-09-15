"""Read CodeV-R1-style Verilog benchmark records without external imports."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator


@dataclass(frozen=True)
class DatasetRecord:
    task_id: str
    specification: str
    testbench: str | None = None
    reference_code: str | None = None
    raw: dict[str, Any] | None = None


_SPEC_FIELDS = (
    "detail_description",
    "fullprompt",
    "instruction",
    "question",
    "description",
    "specification",
    "prompt",
)
_TESTBENCH_FIELDS = ("testbench", "testbench_code", "tb", "test")
_REFERENCE_FIELDS = ("canonical_solution", "golden_code", "reference_code", "solution")


def _first_text(record: dict[str, Any], fields: tuple[str, ...]) -> str | None:
    for field in fields:
        value = record.get(field)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def normalize_record(record: dict[str, Any], index: int) -> DatasetRecord:
    """Normalize common VerilogEval, RTLLM, and CodeV-R1 JSON layouts."""
    specification = _first_text(record, _SPEC_FIELDS)
    if specification is None:
        raise ValueError(f"record {index} has no supported specification field")
    task_id = str(
        record.get("task_id")
        or record.get("id")
        or record.get("name")
        or f"task_{index:05d}"
    )
    return DatasetRecord(
        task_id=task_id,
        specification=specification,
        testbench=_first_text(record, _TESTBENCH_FIELDS),
        reference_code=_first_text(record, _REFERENCE_FIELDS),
        raw=record,
    )


def iter_dataset(path: str | Path) -> Iterator[DatasetRecord]:
    """Yield normalized records from JSONL or a JSON array/object file."""
    dataset_path = Path(path)
    if not dataset_path.is_file():
        raise FileNotFoundError(f"dataset does not exist: {dataset_path}")

    if dataset_path.suffix.lower() == ".jsonl":
        with dataset_path.open("r", encoding="utf-8-sig") as stream:
            for line_number, line in enumerate(stream, start=1):
                if not line.strip():
                    continue
                value = json.loads(line)
                if not isinstance(value, dict):
                    raise ValueError(f"line {line_number} is not a JSON object")
                yield normalize_record(value, line_number)
        return

    value = json.loads(dataset_path.read_text(encoding="utf-8-sig"))
    records = value if isinstance(value, list) else value.get("data", [value])
    if not isinstance(records, list):
        raise ValueError("JSON dataset must be a list, object, or object with data list")
    for index, record in enumerate(records, start=1):
        if not isinstance(record, dict):
            raise ValueError(f"record {index} is not a JSON object")
        yield normalize_record(record, index)
