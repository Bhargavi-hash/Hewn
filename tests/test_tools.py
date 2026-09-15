from typing import Any

import pytest

from hewn.tools import (
    ToolCall,
    ToolDefinition,
    ToolError,
    ToolExecutor,
    ToolRegistry,
    ToolResult,
)


def test_expected_tool_error_becomes_failed_result() -> None:
    def failing_handler(arguments: dict[str, Any]) -> ToolResult:
        raise ToolError("File not found")

    registry = ToolRegistry()
    registry.register(
        ToolDefinition(
            name="failing",
            description="Always fails in an expected way.",
            input_schema={
                "type": "object",
                "properties": {},
                "additionalProperties": False,
            },
            handler=failing_handler,
        )
    )

    executor = ToolExecutor(registry)

    result = executor.execute(
        ToolCall(
            name="failing",
            arguments={},
        )
    )

    assert result == ToolResult(
        ok=False,
        error="File not found",
    )


def test_unexpected_handler_bug_is_not_hidden() -> None:
    def buggy_handler(arguments: dict[str, Any]) -> ToolResult:
        raise RuntimeError("programming bug")

    registry = ToolRegistry()
    registry.register(
        ToolDefinition(
            name="buggy",
            description="Contains an unexpected implementation bug.",
            input_schema={
                "type": "object",
                "properties": {},
                "additionalProperties": False,
            },
            handler=buggy_handler,
        )
    )

    executor = ToolExecutor(registry)

    with pytest.raises(RuntimeError, match="programming bug"):
        executor.execute(
            ToolCall(
                name="buggy",
                arguments={},
            )
        )

def echo_handler(arguments: dict[str, Any]) -> ToolResult:
    value = arguments["value"]
    return ToolResult(ok=True, output=str(value))


def make_echo_tool() -> ToolDefinition:
    return ToolDefinition(
        name="echo",
        description="Return the supplied value.",
        input_schema={
            "type": "object",
            "properties": {
                "value": {"type": "string"},
            },
            "required": ["value"],
            "additionalProperties": False,
        },
        handler=echo_handler,
    )


def test_registered_tool_executes() -> None:
    registry = ToolRegistry()
    registry.register(make_echo_tool())

    executor = ToolExecutor(registry)

    result = executor.execute(
        ToolCall(
            name="echo",
            arguments={"value": "hello"},
        )
    )

    assert result == ToolResult(ok=True, output="hello")


def test_unknown_tool_is_rejected() -> None:
    registry = ToolRegistry()
    executor = ToolExecutor(registry)

    result = executor.execute(
        ToolCall(
            name="destroy_the_moon",
            arguments={},
        )
    )

    assert result.ok is False
    assert result.error == "Unknown tool: destroy_the_moon"


def test_duplicate_tool_registration_is_rejected() -> None:
    registry = ToolRegistry()
    registry.register(make_echo_tool())

    try:
        registry.register(make_echo_tool())
    except ValueError as exc:
        assert str(exc) == "Tool already registered: echo"
    else:
        raise AssertionError("Expected duplicate registration to fail")