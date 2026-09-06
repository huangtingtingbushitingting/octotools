from __future__ import annotations

import json
import math
import time
from contextlib import contextmanager
from contextvars import ContextVar, Token
from dataclasses import asdict, dataclass, field
from threading import Lock
from typing import Any, Iterator


def _serialize(value: Any) -> str:
    if isinstance(value, str):
        return value
    try:
        return json.dumps(value, ensure_ascii=False, default=str)
    except (TypeError, ValueError):
        return str(value)


def estimate_tokens(value: Any) -> int:
    """Provider-independent approximation; never reported as exact usage."""
    text = _serialize(value)
    if not text:
        return 0
    ascii_count = sum(ord(character) < 128 for character in text)
    non_ascii_count = len(text) - ascii_count
    return max(1, math.ceil(ascii_count / 4 + non_ascii_count / 1.5))


@dataclass(frozen=True)
class LLMCallRecord:
    component: str
    model: str
    duration_seconds: float
    input_tokens: int
    output_tokens: int
    token_source: str = "estimated_from_text"
    error: str | None = None


@dataclass
class UsageLedger:
    calls: list[LLMCallRecord] = field(default_factory=list)
    _lock: Lock = field(default_factory=Lock, repr=False)

    def record(self, call: LLMCallRecord) -> None:
        with self._lock:
            self.calls.append(call)

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            calls = list(self.calls)
        by_component: dict[str, dict[str, Any]] = {}
        for call in calls:
            component = by_component.setdefault(
                call.component,
                {
                    "calls": 0,
                    "input_tokens": 0,
                    "output_tokens": 0,
                    "duration_seconds": 0.0,
                    "errors": 0,
                },
            )
            component["calls"] += 1
            component["input_tokens"] += call.input_tokens
            component["output_tokens"] += call.output_tokens
            component["duration_seconds"] += call.duration_seconds
            component["errors"] += int(call.error is not None)

        for component in by_component.values():
            component["duration_seconds"] = round(
                component["duration_seconds"],
                6,
            )

        return {
            "llm_calls": len(calls),
            "input_tokens": sum(call.input_tokens for call in calls),
            "output_tokens": sum(call.output_tokens for call in calls),
            "total_tokens": sum(
                call.input_tokens + call.output_tokens for call in calls
            ),
            "duration_seconds": round(
                sum(call.duration_seconds for call in calls),
                6,
            ),
            "token_source": "estimated_from_text",
            "by_component": by_component,
            "calls": [asdict(call) for call in calls],
        }


_ACTIVE_LEDGER: ContextVar[UsageLedger | None] = ContextVar(
    "octotools_usage_ledger",
    default=None,
)


@contextmanager
def collect_usage(ledger: UsageLedger | None = None) -> Iterator[UsageLedger]:
    active = ledger or UsageLedger()
    token: Token[UsageLedger | None] = _ACTIVE_LEDGER.set(active)
    try:
        yield active
    finally:
        _ACTIVE_LEDGER.reset(token)


class InstrumentedEngine:
    """Transparent engine proxy that records provider-independent usage."""

    def __init__(self, engine: Any, *, component: str, model: str) -> None:
        self._engine = engine
        self._component = component
        self._model = model

    def __getattr__(self, name: str) -> Any:
        return getattr(self._engine, name)

    def __call__(self, content: Any, **kwargs: Any) -> Any:
        return self._invoke(self._engine, content, **kwargs)

    def generate(self, content: Any, **kwargs: Any) -> Any:
        return self._invoke(self._engine.generate, content, **kwargs)

    def _invoke(self, callable_engine: Any, content: Any, **kwargs: Any) -> Any:
        started_at = time.monotonic()
        output: Any = None
        error: str | None = None
        try:
            output = callable_engine(content, **kwargs)
            return output
        except Exception as exception:
            error = f"{type(exception).__name__}: {exception}"
            raise
        finally:
            ledger = _ACTIVE_LEDGER.get()
            if ledger is not None:
                ledger.record(
                    LLMCallRecord(
                        component=self._component,
                        model=self._model,
                        duration_seconds=round(
                            time.monotonic() - started_at,
                            6,
                        ),
                        input_tokens=estimate_tokens(
                            {
                                "content": content,
                                "system_prompt": kwargs.get("system_prompt"),
                            }
                        ),
                        output_tokens=estimate_tokens(output),
                        error=error,
                    )
                )


def instrument_engine(
    engine: Any,
    *,
    component: str,
    model: str,
) -> InstrumentedEngine:
    if isinstance(engine, InstrumentedEngine):
        return engine
    return InstrumentedEngine(engine, component=component, model=model)
