from __future__ import annotations

from typing import Any

from hewn.tools import ToolDefinition, ToolError, ToolResult
from hewn.workspace import Workspace, WorkspaceViolationError


def make_read_file_tool(workspace: Workspace) -> ToolDefinition:
    def read_file_handler(arguments: dict[str, Any]) -> ToolResult:
        try:
            path = workspace.resolve(arguments["path"])
        except WorkspaceViolationError as exc:
            raise ToolError(str(exc)) from exc
        
        if not path.exists():
            raise ToolError(f"File not found: {arguments['path']}")

        if not path.is_file():
            raise ToolError(f"Not a file: {arguments['path']}")

        try:
            contents = path.read_text(encoding="utf-8")
        except UnicodeDecodeError as exc:
            raise ToolError(
                f"File is not valid UTF-8: {arguments['path']}"
            ) from exc

        return ToolResult(
            ok=True,
            output=contents,
        )

    return ToolDefinition(
        name="read_file",
        description="Read the UTF-8 text contents of a file inside the workspace.",
        input_schema={
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "minLength": 1,
                },
            },
            "required": ["path"],
            "additionalProperties": False,
        },
        handler=read_file_handler,
    )