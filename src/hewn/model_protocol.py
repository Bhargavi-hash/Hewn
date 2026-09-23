from __future__ import annotations

import json
from dataclasses import dataclass
from enum import Enum
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


class ParseSource(Enum):
    CANONICAL = "canonical"
    NORMALIZED = "normalized"


@dataclass(frozen=True)
class ParsedModelResponse:
    response: ModelResponse
    source: ParseSource
    normalization_rule: str | None = None

    def __post_init__(self) -> None:
        if self.source is ParseSource.CANONICAL:
            if self.normalization_rule is not None:
                raise ValueError(
                    "Canonical responses cannot have a normalization rule"
                )
            return

        if self.normalization_rule is None:
            raise ValueError(
                "Normalized responses must record their normalization rule"
            )


def serialize_model_response(
    response: ModelResponse,
) -> str:
    """
    Serialize one typed model response using Hewn's canonical wire protocol.

    Training data, evaluators, prompts, and inference code should use this
    function rather than independently constructing protocol JSON.
    """
    if isinstance(response, FinalResponse):
        payload: dict[str, Any] = {
            "type": "final",
            "text": response.text,
        }
    elif isinstance(response, ToolCall):
        payload = {
            "type": "tool_call",
            "name": response.name,
            "arguments": response.arguments,
        }
    else:
        raise TypeError(
            "Unsupported model response: "
            f"{type(response).__name__}"
        )

    return json.dumps(
        payload,
        separators=(",", ":"),
        sort_keys=True,
    )


def parse_model_response_with_provenance(
    text: str,
) -> ParsedModelResponse:
    """
    Parse canonical Hewn protocol first.

    If strict parsing fails, attempt only allowlisted deterministic
    normalization. The result records whether the model emitted the
    production protocol natively or required normalization.
    """
    try:
        response = parse_model_response(text)
    except ModelProtocolError:
        normalized = normalize_model_response(text)

        if normalized.response is None:
            raise

        if normalized.rule is None:
            raise RuntimeError(
                "Normalizer returned a response without provenance"
            )

        return ParsedModelResponse(
            response=normalized.response,
            source=ParseSource.NORMALIZED,
            normalization_rule=normalized.rule,
        )

    return ParsedModelResponse(
        response=response,
        source=ParseSource.CANONICAL,
    )


def parse_or_normalize_model_response(
    text: str,
) -> ModelResponse:
    """
    Compatibility API returning only the typed response.

    Callers that need protocol-compliance telemetry should use
    parse_model_response_with_provenance().
    """
    return parse_model_response_with_provenance(text).response


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
