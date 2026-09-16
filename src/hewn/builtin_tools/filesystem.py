from __future__ import annotations

from typing import Any

from hewn.tools import ToolDefinition, ToolError, ToolResult
from hewn.workspace import Workspace, WorkspaceViolationError

DEFAULT_DIRECTORY_ENTRY_LIMIT = 200

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

def make_list_directory_tool(
        workspace: Workspace,
        *,
        entry_limit: int = DEFAULT_DIRECTORY_ENTRY_LIMIT,
    ) -> ToolDefinition:
    if entry_limit < 1:
        raise ValueError("entry_limit must be at least 1")
    
    def list_directory_handler(arguments: dict[str, Any]) -> ToolResult:
        requested_path = arguments["path"]

        try:
            path = workspace.resolve(requested_path)
        except WorkspaceViolationError as exc:
            raise ToolError(str(exc)) from exc

        if not path.exists():
            raise ToolError(f"Directory not found: {requested_path}")

        if not path.is_dir():
            raise ToolError(f"Not a directory: {requested_path}")

        entries = sorted(
            path.iterdir(),
            key=lambda entry: (not entry.is_dir(), entry.name.lower()),
        )

        visible_entries = entries[:entry_limit]

        lines = [
            f"{entry.name}/" if entry.is_dir() else entry.name
            for entry in visible_entries
        ]

        remaining = len(entries) - len(visible_entries)

        if remaining > 0:
            lines.append(f"... {remaining} more entries not shown")

        return ToolResult(
            ok=True,
            output="\n".join(lines),
        )

    return ToolDefinition(
        name="list_directory",
        description=(
            "List the immediate files and directories inside a workspace directory. "
            "Directories end with '/'. The listing is not recursive."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                },
            },
            "required": ["path"],
            "additionalProperties": False,
        },
        handler=list_directory_handler,
    )

def make_replace_text_tool(
    workspace: Workspace,
) -> ToolDefinition:
    def replace_text_handler(
        arguments: dict[str, Any],
    ) -> ToolResult:
        try:
            path = workspace.resolve(arguments["path"])
        except WorkspaceViolationError as exc:
            raise ToolError(str(exc)) from exc

        if not path.exists():
            raise ToolError(
                f"File not found: {arguments['path']}"
            )

        if not path.is_file():
            raise ToolError(
                f"Not a file: {arguments['path']}"
            )

        try:
            contents = path.read_text(encoding="utf-8")
        except UnicodeDecodeError as exc:
            raise ToolError(
                f"File is not valid UTF-8: {arguments['path']}"
            ) from exc

        old = arguments["old"]
        new = arguments["new"]

        occurrence_count = contents.count(old)

        if occurrence_count == 0:
            raise ToolError(
                "Text to replace was not found"
            )

        if occurrence_count > 1:
            raise ToolError(
                "Text to replace occurs more than once"
            )

        updated = contents.replace(
            old,
            new,
            1,
        )

        path.write_text(
            updated,
            encoding="utf-8",
        )

        return ToolResult(
            ok=True,
            output=f"Updated {arguments['path']}",
        )

    return ToolDefinition(
        name="replace_text",
        description=(
            "Replace exactly one occurrence of text in a UTF-8 "
            "file inside the workspace. The old text must occur "
            "exactly once."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "minLength": 1,
                },
                "old": {
                    "type": "string",
                    "minLength": 1,
                },
                "new": {
                    "type": "string",
                },
            },
            "required": [
                "path",
                "old",
                "new",
            ],
            "additionalProperties": False,
        },
        handler=replace_text_handler,
    )