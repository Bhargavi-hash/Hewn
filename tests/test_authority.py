from __future__ import annotations

from typing import Any

from hewn.authority import (
    AuthorityGrant,
    AuthorityPolicy,
    Capability,
    classify_tool_capability,
)
from hewn.tools import (
    ToolCall,
    ToolDefinition,
    ToolExecutor,
    ToolRegistry,
    ToolResult,
)


def make_recording_executor(
    grant: AuthorityGrant,
) -> tuple[ToolExecutor, list[dict[str, Any]]]:
    calls: list[dict[str, Any]] = []

    def handler(arguments: dict[str, Any]) -> ToolResult:
        calls.append(arguments)
        return ToolResult(ok=True, output="executed")

    registry = ToolRegistry()
    registry.register(
        ToolDefinition(
            name="replace_text",
            description="Test mutation tool.",
            input_schema={
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                },
                "required": ["path"],
                "additionalProperties": False,
            },
            handler=handler,
        )
    )

    return (
        ToolExecutor(
            registry,
            authority_policy=AuthorityPolicy(grant),
        ),
        calls,
    )


def test_classifies_builtin_capabilities() -> None:
    assert classify_tool_capability("list_directory") is Capability.REPOSITORY_READ
    assert classify_tool_capability("read_file") is Capability.REPOSITORY_READ
    assert classify_tool_capability("search_text") is Capability.REPOSITORY_READ
    assert classify_tool_capability("find_symbol") is Capability.REPOSITORY_READ
    assert classify_tool_capability("repository_map") is Capability.REPOSITORY_READ

    assert classify_tool_capability("replace_text") is Capability.REPOSITORY_WRITE
    assert classify_tool_capability("run_check") is Capability.APPROVED_CHECK


def test_unknown_tool_has_no_capability_classification() -> None:
    assert classify_tool_capability("future_tool") is None


def test_repository_read_allowed_when_granted() -> None:
    policy = AuthorityPolicy(
        AuthorityGrant(repository_read=True)
    )

    decision = policy.authorize(
        ToolCall(
            name="read_file",
            arguments={"path": "src/main.py"},
        )
    )

    assert decision.allowed is True
    assert decision.capability is Capability.REPOSITORY_READ


def test_repository_read_rejected_without_grant() -> None:
    policy = AuthorityPolicy(AuthorityGrant())

    decision = policy.authorize(
        ToolCall(
            name="read_file",
            arguments={"path": "src/main.py"},
        )
    )

    assert decision.allowed is False
    assert decision.capability is Capability.REPOSITORY_READ
    assert "repository_read" in decision.reason


def test_repository_write_allowed_when_granted() -> None:
    policy = AuthorityPolicy(
        AuthorityGrant(repository_write=True)
    )

    decision = policy.authorize(
        ToolCall(
            name="replace_text",
            arguments={
                "path": "src/main.py",
                "old": "before",
                "new": "after",
            },
        )
    )

    assert decision.allowed is True
    assert decision.capability is Capability.REPOSITORY_WRITE


def test_repository_write_rejected_without_grant() -> None:
    policy = AuthorityPolicy(AuthorityGrant())

    decision = policy.authorize(
        ToolCall(
            name="replace_text",
            arguments={
                "path": "src/main.py",
                "old": "before",
                "new": "after",
            },
        )
    )

    assert decision.allowed is False
    assert decision.capability is Capability.REPOSITORY_WRITE


def test_approved_check_allowed_when_granted() -> None:
    policy = AuthorityPolicy(
        AuthorityGrant(approved_checks=True)
    )

    decision = policy.authorize(
        ToolCall(
            name="run_check",
            arguments={"check": "tests"},
        )
    )

    assert decision.allowed is True
    assert decision.capability is Capability.APPROVED_CHECK


def test_approved_check_rejected_without_grant() -> None:
    policy = AuthorityPolicy(AuthorityGrant())

    decision = policy.authorize(
        ToolCall(
            name="run_check",
            arguments={"check": "tests"},
        )
    )

    assert decision.allowed is False
    assert decision.capability is Capability.APPROVED_CHECK


def test_unknown_registered_tool_is_denied_by_default() -> None:
    policy = AuthorityPolicy(
        AuthorityGrant(
            repository_read=True,
            repository_write=True,
            approved_checks=True,
        )
    )

    decision = policy.authorize(
        ToolCall(
            name="future_tool",
            arguments={},
        )
    )

    assert decision.allowed is False
    assert decision.capability is None
    assert "No authority classification" in decision.reason


def test_denied_call_does_not_invoke_handler() -> None:
    executor, calls = make_recording_executor(
        AuthorityGrant(repository_write=False)
    )

    result = executor.execute(
        ToolCall(
            name="replace_text",
            arguments={"path": "src/main.py"},
        )
    )

    assert result.ok is False
    assert result.error is not None
    assert result.error.startswith("Authority denied:")
    assert calls == []


def test_allowed_call_invokes_handler() -> None:
    executor, calls = make_recording_executor(
        AuthorityGrant(repository_write=True)
    )

    result = executor.execute(
        ToolCall(
            name="replace_text",
            arguments={"path": "src/main.py"},
        )
    )

    assert result.ok is True
    assert result.output == "executed"
    assert calls == [{"path": "src/main.py"}]


def test_schema_validation_occurs_before_authority() -> None:
    executor, calls = make_recording_executor(
        AuthorityGrant(repository_write=True)
    )

    result = executor.execute(
        ToolCall(
            name="replace_text",
            arguments={
                "path": "src/main.py",
                "unexpected": True,
            },
        )
    )

    assert result.ok is False
    assert result.error is not None
    assert result.error.startswith("Invalid tool arguments:")
    assert calls == []


def test_executor_without_policy_preserves_existing_behavior() -> None:
    calls: list[dict[str, Any]] = []

    def handler(arguments: dict[str, Any]) -> ToolResult:
        calls.append(arguments)
        return ToolResult(ok=True, output="executed")

    registry = ToolRegistry()
    registry.register(
        ToolDefinition(
            name="future_tool",
            description="Compatibility test tool.",
            input_schema={
                "type": "object",
                "additionalProperties": False,
            },
            handler=handler,
        )
    )

    executor = ToolExecutor(registry)

    result = executor.execute(
        ToolCall(
            name="future_tool",
            arguments={},
        )
    )

    assert result.ok is True
    assert calls == [{}]