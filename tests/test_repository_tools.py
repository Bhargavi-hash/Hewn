from pathlib import Path

from hewn.builtin_tools.repository import (
    format_repository_map,
    make_repository_map_tool,
)
from hewn.repository.index import RepositoryIndex
from hewn.tools import ToolCall, ToolExecutor, ToolRegistry


def make_executor(root: Path) -> ToolExecutor:
    repository_index = RepositoryIndex.build(root)

    registry = ToolRegistry()
    registry.register(
        make_repository_map_tool(repository_index)
    )

    return ToolExecutor(registry)


def test_repository_map_shows_files_symbols_and_dependencies(
    tmp_path: Path,
) -> None:
    package = tmp_path / "src" / "example"
    package.mkdir(parents=True)

    (package / "tools.py").write_text(
        "class ToolExecutor:\n"
        "    pass\n",
        encoding="utf-8",
    )

    (package / "agent.py").write_text(
        "from example.tools import ToolExecutor\n\n"
        "class Agent:\n"
        "    def run(self) -> None:\n"
        "        pass\n",
        encoding="utf-8",
    )

    executor = make_executor(tmp_path)

    result = executor.execute(
        ToolCall(
            name="repository_map",
            arguments={},
        )
    )

    assert result.ok is True
    assert result.output is not None
    assert "src/example/agent.py" in result.output
    assert "Agent" in result.output
    assert "Agent.run" in result.output
    assert "-> src/example/tools.py" in result.output


def test_repository_map_can_scope_to_path(
    tmp_path: Path,
) -> None:
    source = tmp_path / "src" / "example"
    tests = tmp_path / "tests"

    source.mkdir(parents=True)
    tests.mkdir()

    (source / "agent.py").write_text(
        "class Agent:\n"
        "    pass\n",
        encoding="utf-8",
    )

    (tests / "test_agent.py").write_text(
        "def test_agent() -> None:\n"
        "    pass\n",
        encoding="utf-8",
    )

    executor = make_executor(tmp_path)

    result = executor.execute(
        ToolCall(
            name="repository_map",
            arguments={"path": "src"},
        )
    )

    assert result.ok is True
    assert result.output is not None
    assert "src/example/agent.py" in result.output
    assert "tests/test_agent.py" not in result.output

def test_format_repository_map_can_scope_to_path(
    tmp_path: Path,
) -> None:
    source = tmp_path / "src" / "example"
    tests = tmp_path / "tests"

    source.mkdir(parents=True)
    tests.mkdir()

    (source / "agent.py").write_text(
        "class Agent:\n"
        "    pass\n",
        encoding="utf-8",
    )

    (tests / "test_agent.py").write_text(
        "def test_agent() -> None:\n"
        "    pass\n",
        encoding="utf-8",
    )

    index = RepositoryIndex.build(tmp_path)

    output = format_repository_map(
        index,
        path_prefix="src",
    )

    assert "src/example/agent.py" in output
    assert "tests/test_agent.py" not in output