from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from hewn.tools import ToolCall, ToolDefinition


@dataclass(frozen=True)
class FinalResponse:
    text: str

# Model invocation can produce exactly one of the ToolCall or Final responses
ModelResponse = ToolCall | FinalResponse

@dataclass(frozen=True)
class Message:
    role: str
    content: str

class Model(Protocol):
    def respond(
        self,
        messages: list[Message],
        tools: list[ToolDefinition],
    ) -> ModelResponse:
        ...

@dataclass
class EchoModel:
    """Minimal deterministic model used to verify application wiring."""

    def respond(
        self,
        messages: list[Message],
        tools: list[ToolDefinition],
    ) -> ModelResponse:
        del tools

        latest = messages[-1]

        return FinalResponse(
            text=f"Echo: {latest.content}",
        )