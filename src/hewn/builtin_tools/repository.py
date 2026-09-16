from __future__ import annotations

from pathlib import PurePosixPath
from typing import Any

from hewn.repository.index import RepositoryIndex
from hewn.tools import ToolDefinition, ToolResult


def make_repository_map_tool(
    repository_index: RepositoryIndex,
) -> ToolDefinition:
    def repository_map_handler(
        arguments: dict[str, Any],
    ) -> ToolResult:
        path_prefix = arguments.get("path")

        lines: list[str] = []

        for path, source_file in sorted(
            repository_index.files.items(),
            key=lambda item: str(item[0]),
        ):
            if path_prefix is not None and not _matches_prefix(
                path,
                path_prefix,
            ):
                continue

            lines.append(str(path))

            if source_file.symbols:
                symbols = ", ".join(
                    symbol.qualified_name
                    for symbol in source_file.symbols
                )
                lines.append(f"  symbols: {symbols}")

            dependencies = repository_index.dependencies_from(path)

            if dependencies:
                lines.append("  imports:")
                for dependency in dependencies:
                    lines.append(f"    -> {dependency.target}")

        return ToolResult(
            ok=True,
            output="\n".join(lines),
        )

    return ToolDefinition(
        name="repository_map",
        description=(
            "Inspect the repository's structural map. Returns source files, "
            "defined symbols, and internal file dependencies. Use this when "
            "you need to understand where an unfamiliar behavior or concept "
            "may be implemented."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "minLength": 1,
                    "description": (
                        "Optional repository-relative path prefix used to "
                        "limit the structural map."
                    ),
                },
            },
            "additionalProperties": False,
        },
        handler=repository_map_handler,
    )


def _matches_prefix(
    path: PurePosixPath,
    prefix: str,
) -> bool:
    normalized = prefix.strip("/")

    if not normalized:
        return True

    path_text = str(path)

    return (
        path_text == normalized
        or path_text.startswith(f"{normalized}/")
    )