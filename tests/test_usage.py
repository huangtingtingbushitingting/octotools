from octotools.research.usage import (
    UsageLedger,
    collect_usage,
    instrument_engine,
)


class EchoEngine:
    def __call__(self, content, **kwargs):
        return f"echo: {content}"

    def generate(self, content, **kwargs):
        return f"generated: {content}"


def test_instrumented_engine_records_usage_by_component():
    ledger = UsageLedger()
    engine = instrument_engine(
        EchoEngine(),
        component="planner",
        model="test-model",
    )

    with collect_usage(ledger):
        assert engine("hello") == "echo: hello"
        assert engine.generate("world") == "generated: world"

    usage = ledger.snapshot()
    assert usage["llm_calls"] == 2
    assert usage["total_tokens"] > 0
    assert usage["token_source"] == "estimated_from_text"
    assert usage["by_component"]["planner"]["calls"] == 2


def test_calls_outside_collection_are_not_retained():
    engine = instrument_engine(
        EchoEngine(),
        component="planner",
        model="test-model",
    )
    engine("not recorded")

    ledger = UsageLedger()
    with collect_usage(ledger):
        pass

    assert ledger.snapshot()["llm_calls"] == 0


def test_vllm_prefix_wins_when_served_model_name_contains_gpt(monkeypatch):
    import sys
    import types

    from octotools.engine.factory import create_llm_engine

    captured = {}

    class FakeVLLM(EchoEngine):
        def __init__(self, model_string, **kwargs):
            captured["model"] = model_string
            captured["kwargs"] = kwargs

    fake_module = types.ModuleType("octotools.engine.vllm")
    fake_module.ChatVLLM = FakeVLLM
    monkeypatch.setitem(sys.modules, "octotools.engine.vllm", fake_module)
    engine = create_llm_engine(
        "vllm-openai/gpt-oss-20b",
        is_multimodal=False,
    )

    assert engine("hello") == "echo: hello"
    assert captured["model"] == "openai/gpt-oss-20b"
