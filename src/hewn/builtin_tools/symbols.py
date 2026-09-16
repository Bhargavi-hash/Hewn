from __future__ import annotations

from typing import Any

from hewn.repository.index import RepositoryIndex
from hewn.tools import ToolDefinition, ToolResult


def make_find_symbol_tool(
    repository_index: RepositoryIndex,
) -> ToolDefinition:
    def find_symbol_handler(
        arguments: dict[str, Any],
    ) -> ToolResult:
        name = arguments["name"]
        matches = repository_index.find_symbol(name)

        output = "\n".join(
            (
                f"{symbol.location.path}:"
                f"{symbol.location.start_line}:"
                f"{symbol.kind.value} "
                f"{symbol.qualified_name}"
            )
            for symbol in matches
        )

        return ToolResult(
            ok=True,
            output=output,
        )

    return ToolDefinition(
        name="find_symbol",
        description=(
            "Find Python class, function, and method definitions by exact "
            "symbol name in the repository. Returns definition file paths, "
            "line numbers, symbol kinds, and qualified names."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "minLength": 1,
                },
            },
            "required": ["name"],
            "additionalProperties": False,
        },
        handler=find_symbol_handler,
    )