from __future__ import annotations

from pathlib import Path

from evaluate_grounding_intervention import (
    GROUNDING_REASON_MISSING_TARGET,
    GROUNDING_REASON_NOOP,
    MISSING_TARGET_FEEDBACK,
    NOOP_FEEDBACK,
    GroundingToolExecutor,
)

from hewn.authority import AuthorityGrant, AuthorityPolicy
from hewn.builtin_tools import make_builtin_tool_registry
from hewn.models import Message, ModelResponse
from hewn.tools import (
    ToolCall,
    ToolDefinition,
)
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

        self.received_messages.append(
            list(messages)
        )

        response = self.responses[self.index]
        self.index += 1
        return response


def make_executor(
    tmp_path: Path,
    *,
    mutation_feedback_delivered: bool = True,
    grounding_enabled: bool = True,
) -> GroundingToolExecutor:
    workspace = Workspace(tmp_path)

    registry = make_builtin_tool_registry(
        workspace
    )

    authority = AuthorityPolicy(
        AuthorityGrant(
            repository_read=True,
            repository_write=True,
            approved_checks=True,
        )
    )

    return GroundingToolExecutor(
        registry,
        workspace=workspace,
        authority_policy=authority,
        mutation_feedback_delivered=(
            lambda: mutation_feedback_delivered
        ),
        grounding_enabled=grounding_enabled,
    )


def test_missing_target_receives_grounding_feedback(
    tmp_path: Path,
) -> None:
    target = tmp_path / "sample.py"
    target.write_text(
        "VALUE = 2\n",
        encoding="utf-8",
    )

    executor = make_executor(tmp_path)

    result = executor.execute(
        ToolCall(
            name="replace_text",
            arguments={
                "path": "sample.py",
                "old": "VALUE = 999",
                "new": "VALUE = 4",
            },
        )
    )

    assert result.ok is False
    assert result.error is not None
    assert "Text to replace was not found" in result.error
    assert MISSING_TARGET_FEEDBACK in result.error

    assert executor.probe.eligible is True
    assert executor.probe.delivered is True
    assert (
        executor.probe.reason
        == GROUNDING_REASON_MISSING_TARGET
    )

    assert target.read_text(
        encoding="utf-8"
    ) == "VALUE = 2\n"

    assert len(executor.calls) == 1
    assert executor.calls[0].effective_mutation is False


def test_noop_receives_grounding_feedback_without_repository_delta(
    tmp_path: Path,
) -> None:
    target = tmp_path / "sample.py"
    original = "VALUE = 2\n"

    target.write_text(
        original,
        encoding="utf-8",
    )

    executor = make_executor(tmp_path)

    result = executor.execute(
        ToolCall(
            name="replace_text",
            arguments={
                "path": "sample.py",
                "old": "VALUE = 2",
                "new": "VALUE = 2",
            },
        )
    )

    assert result.ok is True
    assert result.output is not None
    assert NOOP_FEEDBACK in result.output

    assert executor.probe.eligible is True
    assert executor.probe.delivered is True
    assert (
        executor.probe.reason
        == GROUNDING_REASON_NOOP
    )

    assert target.read_text(
        encoding="utf-8"
    ) == original

    assert len(executor.calls) == 1
    assert executor.calls[0].ok is True
    assert executor.calls[0].effective_mutation is False


def test_effective_edit_does_not_receive_grounding_feedback(
    tmp_path: Path,
) -> None:
    target = tmp_path / "sample.py"

    target.write_text(
        "VALUE = 2\n",
        encoding="utf-8",
    )

    executor = make_executor(tmp_path)

    result = executor.execute(
        ToolCall(
            name="replace_text",
            arguments={
                "path": "sample.py",
                "old": "VALUE = 2",
                "new": "VALUE = 4",
            },
        )
    )

    assert result.ok is True
    assert result.output is not None
    assert MISSING_TARGET_FEEDBACK not in result.output
    assert NOOP_FEEDBACK not in result.output

    assert executor.probe.eligible is False
    assert executor.probe.delivered is False
    assert executor.probe.reason is None

    assert target.read_text(
        encoding="utf-8"
    ) == "VALUE = 4\n"

    assert len(executor.calls) == 1
    assert executor.calls[0].effective_mutation is True


