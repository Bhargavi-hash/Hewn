from __future__ import annotations

import ast
from pathlib import Path
from typing import Any

from hewn.tools import ToolDefinition, ToolResult
from hewn.workspace import Workspace


def _find_python_symbols(
    root: Path,
    symbol_name: str,
) -> list[str]:
    matches: list[str] = []

    for path in sorted(root.rglob("*.py")):
        try:
            source = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue

        try:
            tree = ast.parse(source, filename=str(path))
        except SyntaxError:
            continue

        for node in ast.walk(tree):
            if isinstance(
                node,
                (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef),
            ) and node.name == symbol_name:
                kind = (
                    "class"
                    if isinstance(node, ast.ClassDef)
                    else "function"
                )

                matches.append(
                    f"{path.relative_to(root)}:"
                    f"{node.lineno}:{kind} {node.name}"
                )

    return matches


def make_find_symbol_tool(
    workspace: Workspace,
) -> ToolDefinition:
    def find_symbol_handler(
        arguments: dict[str, Any],
    ) -> ToolResult:
        name = arguments["name"]

        matches = _find_python_symbols(
            workspace.root,
            name,
        )

        if not matches:
            return ToolResult(
                ok=True,
                output="",
            )

        return ToolResult(
            ok=True,
            output="\n".join(matches),
        )

    return ToolDefinition(
        name="find_symbol",
        description=(
            "Find Python class and function definitions by exact symbol "
            "name in the workspace. Returns definition file paths, line "
            "numbers, symbol kinds, and names."
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