from __future__ import annotations

from dataclasses import dataclass
from time import perf_counter

from hewn.models import FinalResponse, Message, Model
from hewn.telemetry import AgentMetrics
from hewn.tools import ToolCall, ToolExecutor, ToolRegistry


class AgentLimitError(RuntimeError):
    """The agent exceeded its allowed number of model turns."""

@dataclass(frozen=True)
class AgentRunResult:
    text: str
    metrics: AgentMetrics

@dataclass
class Agent:
    model: Model
    registry: ToolRegistry
    executor: ToolExecutor
    max_turns: int = 20

    def run(self, user_request: str) -> AgentRunResult:
        started_at = perf_counter()
        messages = [
            Message(
                role="user",
                content=user_request,
            )
        ]

        tools = self.registry.definitions()
        metrics = AgentMetrics()

        for _ in range(self.max_turns):
            metrics.model_calls += 1
            response = self.model.respond(
                messages=messages,
                tools=tools,
            )

            if isinstance(response, FinalResponse):
                metrics.wall_time_seconds = perf_counter() - started_at
                return AgentRunResult(
                    text=response.text,
                    metrics=metrics,
                )

            if isinstance(response, ToolCall):
                metrics.tool_calls += 1
                result = self.executor.execute(response)

                if result.ok:
                    metrics.successful_tool_calls += 1
                else:
                    metrics.failed_tool_calls += 1

                messages.append(
                    Message(
                        role="assistant",
                        content=(
                            f"Tool call: {response.name} "
                            f"{response.arguments}"
                        ),
                    )
                )

                messages.append(
                    Message(
                        role="tool",
                        content=(
                            result.output
                            if result.ok
                            else f"Error: {result.error}"
                        )
                        or "",
                    )
                )

                continue

            raise TypeError(
                f"Unsupported model response: {type(response).__name__}"
            )

        raise AgentLimitError(
            f"Agent exceeded maximum turns: {self.max_turns}"
        )