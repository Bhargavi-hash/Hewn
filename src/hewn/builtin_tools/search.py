
from __future__ import annotations

import subprocess
from typing import Any

from hewn.tools import ToolDefinition, ToolError, ToolResult
from hewn.workspace import Workspace

DEFAULT_SEARCH_RESULT_LIMIT = 100


def make_search_text_tool(
    workspace: Workspace,
    *,
    result_limit: int = DEFAULT_SEARCH_RESULT_LIMIT,
) -> ToolDefinition:
    if result_limit < 1:
        raise ValueError("result_limit must be at least 1")

    def search_text_handler(arguments: dict[str, Any]) -> ToolResult:
        query = arguments["query"]

        try:
            completed = subprocess.run(
                [
                    "rg",
                    "--line-number",
                    "--no-heading",
                    "--color=never",
                    "--fixed-strings",
                    query,
                    ".",
                ],
                cwd=workspace.root,
                capture_output=True,
                text=True,
                check=False,
            )
        except FileNotFoundError as exc:
            raise ToolError(
                "search_text requires ripgrep (rg), but it is not installed"
            ) from exc

        if completed.returncode not in {0, 1}:
            message = completed.stderr.strip() or "ripgrep failed"
            raise ToolError(f"Search failed: {message}")

        matches = completed.stdout.splitlines()

        visible_matches = matches[:result_limit]
        remaining = len(matches) - len(visible_matches)

        if remaining > 0:
            visible_matches.append(
                f"... {remaining} more matches not shown"
            )

        return ToolResult(
            ok=True,
            output="\n".join(visible_matches),
        )

    return ToolDefinition(
        name="search_text",
        description=(
            "Search workspace text files for an exact text string. "
            "Returns matching file paths, line numbers, and matching lines."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "minLength": 1,
                },
            },
            "required": ["query"],
            "additionalProperties": False,
        },
        handler=search_text_handler,
    )