def test_grounding_not_delivered_before_mutation_feedback(
    tmp_path: Path,
) -> None:
    target = tmp_path / "sample.py"

    target.write_text(
        "VALUE = 2\n",
        encoding="utf-8",
    )

    executor = make_executor(
        tmp_path,
        mutation_feedback_delivered=False,
    )

    result = executor.execute(
        ToolCall(
            name="replace_text",
            arguments={
                "path": "sample.py",
                "old": "VALUE = 999",
                "new": "VALUE = 4",
            },
        )
    )

    assert result.ok is False
    assert result.error == "Text to replace was not found"

    assert executor.probe.eligible is False
    assert executor.probe.delivered is False
    assert executor.probe.reason is None


def test_grounding_not_delivered_when_disabled(
    tmp_path: Path,
) -> None:
    target = tmp_path / "sample.py"

    target.write_text(
        "VALUE = 2\n",
        encoding="utf-8",
    )

    executor = make_executor(
        tmp_path,
        grounding_enabled=False,
    )

    result = executor.execute(
        ToolCall(
            name="replace_text",
            arguments={
                "path": "sample.py",
                "old": "VALUE = 999",
                "new": "VALUE = 4",
            },
        )
    )

    assert result.ok is False
    assert result.error == "Text to replace was not found"

    assert executor.probe.eligible is False
    assert executor.probe.delivered is False


def test_grounding_feedback_is_delivered_at_most_once(
    tmp_path: Path,
) -> None:
    target = tmp_path / "sample.py"

    target.write_text(
        "VALUE = 2\n",
        encoding="utf-8",
    )

    executor = make_executor(tmp_path)

    first = executor.execute(
        ToolCall(
            name="replace_text",
            arguments={
                "path": "sample.py",
                "old": "VALUE = 999",
                "new": "VALUE = 4",
            },
        )
    )

    second = executor.execute(
        ToolCall(
            name="replace_text",
            arguments={
                "path": "sample.py",
                "old": "VALUE = 888",
                "new": "VALUE = 4",
            },
        )
    )

    assert first.error is not None
    assert MISSING_TARGET_FEEDBACK in first.error

    assert second.error == "Text to replace was not found"

    assert executor.probe.delivered is True
    assert len(
        [
            call
            for call in executor.calls
            if call.grounding_delivered
        ]
    ) == 1


def test_probe_detects_edit_after_grounding(
    tmp_path: Path,
) -> None:
    target = tmp_path / "sample.py"

    target.write_text(
        "VALUE = 2\n",
        encoding="utf-8",
    )

    executor = make_executor(tmp_path)

    executor.execute(
        ToolCall(
            name="replace_text",
            arguments={
                "path": "sample.py",
                "old": "VALUE = 999",
                "new": "VALUE = 4",
            },
        )
    )

    assert (
        executor.probe.edit_attempted_after_grounding
        is False
    )

    executor.execute(
        ToolCall(
            name="replace_text",
            arguments={
                "path": "sample.py",
                "old": "VALUE = 2",
                "new": "VALUE = 4",
            },
        )
    )

    assert (
        executor.probe.edit_attempted_after_grounding
        is True
    )


def test_grounding_feedback_contains_no_replacement_text(
    tmp_path: Path,
) -> None:
    target = tmp_path / "sample.py"

    target.write_text(
        "VALUE = 2\n",
        encoding="utf-8",
    )

    executor = make_executor(tmp_path)

    secret_replacement = "VALUE = 123456789"

    result = executor.execute(
        ToolCall(
            name="replace_text",
            arguments={
                "path": "sample.py",
                "old": "MISSING_SENTINEL",
                "new": secret_replacement,
            },
        )
    )

    assert result.error is not None
    assert MISSING_TARGET_FEEDBACK in result.error
    assert secret_replacement not in MISSING_TARGET_FEEDBACK
    assert "MISSING_SENTINEL" not in MISSING_TARGET_FEEDBACK