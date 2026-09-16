from pathlib import Path

import pytest

from hewn.builtin_tools.filesystem import (
    make_list_directory_tool,
    make_read_file_tool,
    make_replace_text_tool,
)
from hewn.tools import ToolCall, ToolExecutor, ToolRegistry
from hewn.workspace import Workspace


def make_executor(workspace_root: Path) -> ToolExecutor:
    workspace = Workspace(workspace_root)

    registry = ToolRegistry()
    registry.register(make_read_file_tool(workspace))
    registry.register(make_list_directory_tool(workspace))

    return ToolExecutor(registry)


def test_read_file_returns_contents(tmp_path: Path) -> None:
    source = tmp_path / "hello.py"
    source.write_text("print('hello')\n", encoding="utf-8")

    executor = make_executor(tmp_path)

    result = executor.execute(
        ToolCall(
            name="read_file",
            arguments={"path": "hello.py"},
        )
    )

    assert result.ok is True
    assert result.output == "print('hello')\n"
    assert result.error is None


def test_read_file_reports_missing_file(tmp_path: Path) -> None:
    executor = make_executor(tmp_path)

    result = executor.execute(
        ToolCall(
            name="read_file",
            arguments={"path": "missing.py"},
        )
    )

    assert result.ok is False
    assert result.error == "File not found: missing.py"


def test_read_file_rejects_directory(tmp_path: Path) -> None:
    directory = tmp_path / "src"
    directory.mkdir()

    executor = make_executor(tmp_path)

    result = executor.execute(
        ToolCall(
            name="read_file",
            arguments={"path": "src"},
        )
    )

    assert result.ok is False
    assert result.error == "Not a file: src"

def test_read_file_rejects_invalid_schema(tmp_path: Path) -> None:
    executor = make_executor(tmp_path)

    result = executor.execute(
        ToolCall(
            name="read_file",
            arguments={"path": 42},
        )
    )

    assert result.ok is False
    assert result.error is not None
    assert "string" in result.error

def test_read_file_rejects_workspace_escape(tmp_path: Path) -> None:
    outside = tmp_path.parent / "secret.txt"
    outside.write_text("secret", encoding="utf-8")

    executor = make_executor(tmp_path)

    result = executor.execute(
        ToolCall(
            name="read_file",
            arguments={"path": "../secret.txt"},
        )
    )

    assert result.ok is False
    assert result.error is not None
    assert "escapes workspace" in result.error

def test_list_directory_returns_immediate_entries(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "tests").mkdir()
    (tmp_path / "README.md").write_text("hello", encoding="utf-8")
    (tmp_path / "pyproject.toml").write_text("", encoding="utf-8")

    executor = make_executor(tmp_path)

    result = executor.execute(
        ToolCall(
            name="list_directory",
            arguments={"path": "."},
        )
    )

    assert result.ok is True
    assert result.output == (
        "src/\n"
        "tests/\n"
        "pyproject.toml\n"
        "README.md"
    )

def test_list_directory_is_not_recursive(tmp_path: Path) -> None:
    source = tmp_path / "src"
    source.mkdir()

    nested = source / "hewn"
    nested.mkdir()

    (nested / "agent.py").write_text("", encoding="utf-8")

    executor = make_executor(tmp_path)

    result = executor.execute(
        ToolCall(
            name="list_directory",
            arguments={"path": "."},
        )
    )

    assert result.ok is True
    assert result.output == "src/"
    assert "agent.py" not in result.output

def test_list_directory_rejects_workspace_escape(tmp_path: Path) -> None:
    executor = make_executor(tmp_path)

    result = executor.execute(
        ToolCall(
            name="list_directory",
            arguments={"path": ".."},
        )
    )

    assert result.ok is False
    assert result.error is not None
    assert "escapes workspace" in result.error


def test_list_directory_rejects_file_path(tmp_path: Path) -> None:
    (tmp_path / "README.md").write_text("hello", encoding="utf-8")

    executor = make_executor(tmp_path)

    result = executor.execute(
        ToolCall(
            name="list_directory",
            arguments={"path": "README.md"},
        )
    )

    assert result.ok is False
    assert result.error == "Not a directory: README.md"

def test_list_directory_truncates_large_listing(tmp_path: Path) -> None:
    for index in range(5):
        (tmp_path / f"file{index}.txt").write_text("", encoding="utf-8")

    workspace = Workspace(tmp_path)

    registry = ToolRegistry()
    registry.register(
        make_list_directory_tool(
            workspace,
            entry_limit=3,
        )
    )

    executor = ToolExecutor(registry)

    result = executor.execute(
        ToolCall(
            name="list_directory",
            arguments={"path": "."},
        )
    )

    assert result.ok is True
    assert result.output == (
        "file0.txt\n"
        "file1.txt\n"
        "file2.txt\n"
        "... 2 more entries not shown"
    )

def test_list_directory_rejects_invalid_entry_limit(
    tmp_path: Path,
) -> None:
    workspace = Workspace(tmp_path)

    with pytest.raises(
        ValueError,
        match="entry_limit must be at least 1",
    ):
        make_list_directory_tool(
            workspace,
            entry_limit=0,
        )

def test_replace_text_updates_unique_match(
    tmp_path: Path,
) -> None:
    path = tmp_path / "example.py"
    path.write_text(
        "def add(a, b):\n"
        "    return a - b\n",
        encoding="utf-8",
    )

    workspace = Workspace(tmp_path)
    registry = ToolRegistry()
    registry.register(
        make_replace_text_tool(workspace)
    )
    executor = ToolExecutor(registry)

    result = executor.execute(
        ToolCall(
            name="replace_text",
            arguments={
                "path": "example.py",
                "old": "return a - b",
                "new": "return a + b",
            },
        )
    )

    assert result.ok
    assert path.read_text(encoding="utf-8") == (
        "def add(a, b):\n"
        "    return a + b\n"
    )

def test_replace_text_rejects_missing_match(
    tmp_path: Path,
) -> None:
    path = tmp_path / "example.py"
    path.write_text(
        "return a + b\n",
        encoding="utf-8",
    )

    workspace = Workspace(tmp_path)
    registry = ToolRegistry()
    registry.register(
        make_replace_text_tool(workspace)
    )
    executor = ToolExecutor(registry)

    result = executor.execute(
        ToolCall(
            name="replace_text",
            arguments={
                "path": "example.py",
                "old": "return a - b",
                "new": "return a + b",
            },
        )
    )

    assert not result.ok
    assert result.error == (
        "Text to replace was not found"
    )

def test_replace_text_rejects_multiple_matches(
    tmp_path: Path,
) -> None:
    path = tmp_path / "example.py"
    path.write_text(
        "return None\n"
        "return None\n",
        encoding="utf-8",
    )

    workspace = Workspace(tmp_path)
    registry = ToolRegistry()
    registry.register(
        make_replace_text_tool(workspace)
    )
    executor = ToolExecutor(registry)

    result = executor.execute(
        ToolCall(
            name="replace_text",
            arguments={
                "path": "example.py",
                "old": "return None",
                "new": "return result",
            },
        )
    )

    assert not result.ok
    assert result.error == (
        "Text to replace occurs more than once"
    )

    assert path.read_text(encoding="utf-8") == (
        "return None\n"
        "return None\n"
    )