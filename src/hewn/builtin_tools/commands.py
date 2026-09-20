from __future__ import annotations

import sys
from typing import Any

from hewn.execution import (
    DirectExecutionBackend,
    ExecutionError,
    ExecutionTimeoutError,
    ProcessExecutionBackend,
)
from hewn.tools import ToolDefinition, ToolError, ToolResult
from hewn.workspace import Workspace

DEFAULT_COMMAND_TIMEOUT_SECONDS = 60.0
DEFAULT_COMMAND_OUTPUT_LIMIT = 12_000


CHECK_COMMANDS = {
    "tests": [sys.executable, "-B", "-m", "pytest", "-q"],
    "lint": ["ruff", "check", "."],
    "types": ["mypy", "src", "tests"],
}


def make_run_check_tool(
    workspace: Workspace,
    *,
    timeout_seconds: float = DEFAULT_COMMAND_TIMEOUT_SECONDS,
    output_limit: int = DEFAULT_COMMAND_OUTPUT_LIMIT,
    execution_backend: ProcessExecutionBackend | None = None,
) -> ToolDefinition:
    if timeout_seconds <= 0:
        raise ValueError(
            "timeout_seconds must be greater than zero"
        )

    if output_limit < 1:
        raise ValueError(
            "output_limit must be at least 1"
        )

    backend = execution_backend or DirectExecutionBackend()

    def run_check_handler(
        arguments: dict[str, Any],
    ) -> ToolResult:
        check = arguments["check"]
        command = CHECK_COMMANDS[check]

        try:
            completed = backend.run(
                command,
                workspace=workspace,
                timeout_seconds=timeout_seconds,
            )
        except ExecutionTimeoutError as exc:
            raise ToolError(
                f"Check timed out after {timeout_seconds:g} seconds"
            ) from exc
        except ExecutionError as exc:
            raise ToolError(str(exc)) from exc

        output = _combine_output(
            completed.stdout,
            completed.stderr,
        )

        output = _truncate_output(
            output,
            output_limit=output_limit,
        )

        if completed.returncode != 0:
            return ToolResult(
                ok=False,
                output=output,
                error=(
                    "Check failed with exit code "
                    f"{completed.returncode}"
                ),
            )

        return ToolResult(
            ok=True,
            output=output,
        )

    return ToolDefinition(
        name="run_check",
        description=(
            "Run an approved development check inside the "
            "workspace. Available checks: tests, lint, types."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "check": {
                    "type": "string",
                    "enum": sorted(CHECK_COMMANDS),
                }
            },
            "required": ["check"],
            "additionalProperties": False,
        },
        handler=run_check_handler,
    )


def _combine_output(
    stdout: str,
    stderr: str,
) -> str:
    parts = [
        part.strip()
        for part in (stdout, stderr)
        if part.strip()
    ]

    return "\n".join(parts)


def _truncate_output(
    output: str,
    *,
    output_limit: int,
) -> str:
    if len(output) <= output_limit:
        return output

    omitted = len(output) - output_limit

    return (
        output[:output_limit]
        + f"\n... {omitted} characters not shown"
    )