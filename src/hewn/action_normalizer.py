from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from hewn.models import ModelResponse
from hewn.tools import ToolCall


@dataclass(frozen=True)
class NormalizationResult:
    """
    Result of attempting to recover a canonical Hewn response.

    `response` is None when the raw output cannot be normalized without
    guessing or inventing information.
    """

    response: ModelResponse | None
    rule: str | None


def normalize_model_response(text: str) -> NormalizationResult:
    """
    Recover a small allowlisted set of semantically unambiguous model outputs.

    This is intentionally not a general JSON repair layer. It must never invent
    missing arguments, infer an edit, or choose a tool on the model's behalf.
    """

    try:
        payload: Any = json.loads(text)
    except json.JSONDecodeError:
        return NormalizationResult(
            response=None,
            rule=None,
        )

    if not isinstance(payload, dict):
        return NormalizationResult(
            response=None,
            rule=None,
        )

    result = _normalize_action_shape(payload)
    if result is not None:
        return result

    result = _normalize_tool_shape(payload)
    if result is not None:
        return result

    return NormalizationResult(
        response=None,
        rule=None,
    )


def _normalize_action_shape(
    payload: dict[str, Any],
) -> NormalizationResult | None:
    """
    Normalize forms such as:

        {"action": "read_file", "file": "src/a.py"}

    Only exact allowlisted key sets are accepted.
    """

    if set(payload) == {"action", "file"}:
        action = payload["action"]
        file_path = payload["file"]

        if (
            action == "read_file"
            and isinstance(file_path, str)
        ):
            return NormalizationResult(
                response=ToolCall(
                    name="read_file",
                    arguments={"path": file_path},
                ),
                rule="action_file_to_read_file",
            )

    return None


def _normalize_tool_shape(
    payload: dict[str, Any],
) -> NormalizationResult | None:
    """
    Normalize forms such as:

        {"tool": "read_file", "args": ["src/a.py"]}

    Again, only forms whose meaning is mechanically unique are accepted.
    """

    if set(payload) == {"tool", "args"}:
        tool = payload["tool"]
        args = payload["args"]

        if (
            tool == "read_file"
            and isinstance(args, list)
            and len(args) == 1
            and isinstance(args[0], str)
        ):
            return NormalizationResult(
                response=ToolCall(
                    name="read_file",
                    arguments={"path": args[0]},
                ),
                rule="tool_args_to_read_file",
            )

    return None
