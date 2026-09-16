from pathlib import Path

from hewn.builtin_tools import make_builtin_tool_registry
from hewn.repository.index import RepositoryIndex
from hewn.workspace import Workspace


def test_builtin_registry_contains_expected_tools(
    tmp_path: Path,
) -> None:
    workspace = Workspace(tmp_path)
    repository_index = RepositoryIndex.build(tmp_path)


    registry = make_builtin_tool_registry(
        workspace,
        repository_index=repository_index,
    )

    names = {
        definition.name
        for definition in registry.definitions()
    }

    assert names == {
        "list_directory",
        "read_file",
        "replace_text",
        "search_text",
        "run_check",
        "find_symbol",
        "repository_map",
    }