from pathlib import PurePosixPath

import pytest

from hewn.repository.models import SymbolKind
from hewn.repository.python_parser import (
    PythonParseError,
    parse_python_source,
)


def test_parse_python_source_extracts_class_and_method() -> None:
    source = """\
class Agent:
    def run(self) -> None:
        pass
"""

    parsed = parse_python_source(
        PurePosixPath("src/hewn/agent.py"),
        source,
    )

    assert len(parsed.symbols) == 2

    agent, run = parsed.symbols

    assert agent.name == "Agent"
    assert agent.qualified_name == "Agent"
    assert agent.kind is SymbolKind.CLASS
    assert agent.location.start_line == 1
    assert agent.location.end_line == 3

    assert run.name == "run"
    assert run.qualified_name == "Agent.run"
    assert run.kind is SymbolKind.METHOD
    assert run.location.start_line == 2


def test_parse_python_source_extracts_top_level_function() -> None:
    parsed = parse_python_source(
        PurePosixPath("src/hewn/example.py"),
        """\
def calculate() -> int:
    return 42
""",
    )

    assert len(parsed.symbols) == 1

    symbol = parsed.symbols[0]

    assert symbol.name == "calculate"
    assert symbol.qualified_name == "calculate"
    assert symbol.kind is SymbolKind.FUNCTION


def test_parse_python_source_extracts_async_function() -> None:
    parsed = parse_python_source(
        PurePosixPath("worker.py"),
        """\
async def process() -> None:
    pass
""",
    )

    assert parsed.symbols[0].name == "process"
    assert parsed.symbols[0].kind is SymbolKind.FUNCTION


def test_parse_python_source_extracts_imports() -> None:
    parsed = parse_python_source(
        PurePosixPath("src/hewn/agent.py"),
        """\
import json
import pathlib as paths
from hewn.tools import ToolExecutor
from hewn.models import ToolCall as Call
""",
    )

    assert len(parsed.imports) == 4

    assert parsed.imports[0].module == "json"
    assert parsed.imports[0].name is None
    assert parsed.imports[0].alias is None

    assert parsed.imports[1].module == "pathlib"
    assert parsed.imports[1].alias == "paths"

    assert parsed.imports[2].module == "hewn.tools"
    assert parsed.imports[2].name == "ToolExecutor"

    assert parsed.imports[3].module == "hewn.models"
    assert parsed.imports[3].name == "ToolCall"
    assert parsed.imports[3].alias == "Call"


def test_parse_python_source_preserves_relative_import() -> None:
    parsed = parse_python_source(
        PurePosixPath("src/hewn/example.py"),
        "from .tools import ToolExecutor\n",
    )

    imported = parsed.imports[0]

    assert imported.module == ".tools"
    assert imported.name == "ToolExecutor"


def test_parse_python_source_qualifies_method() -> None:
    parsed = parse_python_source(
        PurePosixPath("example.py"),
        """\
class First:
    def run(self) -> None:
        pass

class Second:
    def run(self) -> None:
        pass
""",
    )

    run_symbols = [
        symbol
        for symbol in parsed.symbols
        if symbol.name == "run"
    ]

    assert [symbol.qualified_name for symbol in run_symbols] == [
        "First.run",
        "Second.run",
    ]


def test_parse_python_source_does_not_index_nested_function() -> None:
    parsed = parse_python_source(
        PurePosixPath("example.py"),
        """\
def outer() -> None:
    def inner() -> None:
        pass

    inner()
""",
    )

    assert [symbol.qualified_name for symbol in parsed.symbols] == [
        "outer"
    ]


def test_parse_python_source_rejects_invalid_python() -> None:
    with pytest.raises(
        PythonParseError,
        match="Could not parse",
    ):
        parse_python_source(
            PurePosixPath("broken.py"),
            "def broken(\n",
        )