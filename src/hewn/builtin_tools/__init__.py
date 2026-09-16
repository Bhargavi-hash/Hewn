from __future__ import annotations

from hewn.builtin_tools.commands import make_run_check_tool
from hewn.builtin_tools.filesystem import (
    make_list_directory_tool,
    make_read_file_tool,
    make_replace_text_tool,
)
from hewn.builtin_tools.repository import make_repository_map_tool
from hewn.builtin_tools.search import make_search_text_tool
from hewn.builtin_tools.symbols import make_find_symbol_tool
from hewn.repository.index import RepositoryIndex
from hewn.tools import ToolRegistry
from hewn.workspace import Workspace


def make_builtin_tool_registry(
    workspace: Workspace,
    repository_index: RepositoryIndex | None = None,
) -> ToolRegistry:
    registry = ToolRegistry()

    registry.register(make_list_directory_tool(workspace))
    registry.register(make_read_file_tool(workspace))
    registry.register(make_search_text_tool(workspace))
    registry.register(make_replace_text_tool(workspace))
    registry.register(make_run_check_tool(workspace))
    if repository_index is not None:
        registry.register(
            make_find_symbol_tool(repository_index)
        )
        registry.register(
            make_repository_map_tool(repository_index)
        )

    return registry