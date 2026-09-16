import json

import pytest

from hewn.llama_cpp import LlamaCppModel
from hewn.models import Message, ModelError
from hewn.tools import ToolDefinition, ToolResult


def make_example_tool() -> ToolDefinition:
    return ToolDefinition(
        name="search_text",
        description="Search repository text.",
        input_schema={
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                }
            },
            "required": ["query"],
            "additionalProperties": False,
        },
        handler=lambda arguments: ToolResult(
            ok=True,
            output=str(arguments),
        ),
    )


def test_build_messages_contains_tools() -> None:
    model = LlamaCppModel()

    messages = model._build_messages(
        [Message(role="user", content="Find ToolExecutor.")],
        [make_example_tool()],
    )

    assert messages[0]["role"] == "system"
    assert "search_text" in messages[0]["content"]
    assert '"query"' in messages[0]["content"]

    assert messages[1] == {
        "role": "user",
        "content": "Find ToolExecutor.",
    }


def test_extract_content() -> None:
    model = LlamaCppModel()

    body = json.dumps(
        {
            "choices": [
                {
                    "message": {
                        "content": (
                            '{"type":"final","text":"Done."}'
                        )
                    }
                }
            ]
        }
    )

    assert model._extract_content(body) == (
        '{"type":"final","text":"Done."}'
    )


def test_extract_content_rejects_invalid_response() -> None:
    model = LlamaCppModel()

    with pytest.raises(
        ModelError,
        match="invalid chat response",
    ):
        model._extract_content("{}")