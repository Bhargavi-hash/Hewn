from __future__ import annotations

from hewn.agent import (
    Agent,
    _build_initial_user_message,
    _format_tool_observation,
)
from hewn.context.models import ContextBundle
from hewn.model_protocol import serialize_model_response
from hewn.models import Message
from hewn.tools import ToolCall


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
            content=serialize_model_response(call),
        ),
        Message(
            role="tool",
            content=observation,
        ),
    ]

    return messages, observation
