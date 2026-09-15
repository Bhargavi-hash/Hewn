from __future__ import annotations

from dataclasses import dataclass


@dataclass
class AgentMetrics:
    model_calls: int = 0
    tool_calls: int = 0
    successful_tool_calls: int = 0
    failed_tool_calls: int = 0
    wall_time_seconds: float = 0.0

    