from __future__ import annotations

from pathlib import Path

from hewn.builtin_tools.commands import make_run_check_tool
from hewn.tools import ToolCall, ToolExecutor, ToolRegistry
from hewn.workspace import Workspace


def make_executor(
    workspace_root: Path,
    *,
    timeout_seconds: float = 60.0,
    output_limit: int = 12_000,
) -> ToolExecutor:
    workspace = Workspace(workspace_root)

    registry = ToolRegistry()
    registry.register(
        make_run_check_tool(
            workspace,
            timeout_seconds=timeout_seconds,
            output_limit=output_limit,
        )
    )

    return ToolExecutor(registry)


def test_run_check_executes_passing_tests(
    tmp_path: Path,
) -> None:
    (tmp_path / "test_example.py").write_text(
        "def test_example():\n"
        "    assert 1 + 1 == 2\n",
        encoding="utf-8",
    )

    executor = make_executor(tmp_path)

    result = executor.execute(
        ToolCall(
            name="run_check",
            arguments={
                "check": "tests",
            },
        )
    )

    assert result.ok
    assert result.error is None
    assert "1 passed" in (result.output or "")


def test_run_check_returns_failing_test_output(
    tmp_path: Path,
) -> None:
    (tmp_path / "test_example.py").write_text(
        "def test_example():\n"
        "    assert 1 + 1 == 3\n",
        encoding="utf-8",
    )

    executor = make_executor(tmp_path)

    result = executor.execute(
        ToolCall(
            name="run_check",
            arguments={
                "check": "tests",
            },
        )
    )

    assert not result.ok
    assert result.error == "Check failed with exit code 1"
    assert "FAILED" in (result.output or "")


def test_run_check_rejects_unknown_check(
    tmp_path: Path,
) -> None:
    executor = make_executor(tmp_path)

    result = executor.execute(
        ToolCall(
            name="run_check",
            arguments={
                "check": "delete_everything",
            },
        )
    )

    assert not result.ok
    assert result.error is not None
    assert "Invalid tool arguments" in result.error


def test_run_check_rejects_additional_arguments(
    tmp_path: Path,
) -> None:
    executor = make_executor(tmp_path)

    result = executor.execute(
        ToolCall(
            name="run_check",
            arguments={
                "check": "tests",
                "command": "rm -rf /",
            },
        )
    )

    assert not result.ok
    assert result.error is not None
    assert "Invalid tool arguments" in result.error


def test_run_check_rejects_nonpositive_timeout(
    tmp_path: Path,
) -> None:
    workspace = Workspace(tmp_path)

    try:
        make_run_check_tool(
            workspace,
            timeout_seconds=0,
        )
    except ValueError as exc:
        assert str(exc) == (
            "timeout_seconds must be greater than zero"
        )
    else:
        raise AssertionError("Expected ValueError")


def test_run_check_rejects_invalid_output_limit(
    tmp_path: Path,
) -> None:
    workspace = Workspace(tmp_path)

    try:
        make_run_check_tool(
            workspace,
            output_limit=0,
        )
    except ValueError as exc:
        assert str(exc) == (
            "output_limit must be at least 1"
        )
    else:
        raise AssertionError("Expected ValueError")


def test_run_check_truncates_large_output(
    tmp_path: Path,
) -> None:
    (tmp_path / "test_example.py").write_text(
        "def test_example():\n"
        "    assert False, 'abcdefghijklmnopqrstuvwxyz'\n",
        encoding="utf-8",
    )

    executor = make_executor(
        tmp_path,
        output_limit=100,
    )

    result = executor.execute(
        ToolCall(
            name="run_check",
            arguments={
                "check": "tests",
            },
        )
    )

    assert not result.ok
    assert result.output is not None
    assert "characters not shown" in result.output