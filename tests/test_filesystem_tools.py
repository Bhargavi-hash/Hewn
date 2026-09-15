from pathlib import Path

from hewn.builtin_tools.filesystem import make_read_file_tool
from hewn.tools import ToolCall, ToolExecutor, ToolRegistry
from hewn.workspace import Workspace


def make_executor(workspace_root: Path) -> ToolExecutor:
    workspace = Workspace(workspace_root)

    registry = ToolRegistry()
    registry.register(make_read_file_tool(workspace))

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