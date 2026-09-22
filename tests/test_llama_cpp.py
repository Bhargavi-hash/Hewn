import json
from typing import Self
from urllib.error import HTTPError, URLError

import pytest
from _pytest.monkeypatch import MonkeyPatch

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

def test_system_prompt_appends_additional_instruction() -> None:
    model = LlamaCppModel(
        additional_system_instruction="EXPERIMENTAL INSTRUCTION"
    )

    prompt = model._build_system_prompt([])

    assert prompt.endswith("EXPERIMENTAL INSTRUCTION")

def test_system_prompt_omits_extra_separator_by_default() -> None:
    default_model = LlamaCppModel()
    explicit_empty_model = LlamaCppModel(
        additional_system_instruction=None
    )

    assert (
        default_model._build_system_prompt([])
        == explicit_empty_model._build_system_prompt([])
    )

def test_check_available_succeeds(
    monkeypatch: MonkeyPatch,
) -> None:
    class FakeResponse:
        def __enter__(self) -> Self:
            return self
    
        def __exit__(
            self,
            exc_type: object,
            exc_value: object,
            traceback: object,
        ) -> None:
            del exc_type, exc_value, traceback

    def fake_urlopen(
        request: object,
        *,
        timeout: float,
    ) -> FakeResponse:
        del request
        assert timeout == 2.0
        return FakeResponse()

    monkeypatch.setattr(
        "hewn.llama_cpp.urlopen",
        fake_urlopen,
    )

    LlamaCppModel().check_available()


def test_check_available_reports_unreachable_server(
    monkeypatch: MonkeyPatch,
) -> None:
    def fake_urlopen(
        request: object,
        *,
        timeout: float,
    ) -> object:
        del request, timeout
        raise URLError("connection refused")

    monkeypatch.setattr(
        "hewn.llama_cpp.urlopen",
        fake_urlopen,
    )

    with pytest.raises(
        ModelError,
        match="Could not reach llama.cpp: connection refused",
    ):
        LlamaCppModel().check_available()


def test_check_available_reports_http_error(
    monkeypatch: MonkeyPatch,
) -> None:
    def fake_urlopen(
        request: object,
        *,
        timeout: float,
    ) -> object:
        del request, timeout
        raise HTTPError(
            url="http://127.0.0.1:8080/health",
            code=503,
            msg="Service Unavailable",
            hdrs=None,
            fp=None,
        )

    monkeypatch.setattr(
        "hewn.llama_cpp.urlopen",
        fake_urlopen,
    )

    with pytest.raises(
        ModelError,
        match="llama.cpp health check returned HTTP 503",
    ):
        LlamaCppModel().check_available()