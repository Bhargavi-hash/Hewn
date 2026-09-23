from __future__ import annotations

from dataclasses import dataclass

from hewn.agent import (
    Agent,
    AgentRunResult,
    _build_initial_user_message,
    _format_tool_observation,
)
from hewn.completion import CompletionRequirement
from hewn.context.models import ContextBundle
from hewn.models import Message
from hewn.tools import ToolCall


@dataclass(frozen=True, slots=True)
class BootstrapResult:
    run_result: AgentRunResult
    tool_name: str
    observation: str


def run_with_repository_map_bootstrap(
    agent: Agent,
    user_request: str,
    *,
    completion_requirement: CompletionRequirement,
    context: ContextBundle,
) -> BootstrapResult:
    call = ToolCall(
        name="repository_map",
        arguments={},
    )

    result = agent.executor.execute(call)

    if not result.ok:
        raise RuntimeError(
            "Controller repository-map bootstrap failed: "
            f"{result.error or result.output or 'unknown error'}"
        )

    observation = _format_tool_observation(
        ok=result.ok,
        output=result.output,
        error=result.error,
    )

    initial_user_message = _build_initial_user_message(
        user_request=user_request,
        context=context,
    )

    messages = [
        Message(
            role="user",
            content=initial_user_message,
        ),
        Message(
            role="assistant",
            content=(
                "Controller bootstrap tool call: "
                f"{call.name} {call.arguments}"
            ),
        ),
        Message(
            role="tool",
            content=observation,
        ),
    ]

    run_result = agent.run_messages(
        messages,
        completion_requirement=completion_requirement,
    )

    return BootstrapResult(
        run_result=run_result,
        tool_name=call.name,
        observation=observation,
    )

def build_repository_map_bootstrap(
    agent: Agent,
    user_request: str,
    *,
    context: ContextBundle,
) -> tuple[list[Message], str]:
    call = ToolCall(
        name="repository_map",
        arguments={},
    )

    result = agent.executor.execute(call)

    if not result.ok:
        raise RuntimeError(
            "Controller repository-map bootstrap failed: "
            f"{result.error or result.output or 'unknown error'}"
        )

    observation = _format_tool_observation(
        ok=result.ok,
        output=result.output,
        error=result.error,
    )

    initial_user_message = _build_initial_user_message(
        user_request=user_request,
        context=context,
    )

    messages = [
        Message(
            role="user",
            content=initial_user_message,
        ),
        Message(
            role="assistant",
            content=(
                "Controller bootstrap tool call: "
                f"{call.name} {call.arguments}"
            ),
        ),
        Message(
            role="tool",
            content=observation,
        ),
    ]

    return messages, observation