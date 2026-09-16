from __future__ import annotations

from dataclasses import dataclass
from time import perf_counter

from hewn.models import FinalResponse, Message, Model
from hewn.telemetry import AgentEvent, AgentMetrics
from hewn.tools import ToolCall, ToolExecutor, ToolRegistry


def _format_tool_observation(
    *,
    ok: bool,
    output: str | None,
    error: str | None,
) -> str:
    if ok:
        return output or ""

    parts = []

    if error:
        parts.append(f"Error: {error}")

    if output:
        parts.append(output)

    return "\n".join(parts)


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

            metrics.events.append(
                AgentEvent(
                    kind="model_response",
                    detail=repr(response),
                )
            )

            if isinstance(response, FinalResponse):
                metrics.wall_time_seconds = (
                    perf_counter() - started_at
                )

                return AgentRunResult(
                    text=response.text,
                    metrics=metrics,
                )

            if isinstance(response, ToolCall):
                metrics.tool_calls += 1

                result = self.executor.execute(response)

                observation = _format_tool_observation(
                    ok=result.ok,
                    output=result.output,
                    error=result.error,
                )

                metrics.events.append(
                    AgentEvent(
                        kind="tool_result",
                        detail=observation,
                    )
                )

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
                        content=observation,
                    )
                )

                continue

            raise TypeError(
                "Unsupported model response: "
                f"{type(response).__name__}"
            )

        raise AgentLimitError(
            f"Agent exceeded maximum turns: {self.max_turns}"
        )