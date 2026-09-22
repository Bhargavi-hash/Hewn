from __future__ import annotations

from pathlib import Path

import pytest
from evaluate_feedback_representation import (
    MUTATION_FEEDBACK,
    coherent_completion_rejection_formatter,
)

from hewn.agent import Agent, AgentStagnationError
from hewn.builtin_tools import make_builtin_tool_registry
from hewn.completion import CompletionRequirement
from hewn.models import FinalResponse, Message, ModelResponse
from hewn.tools import ToolDefinition, ToolExecutor
from hewn.workspace import Workspace


class RecordingScriptedModel:
    def __init__(
        self,
        responses: list[ModelResponse],
    ) -> None:
        self.responses = responses
        self.index = 0
        self.received_messages: list[list[Message]] = []

    def respond(
        self,
        messages: list[Message],
        tools: list[ToolDefinition],
    ) -> ModelResponse:
        del tools

        self.received_messages.append(list(messages))

        response = self.responses[self.index]
        self.index += 1
        return response


def test_agent_next_invocation_sees_coherent_completion_history(
    tmp_path: Path,
) -> None:
    model = RecordingScriptedModel(
        responses=[
            FinalResponse(text="premature completion"),
            FinalResponse(text="still premature"),
            FinalResponse(text="still premature"),
        ]
    )

    registry = make_builtin_tool_registry(
        Workspace(tmp_path)
    )

    agent = Agent(
        model=model,
        registry=registry,
        executor=ToolExecutor(registry),
        completion_rejection_formatter=(
            coherent_completion_rejection_formatter
        ),
    )

    with pytest.raises(AgentStagnationError):
        agent.run(
            "Change the repository.",
            completion_requirement=CompletionRequirement.VERIFIED,
        )

    assert len(model.received_messages) == 3

    second_invocation = model.received_messages[1]

    assert second_invocation[0] == Message(
        role="user",
        content="Change the repository.",
    )

    assert second_invocation[1] == Message(
        role="assistant",
        content=(
            '{"type":"final",'
            '"text":"premature completion"}'
        ),
    )

    assert second_invocation[2].role == "user"
    assert second_invocation[2].content.startswith(
        "Controller feedback: "
    )
    assert "verification" in second_invocation[2].content.lower()

    assert all(
        message.role != "tool"
        for message in second_invocation
    )

def test_coherent_formatter_retains_rejected_final_response() -> None:
    response = FinalResponse(
        text="premature completion"
    )

    messages = coherent_completion_rejection_formatter(
        response,
        MUTATION_FEEDBACK,
    )

    assert messages[0] == Message(
        role="assistant",
        content=(
            '{"type":"final",'
            '"text":"premature completion"}'
        ),
    )


def test_coherent_formatter_uses_user_controller_feedback() -> None:
    response = FinalResponse(
        text="premature completion"
    )

    messages = coherent_completion_rejection_formatter(
        response,
        MUTATION_FEEDBACK,
    )

    assert messages[1] == Message(
        role="user",
        content=(
            "Controller feedback: "
            + MUTATION_FEEDBACK
        ),
    )


def test_coherent_formatter_preserves_exact_feedback_content() -> None:
    response = FinalResponse(
        text="anything"
    )

    messages = coherent_completion_rejection_formatter(
        response,
        MUTATION_FEEDBACK,
    )

    assert len(messages) == 2
    assert messages[1].content.removeprefix(
        "Controller feedback: "
    ) == MUTATION_FEEDBACK