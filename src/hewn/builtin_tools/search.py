
from __future__ import annotations

import subprocess
from typing import Any

from hewn.tools import ToolDefinition, ToolError, ToolResult
from hewn.workspace import Workspace, WorkspaceViolationError

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
        requested_path = arguments.get("path", ".")

        try:
            search_root = workspace.resolve(requested_path)
        except WorkspaceViolationError as exc:
            raise ToolError(str(exc)) from exc

        if not search_root.exists():
            raise ToolError(f"Search path not found: {requested_path}")

        if not search_root.is_dir():
            raise ToolError(f"Search path is not a directory: {requested_path}")

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
                cwd=search_root,
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
            "Search for an exact text string within a workspace directory. "
            "The optional path selects a workspace-relative directory and "
            "defaults to the workspace root. Returns matching file paths, "
            "line numbers, and matching lines."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "minLength": 1,
                },
                "path": {
                    "type": "string",
                    "minLength": 1,
                },
            },
            "required": ["query"],
            "additionalProperties": False,
        },
        handler=search_text_handler,
    )