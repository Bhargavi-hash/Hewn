from __future__ import annotations

import json
from typing import Any

from hewn.action_normalizer import normalize_model_response
from hewn.models import FinalResponse, ModelResponse
from hewn.tools import ToolCall


class ModelProtocolError(ValueError):
    def __init__(
        self,
        message: str,
        *,
        raw_response: str,
    ) -> None:
        super().__init__(message)
        self.raw_response = raw_response

def parse_or_normalize_model_response(
    text: str,
) -> ModelResponse:
    """
    Parse the canonical Hewn protocol first.

    If strict parsing fails, attempt only allowlisted deterministic
    normalization. The canonical parser itself remains strict.
    """

    try:
        return parse_model_response(text)
    except ModelProtocolError:
        normalized = normalize_model_response(text)

        if normalized.response is not None:
            return normalized.response

        raise

def parse_model_response(text: str) -> ModelResponse:
    try:
        payload: Any = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ModelProtocolError(
            "Model response is not valid JSON",
            raw_response=text,
        ) from exc

    if not isinstance(payload, dict):
        raise ModelProtocolError(
            "Model response must be a JSON object",
            raw_response=text,
        )

    response_type = payload.get("type")

    if response_type == "final":
        return _parse_final_response(
            payload,
            raw_response=text,
        )

    if response_type == "tool_call":
        return _parse_tool_call(
            payload,
            raw_response=text,
        )

    raise ModelProtocolError(
        f"Unknown model response type: {response_type!r}",
        raw_response=text,
    )


def _parse_final_response(
    payload: dict[str, Any],
    *,
    raw_response: str,
) -> FinalResponse:
    if set(payload) != {"type", "text"}:
        raise ModelProtocolError(
            "Final response must contain exactly 'type' and 'text'",
            raw_response=raw_response,
        )

    text = payload["text"]

    if not isinstance(text, str):
        raise ModelProtocolError(
            "Final response 'text' must be a string",
            raw_response=raw_response,
        )

    return FinalResponse(text=text)


def _parse_tool_call(
    payload: dict[str, Any],
    *,
    raw_response: str,
) -> ToolCall:
    if set(payload) != {"type", "name", "arguments"}:
        raise ModelProtocolError(
            "Tool call must contain exactly "
            "'type', 'name', and 'arguments'",
            raw_response=raw_response,
        )

    name = payload["name"]
    arguments = payload["arguments"]

    if not isinstance(name, str):
        raise ModelProtocolError(
            "Tool call 'name' must be a string",
            raw_response=raw_response,
        )

    if not isinstance(arguments, dict):
        raise ModelProtocolError(
            "Tool call 'arguments' must be an object",
            raw_response=raw_response,
        )

    return ToolCall(
        name=name,
        arguments=arguments,
    )