
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from jsonschema import ValidationError, validate


class ToolError(Exception):
    """Expected failure while executing a tool."""

# This isn't a class or a function.
# It's a type alias.
# We are giving a name to a particular shape of function.
ToolHandler = Callable[[dict[str, Any]], "ToolResult"] # A function that takes a dictionary of arguments and returns a ToolResult.

# This is the complete description of one available capability.
# ToolDefinition = Tool's ID card + Instruction Manual + Implementation Pointer
@dataclass(frozen=True)
class ToolDefinition:
    name: str                   # Name exposed to the model. Example: read_file
    description: str            # Model needs to know what the tool is for. A weak description might cause a small model to choose the wrong tool.
    input_schema: dict[str, Any] # Describes what arguments are legal
    handler: ToolHandler        # The actual python function that will be called when the model chooses this tool. It must match the input_schema.

# A request to execute a tool. This is the input to the ToolExecutor.
@dataclass(frozen=True)
class ToolCall:
    name: str
    arguments: dict[str, Any]


@dataclass(frozen=True)
class ToolResult:
    ok: bool
    output: str | None = None
    error: str | None = None

# Hewn's Tool Catalog. This is where all the tools are registered and looked up by name.
class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, ToolDefinition] = {}

    def register(self, tool: ToolDefinition) -> None:
        if tool.name in self._tools:
            raise ValueError(f"Tool already registered: {tool.name}")

        self._tools[tool.name] = tool

    def get(self, name: str) -> ToolDefinition | None:
        return self._tools.get(name)

    def definitions(self) -> list[ToolDefinition]:
        return list(self._tools.values())

# ToolHandler = Employee who knows how to do one job
# ToolExecutor = Manager who knows how to find the right employee and give them the right job to do.
class ToolExecutor:
    def __init__(self, registry: ToolRegistry) -> None:
        self._registry = registry

    def execute(self, call: ToolCall) -> ToolResult:
        tool = self._registry.get(call.name)

        if tool is None:
            return ToolResult(
                ok=False,
                error=f"Unknown tool: {call.name}",
            )

        try:
            validate(
                instance=call.arguments,    # Actual Data I want to chec
                schema=tool.input_schema,   # Check it against this contract
            )
        except ValidationError as exc:
            return ToolResult(
                ok=False,
                error=f"Invalid tool arguments: {exc.message}",
            )

        try:
            return tool.handler(call.arguments)
        except ToolError as exc:
            return ToolResult(
                ok=False,
                error=str(exc),
            )