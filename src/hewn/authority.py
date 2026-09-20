from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from hewn.tools import ToolCall


class Capability(str, Enum):
    """Operational capabilities that Hewn may grant to an agent session."""

    REPOSITORY_READ = "repository_read"
    REPOSITORY_WRITE = "repository_write"
    APPROVED_CHECK = "approved_check"


@dataclass(frozen=True)
class AuthorityGrant:
    """Immutable capabilities granted by the trusted Hewn runtime."""

    repository_read: bool = False
    repository_write: bool = False
    approved_checks: bool = False


@dataclass(frozen=True)
class AuthorityDecision:
    """Deterministic authorization result for one proposed tool call."""

    allowed: bool
    capability: Capability | None
    reason: str


_READ_TOOLS = frozenset(
    {
        "list_directory",
        "read_file",
        "search_text",
        "find_symbol",
        "repository_map",
    }
)

_WRITE_TOOLS = frozenset(
    {
        "replace_text",
    }
)

_CHECK_TOOLS = frozenset(
    {
        "run_check",
    }
)


def classify_tool_capability(tool_name: str) -> Capability | None:
    """Map a known Hewn tool to the capability required to execute it."""

    if tool_name in _READ_TOOLS:
        return Capability.REPOSITORY_READ

    if tool_name in _WRITE_TOOLS:
        return Capability.REPOSITORY_WRITE

    if tool_name in _CHECK_TOOLS:
        return Capability.APPROVED_CHECK

    return None


class AuthorityPolicy:
    """Authorize tool calls against an immutable runtime capability grant."""

    def __init__(self, grant: AuthorityGrant) -> None:
        self._grant = grant

    @property
    def grant(self) -> AuthorityGrant:
        return self._grant

    def authorize(self, call: ToolCall) -> AuthorityDecision:
        capability = classify_tool_capability(call.name)

        if capability is None:
            return AuthorityDecision(
                allowed=False,
                capability=None,
                reason=f"No authority classification exists for tool: {call.name}",
            )

        if capability is Capability.REPOSITORY_READ:
            allowed = self._grant.repository_read
        elif capability is Capability.REPOSITORY_WRITE:
            allowed = self._grant.repository_write
        else:
            allowed = self._grant.approved_checks

        if allowed:
            return AuthorityDecision(
                allowed=True,
                capability=capability,
                reason=f"Authority grant permits capability: {capability.value}",
            )

        return AuthorityDecision(
            allowed=False,
            capability=capability,
            reason=f"Authority grant denies capability: {capability.value}",
        )