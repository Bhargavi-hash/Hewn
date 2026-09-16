from __future__ import annotations

import json
from typing import Any

from hewn.models import FinalResponse, ModelResponse
from hewn.tools import ToolCall


class ModelProtocolError(ValueError):
    """Model output does not satisfy the Hewn response protocol."""


def parse_model_response(text: str) -> ModelResponse:
    try:
        payload: Any = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ModelProtocolError(
            "Model response is not valid JSON"
        ) from exc

    if not isinstance(payload, dict):
        raise ModelProtocolError(
            "Model response must be a JSON object"
        )

    response_type = payload.get("type")

    if response_type == "final":
        return _parse_final_response(payload)

    if response_type == "tool_call":
        return _parse_tool_call(payload)

    raise ModelProtocolError(
        f"Unknown model response type: {response_type!r}"
    )


def _parse_final_response(
    payload: dict[str, Any],
) -> FinalResponse:
    if set(payload) != {"type", "text"}:
        raise ModelProtocolError(
            "Final response must contain exactly 'type' and 'text'"
        )

    text = payload["text"]

    if not isinstance(text, str):
        raise ModelProtocolError(
            "Final response 'text' must be a string"
        )

    return FinalResponse(text=text)


def _parse_tool_call(
    payload: dict[str, Any],
) -> ToolCall:
    if set(payload) != {"type", "name", "arguments"}:
        raise ModelProtocolError(
            "Tool call must contain exactly "
            "'type', 'name', and 'arguments'"
        )

    name = payload["name"]
    arguments = payload["arguments"]

    if not isinstance(name, str):
        raise ModelProtocolError(
            "Tool call 'name' must be a string"
        )

    if not isinstance(arguments, dict):
        raise ModelProtocolError(
            "Tool call 'arguments' must be an object"
        )

    return ToolCall(
        name=name,
        arguments=arguments,
    )