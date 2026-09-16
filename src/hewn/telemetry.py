from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class AgentEvent:
    kind: str
    detail: str


@dataclass
class AgentMetrics:
    model_calls: int = 0
    tool_calls: int = 0
    successful_tool_calls: int = 0
    failed_tool_calls: int = 0
    wall_time_seconds: float = 0.0
    events: list[AgentEvent] = field(default_factory=list)