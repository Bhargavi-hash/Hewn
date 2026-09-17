from pathlib import PurePosixPath

from hewn.repository.models import SymbolKind
from hewn.repository.python_parser import (
    parse_python_source,
)


def test_parser_records_function_signature() -> None:
    source_file = parse_python_source(
        PurePosixPath("src/example.py"),
        (
            "def execute("
            "call: ToolCall, "
            "limit: int = 5"
            ") -> ToolResult:\n"
            "    pass\n"
        ),
    )

    symbol = source_file.symbols[0]

    assert symbol.kind is SymbolKind.FUNCTION
    assert symbol.signature == (
        "execute(call: ToolCall, "
        "limit: int=5) -> ToolResult"
    )


def test_parser_records_method_signature() -> None:
    source_file = parse_python_source(
        PurePosixPath("src/example.py"),
        (
            "class CompletionPolicy:\n"
            "    def can_finish(self) -> bool:\n"
            "        return True\n"
        ),
    )

    method = source_file.symbols[1]

    assert method.kind is SymbolKind.METHOD
    assert (
        method.qualified_name
        == "CompletionPolicy.can_finish"
    )
    assert (
        method.signature
        == "can_finish(self) -> bool"
    )


def test_parser_records_async_signature() -> None:
    source_file = parse_python_source(
        PurePosixPath("src/example.py"),
        (
            "async def respond("
            "messages: list[str]"
            ") -> Response:\n"
            "    pass\n"
        ),
    )

    symbol = source_file.symbols[0]

    assert symbol.kind is SymbolKind.FUNCTION
    assert symbol.signature == (
        "respond(messages: list[str]) -> Response"
    )


def test_class_has_no_signature() -> None:
    source_file = parse_python_source(
        PurePosixPath("src/example.py"),
        (
            "class Workspace:\n"
            "    pass\n"
        ),
    )

    symbol = source_file.symbols[0]

    assert symbol.kind is SymbolKind.CLASS
    assert symbol.signature is None