from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from time import perf_counter

from hewn.completion import (
    CompletionPolicy,
    CompletionRequirement,
)
from hewn.context.models import ContextBundle
from hewn.models import FinalResponse, Message, Model
from hewn.telemetry import AgentEvent, AgentMetrics
from hewn.tools import (
    ToolCall,
    ToolExecutor,
    ToolRegistry,
)

CompletionPolicyFactory = Callable[
    [CompletionRequirement],
    CompletionPolicy,
]


def _default_completion_policy_factory(
    requirement: CompletionRequirement,
) -> CompletionPolicy:
    return CompletionPolicy(requirement=requirement)


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


def _build_initial_user_message(
    *,
    user_request: str,
    context: ContextBundle | None,
) -> str:
    if context is None or context.evidence_count == 0:
        return user_request

    formatted_context = context.format_for_model()

    return (
        f"{user_request}\n\n"
        "Relevant repository evidence follows. "
        "Use it as grounding, but verify with tools "
        "when necessary.\n\n"
        f"{formatted_context}"
    )


class AgentStagnationError(RuntimeError):
    def __init__(
        self,
        message: str,
        *,
        metrics: AgentMetrics,
    ) -> None:
        super().__init__(message)
        self.metrics = metrics


class AgentLimitError(RuntimeError):
    def __init__(
        self,
        message: str,
        *,
        metrics: AgentMetrics,
    ) -> None:
        super().__init__(message)
        self.metrics = metrics


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
    max_stagnant_turns: int = 3
    completion_policy_factory: CompletionPolicyFactory = (
        _default_completion_policy_factory
    )

    def run(
        self,
        user_request: str,
        *,
        completion_requirement: CompletionRequirement = (
            CompletionRequirement.NONE
        ),
        context: ContextBundle | None = None,
    ) -> AgentRunResult:
        started_at = perf_counter()

        completion_policy = self.completion_policy_factory(
            completion_requirement
        )

        consecutive_stagnant_turns = 0

        initial_user_message = _build_initial_user_message(
            user_request=user_request,
            context=context,
        )

        messages = [
            Message(
                role="user",
                content=initial_user_message,
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
                if not completion_policy.can_finish():
                    reason = completion_policy.rejection_reason()

                    metrics.events.append(
                        AgentEvent(
                            kind="completion_rejected",
                            detail=reason,
                        )
                    )

                    messages.append(
                        Message(
                            role="tool",
                            content=reason,
                        )
                    )

                    consecutive_stagnant_turns += 1

                    if (
                        consecutive_stagnant_turns
                        >= self.max_stagnant_turns
                    ):
                        metrics.events.append(
                            AgentEvent(
                                kind="stagnation_detected",
                                detail=(
                                    f"{consecutive_stagnant_turns} "
                                    "consecutive non-progressing turns"
                                ),
                            )
                        )

                        metrics.wall_time_seconds = (
                            perf_counter() - started_at
                        )

                        raise AgentStagnationError(
                            (
                                "Agent stagnated after "
                                f"{consecutive_stagnant_turns} "
                                "consecutive non-progressing turns"
                            ),
                            metrics=metrics,
                        )

                    continue

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

                completion_policy.record_tool_attempt(
                    call=response,
                    result=result,
                )

                consecutive_stagnant_turns = 0

                if response.name == "run_check":
                    completion_policy.record_check(
                        passed=result.ok
                    )

                if (
                    response.name == "replace_text"
                    and result.ok
                ):
                    completion_policy.record_repository_change()

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

        metrics.wall_time_seconds = (
            perf_counter() - started_at
        )

        raise AgentLimitError(
            (
                "Agent exceeded maximum turns: "
                f"{self.max_turns}"
            ),
            metrics=metrics,
        )