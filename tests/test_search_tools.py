import subprocess
from pathlib import Path

import pytest

from hewn.builtin_tools.search import make_search_text_tool
from hewn.tools import ToolCall, ToolExecutor, ToolRegistry
from hewn.workspace import Workspace


def make_executor(workspace_root: Path) -> ToolExecutor:
    workspace = Workspace(workspace_root)

    registry = ToolRegistry()
    registry.register(make_search_text_tool(workspace))

    return ToolExecutor(registry)


def test_search_text_finds_exact_matches(tmp_path: Path) -> None:
    source = tmp_path / "tools.py"
    source.write_text(
        "class ToolExecutor:\n"
        "    pass\n",
        encoding="utf-8",
    )

    test_file = tmp_path / "test_tools.py"
    test_file.write_text(
        "executor = ToolExecutor()\n",
        encoding="utf-8",
    )

    executor = make_executor(tmp_path)

    result = executor.execute(
        ToolCall(
            name="search_text",
            arguments={"query": "ToolExecutor"},
        )
    )

    assert result.ok is True
    assert result.output is not None
    assert "tools.py:1:class ToolExecutor:" in result.output
    assert "test_tools.py:1:executor = ToolExecutor()" in result.output

# Testing no match semantics
def test_search_text_no_matches_is_success(tmp_path: Path) -> None:
    (tmp_path / "hello.py").write_text(
        "print('hello')\n",
        encoding="utf-8",
    )

    executor = make_executor(tmp_path)

    result = executor.execute(
        ToolCall(
            name="search_text",
            arguments={"query": "DefinitelyNotHere"},
        )
    )

    assert result.ok is True
    assert result.output == ""

# Testing output budget
def test_search_text_truncates_results(tmp_path: Path) -> None:
    source = tmp_path / "many.txt"
    source.write_text(
        "needle\nneedle\nneedle\nneedle\nneedle\n",
        encoding="utf-8",
    )

    workspace = Workspace(tmp_path)

    registry = ToolRegistry()
    registry.register(
        make_search_text_tool(
            workspace,
            result_limit=3,
        )
    )

    executor = ToolExecutor(registry)

    result = executor.execute(
        ToolCall(
            name="search_text",
            arguments={"query": "needle"},
        )
    )

    assert result.ok is True
    assert result.output is not None

    lines = result.output.splitlines()

    assert len(lines) == 4
    assert lines[-1] == "... 2 more matches not shown"

def test_search_text_rejects_invalid_result_limit(
    tmp_path: Path,
) -> None:
    workspace = Workspace(tmp_path)

    with pytest.raises(
        ValueError,
        match="result_limit must be at least 1",
    ):
        make_search_text_tool(
            workspace,
            result_limit=0,
        )

def test_search_text_respects_gitignore(tmp_path: Path) -> None:
    subprocess.run(
        ["git", "init", "-q"],
        cwd=tmp_path,
        check=True,
    )

    (tmp_path / ".gitignore").write_text(
        "ignored.txt\n",
        encoding="utf-8",
    )

    (tmp_path / "visible.txt").write_text(
        "needle\n",
        encoding="utf-8",
    )

    (tmp_path / "ignored.txt").write_text(
        "needle\n",
        encoding="utf-8",
    )

    executor = make_executor(tmp_path)

    result = executor.execute(
        ToolCall(
            name="search_text",
            arguments={"query": "needle"},
        )
    )

    assert result.ok is True
    assert result.output is not None
    assert "visible.txt" in result.output
    assert "ignored.txt" not in result.output