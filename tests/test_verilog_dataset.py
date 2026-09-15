import json

import pytest

from octotools.verilog.dataset import iter_dataset, normalize_record


def test_normalize_codev_record_layouts():
    description = normalize_record(
        {"task_id": "mux", "detail_description": "Build a mux."}, 1
    )
    fullprompt = normalize_record(
        {"task_id": "fsm", "fullprompt": "Build an FSM."}, 2
    )
    completion = normalize_record({"task_id": "alu", "prompt": "module alu("}, 3)
    assert description.specification == "Build a mux."
    assert fullprompt.task_id == "fsm"
    assert completion.specification == "module alu("


def test_iter_jsonl_dataset(tmp_path):
    path = tmp_path / "data.jsonl"
    rows = [
        {"task_id": "one", "question": "First"},
        {"task_id": "two", "description": "Second", "testbench": "module tb;"},
    ]
    path.write_text("\n".join(json.dumps(row) for row in rows), encoding="utf-8")
    records = list(iter_dataset(path))
    assert [record.task_id for record in records] == ["one", "two"]
    assert records[1].testbench == "module tb;"


def test_missing_specification_is_rejected():
    with pytest.raises(ValueError, match="specification"):
        normalize_record({"task_id": "bad"}, 1)
