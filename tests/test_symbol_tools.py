from pathlib import Path

from hewn.builtin_tools.symbols import make_find_symbol_tool
from hewn.repository.index import RepositoryIndex
from hewn.tools import ToolCall, ToolExecutor, ToolRegistry

# from hewn.workspace import Workspace


def make_executor(workspace_root: Path) -> ToolExecutor:
    # workspace = Workspace(workspace_root)
    repository_index = RepositoryIndex.build(workspace_root)

    registry = ToolRegistry()
    registry.register(
        make_find_symbol_tool(repository_index)
    )

    return ToolExecutor(registry)


def test_find_symbol_finds_class_definition(
    tmp_path: Path,
) -> None:
    source = tmp_path / "tools.py"
    source.write_text(
        "class ToolExecutor:\n"
        "    pass\n",
        encoding="utf-8",
    )

    executor = make_executor(tmp_path)

    result = executor.execute(
        ToolCall(
            name="find_symbol",
            arguments={"name": "ToolExecutor"},
        )
    )

    assert result.ok is True
    assert result.output == "tools.py:1:class ToolExecutor"


def test_find_symbol_ignores_symbol_references(
    tmp_path: Path,
) -> None:
    (tmp_path / "definition.py").write_text(
        "class ToolExecutor:\n"
        "    pass\n",
        encoding="utf-8",
    )

    (tmp_path / "usage.py").write_text(
        "from definition import ToolExecutor\n"
        "executor = ToolExecutor()\n",
        encoding="utf-8",
    )

    executor = make_executor(tmp_path)

    result = executor.execute(
        ToolCall(
            name="find_symbol",
            arguments={"name": "ToolExecutor"},
        )
    )

    assert result.ok is True
    assert result.output is not None
    assert "definition.py:1:class ToolExecutor" in result.output
    assert "usage.py" not in result.output


def test_find_symbol_finds_function_definition(
    tmp_path: Path,
) -> None:
    (tmp_path / "example.py").write_text(
        "def calculate() -> int:\n"
        "    return 42\n",
        encoding="utf-8",
    )

    executor = make_executor(tmp_path)

    result = executor.execute(
        ToolCall(
            name="find_symbol",
            arguments={"name": "calculate"},
        )
    )

    assert result.ok is True
    assert result.output == "example.py:1:function calculate"


def test_find_symbol_returns_empty_for_unknown_symbol(
    tmp_path: Path,
) -> None:
    (tmp_path / "example.py").write_text(
        "class SomethingElse:\n"
        "    pass\n",
        encoding="utf-8",
    )

    executor = make_executor(tmp_path)

    result = executor.execute(
        ToolCall(
            name="find_symbol",
            arguments={"name": "Missing"},
        )
    )

    assert result.ok is True
    assert result.output == ""


def test_find_symbol_skips_invalid_python(
    tmp_path: Path,
) -> None:
    (tmp_path / "broken.py").write_text(
        "def broken(\n",
        encoding="utf-8",
    )

    (tmp_path / "valid.py").write_text(
        "class Workspace:\n"
        "    pass\n",
        encoding="utf-8",
    )

    executor = make_executor(tmp_path)

    result = executor.execute(
        ToolCall(
            name="find_symbol",
            arguments={"name": "Workspace"},
        )
    )

    assert result.ok is True
    assert result.output == "valid.py:1:class Workspace"