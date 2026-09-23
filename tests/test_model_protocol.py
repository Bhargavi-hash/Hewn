import pytest

from hewn.model_protocol import (
    ModelProtocolError,
    parse_model_response,
)
from hewn.models import FinalResponse
from hewn.tools import ToolCall


def test_parse_final_response() -> None:
    response = parse_model_response(
        '{"type":"final","text":"Done."}'
    )

    assert response == FinalResponse(text="Done.")


def test_parse_tool_call() -> None:
    response = parse_model_response(
        
            '{"type":"tool_call",'
            '"name":"read_file",'
            '"arguments":{"path":"README.md"}}'
        
    )

    assert response == ToolCall(
        name="read_file",
        arguments={"path": "README.md"},
    )


def test_reject_invalid_json() -> None:
    with pytest.raises(
        ModelProtocolError,
        match="not valid JSON",
    ):
        parse_model_response("I think I should search first.")


def test_reject_unknown_response_type() -> None:
    with pytest.raises(
        ModelProtocolError,
        match="Unknown model response type",
    ):
        parse_model_response(
            '{"type":"something_else"}'
        )


def test_reject_extra_final_fields() -> None:
    with pytest.raises(
        ModelProtocolError,
        match="exactly",
    ):
        parse_model_response(
            
                '{"type":"final",'
                '"text":"Done.",'
                '"extra":true}'
            
        )


def test_reject_non_object_response() -> None:
    with pytest.raises(
        ModelProtocolError,
        match="JSON object",
    ):
        parse_model_response('["final", "Done."]')

def test_protocol_error_preserves_raw_response() -> None:
    raw_response = "I should inspect calculator.py first."

    with pytest.raises(ModelProtocolError) as exc_info:
        parse_model_response(raw_response)

    assert exc_info.value.raw_response == raw_response

def test_structured_protocol_error_preserves_raw_response() -> None:
    raw_response = (
        '{"type":"tool_call","name":123,"arguments":{}}'
    )

    with pytest.raises(ModelProtocolError) as exc_info:
        parse_model_response(raw_response)

    assert exc_info.value.raw_response == raw_response

def test_serialize_tool_call_uses_canonical_protocol() -> None:
    from hewn.model_protocol import serialize_model_response

    encoded = serialize_model_response(
        ToolCall(
            name="read_file",
            arguments={"path": "README.md"},
        )
    )

    assert encoded == (
        '{"arguments":{"path":"README.md"},'
        '"name":"read_file","type":"tool_call"}'
    )

    assert parse_model_response(encoded) == ToolCall(
        name="read_file",
        arguments={"path": "README.md"},
    )


def test_serialize_final_uses_canonical_protocol() -> None:
    from hewn.model_protocol import serialize_model_response

    encoded = serialize_model_response(
        FinalResponse(text="Done.")
    )

    assert encoded == '{"text":"Done.","type":"final"}'
    assert parse_model_response(encoded) == FinalResponse(
        text="Done."
    )


def test_canonical_parse_records_canonical_provenance() -> None:
    from hewn.model_protocol import (
        ParseSource,
        parse_model_response_with_provenance,
    )

    parsed = parse_model_response_with_provenance(
        '{"type":"tool_call","name":"read_file",'
        '"arguments":{"path":"README.md"}}'
    )

    assert parsed.response == ToolCall(
        name="read_file",
        arguments={"path": "README.md"},
    )
    assert parsed.source is ParseSource.CANONICAL
    assert parsed.normalization_rule is None


def test_normalized_parse_records_rule_provenance() -> None:
    from hewn.model_protocol import (
        ParseSource,
        parse_model_response_with_provenance,
    )

    parsed = parse_model_response_with_provenance(
        '{"action":"read_file","file":"README.md"}'
    )

    assert parsed.response == ToolCall(
        name="read_file",
        arguments={"path": "README.md"},
    )
    assert parsed.source is ParseSource.NORMALIZED
    assert (
        parsed.normalization_rule
        == "action_file_to_read_file"
    )


def test_serializer_round_trip_preserves_tool_call() -> None:
    from hewn.model_protocol import serialize_model_response

    original = ToolCall(
        name="replace_text",
        arguments={
            "path": "example.py",
            "old": "x = 1",
            "new": "x = 2",
        },
    )

    encoded = serialize_model_response(original)
    decoded = parse_model_response(encoded)

    assert decoded == original
