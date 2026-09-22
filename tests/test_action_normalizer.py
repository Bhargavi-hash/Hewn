from __future__ import annotations

import pytest

from hewn.action_normalizer import normalize_model_response
from hewn.model_protocol import (
    ModelProtocolError,
    parse_model_response,
    parse_or_normalize_model_response,
)
from hewn.tools import ToolCall


def test_normalizes_action_file_read_file() -> None:
    raw = (
        '{"action":"read_file",'
        '"file":"src/example.py"}'
    )

    result = normalize_model_response(raw)

    assert result.response == ToolCall(
        name="read_file",
        arguments={"path": "src/example.py"},
    )
    assert result.rule == "action_file_to_read_file"


def test_normalizes_tool_args_read_file() -> None:
    raw = (
        '{"tool":"read_file",'
        '"args":["src/example.py"]}'
    )

    result = normalize_model_response(raw)

    assert result.response == ToolCall(
        name="read_file",
        arguments={"path": "src/example.py"},
    )
    assert result.rule == "tool_args_to_read_file"


def test_canonical_parser_remains_strict() -> None:
    raw = (
        '{"action":"read_file",'
        '"file":"src/example.py"}'
    )

    with pytest.raises(ModelProtocolError):
        parse_model_response(raw)


def test_parse_or_normalize_preserves_canonical_protocol() -> None:
    raw = (
        '{"type":"tool_call","name":"read_file",'
        '"arguments":{"path":"src/example.py"}}'
    )

    response = parse_or_normalize_model_response(raw)

    assert response == ToolCall(
        name="read_file",
        arguments={"path": "src/example.py"},
    )


def test_parse_or_normalize_recovers_allowlisted_shape() -> None:
    raw = (
        '{"action":"read_file",'
        '"file":"src/example.py"}'
    )

    response = parse_or_normalize_model_response(raw)

    assert response == ToolCall(
        name="read_file",
        arguments={"path": "src/example.py"},
    )


@pytest.mark.parametrize(
    "raw",
    [
        '{"action":"run_check"}',
        '{"action":"replace_text","text":"change something"}',
        '{"tool":"read_file","args":[]}',
        '{"tool":"read_file","args":["a.py","b.py"]}',
        '{"tool":"replace_text","args":["a.py"]}',
        '{"input":"src/example.py","tool":"read_file"}',
        '{"action":"read_file","file":42}',
        '["read_file","src/example.py"]',
        'not json',
    ],
)
def test_ambiguous_or_invalid_outputs_are_rejected(
    raw: str,
) -> None:
    result = normalize_model_response(raw)

    assert result.response is None
    assert result.rule is None

    with pytest.raises(ModelProtocolError):
        parse_or_normalize_model_response(raw)
