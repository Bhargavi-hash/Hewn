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