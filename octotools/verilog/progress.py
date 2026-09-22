"""Human-readable progress events for Verilog generation workflows."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable


@dataclass(frozen=True)
class PipelineEvent:
    """A single observable step emitted by :class:`VerilogPipeline`."""

    stage: str
    message: str
    attempt: int | None = None
    details: dict[str, Any] = field(default_factory=dict)


ProgressCallback = Callable[[PipelineEvent], None]


class ConsoleProgress:
    """Render pipeline events in the concise, step-based OctoTools style."""

    ICONS = {
        "start": "🔍",
        "generate": "🐙",
        "generated": "📝",
        "verify": "🛠️",
        "verified": "✅",
        "retry": "🔁",
        "error": "🚫",
        "complete": "🎯",
    }

    def __init__(self, *, enabled: bool = True) -> None:
        self.enabled = enabled

    def __call__(self, event: PipelineEvent) -> None:
        if not self.enabled:
            return
        icon = self.ICONS.get(event.stage, "•")
        timestamp = datetime.now().strftime("%H:%M:%S")
        attempt = f" [Attempt {event.attempt}]" if event.attempt is not None else ""
        print(f"\n==> {icon} {timestamp}{attempt} {event.message}", flush=True)
