from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Protocol

from jsonschema import ValidationError, validate


class ToolError(Exception):
    """Expected failure while executing a tool."""


ToolHandler = Callable[[dict[str, Any]], "ToolResult"]


@dataclass(frozen=True)
class ToolDefinition:
    """Complete description and implementation of one model-visible tool."""

    name: str
    description: str
    input_schema: dict[str, Any]
    handler: ToolHandler


@dataclass(frozen=True)
class ToolCall:
    """A model proposal to execute one tool."""

    name: str
    arguments: dict[str, Any]


@dataclass(frozen=True)
class ToolResult:
    """Result returned to the agent after attempting a tool action."""

    ok: bool
    output: str | None = None
    error: str | None = None


class AuthorizationDecision(Protocol):
    """Minimum decision interface required by ToolExecutor."""

    @property
    def allowed(self) -> bool: ...

    @property
    def reason(self) -> str: ...


class ToolAuthorityPolicy(Protocol):
    """Authorization boundary used by ToolExecutor."""

    def authorize(self, call: ToolCall) -> AuthorizationDecision: ...


class ToolRegistry:
    """Catalog of tools available to the agent."""

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


class ToolExecutor:
    """Validate, authorize, and execute model-proposed tool calls."""

    def __init__(
        self,
        registry: ToolRegistry,
        *,
        authority_policy: ToolAuthorityPolicy | None = None,
    ) -> None:
        self._registry = registry
        self._authority_policy = authority_policy

    def execute(self, call: ToolCall) -> ToolResult:
        tool = self._registry.get(call.name)

        if tool is None:
            return ToolResult(
                ok=False,
                error=f"Unknown tool: {call.name}",
            )

        try:
            validate(
                instance=call.arguments,
                schema=tool.input_schema,
            )
        except ValidationError as exc:
            return ToolResult(
                ok=False,
                error=f"Invalid tool arguments: {exc.message}",
            )

        if self._authority_policy is not None:
            decision = self._authority_policy.authorize(call)

            if not decision.allowed:
                return ToolResult(
                    ok=False,
                    error=f"Authority denied: {decision.reason}",
                )

        try:
            return tool.handler(call.arguments)
        except ToolError as exc:
            return ToolResult(
                ok=False,
                error=str(exc),
            )