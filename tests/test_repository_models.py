from pathlib import PurePosixPath

import pytest

from hewn.repository.models import (
    Import,
    SourceFile,
    SourceLocation,
    Symbol,
    SymbolKind,
)


def test_source_location_accepts_repository_relative_path() -> None:
    location = SourceLocation(
        path=PurePosixPath("src/hewn/agent.py"),
        start_line=10,
        end_line=20,
    )

    assert location.path == PurePosixPath("src/hewn/agent.py")
    assert location.start_line == 10
    assert location.end_line == 20


def test_source_location_rejects_absolute_path() -> None:
    with pytest.raises(
        ValueError,
        match="repository-relative",
    ):
        SourceLocation(
            path=PurePosixPath("/tmp/agent.py"),
            start_line=1,
            end_line=1,
        )


def test_source_location_rejects_invalid_line_range() -> None:
    with pytest.raises(
        ValueError,
        match="end_line",
    ):
        SourceLocation(
            path=PurePosixPath("agent.py"),
            start_line=10,
            end_line=5,
        )


def test_symbol_represents_qualified_method() -> None:
    symbol = Symbol(
        name="run",
        kind=SymbolKind.METHOD,
        qualified_name="Agent.run",
        location=SourceLocation(
            path=PurePosixPath("src/hewn/agent.py"),
            start_line=20,
            end_line=40,
        ),
    )

    assert symbol.name == "run"
    assert symbol.qualified_name == "Agent.run"
    assert symbol.kind is SymbolKind.METHOD


def test_import_represents_from_import() -> None:
    imported = Import(
        module="hewn.tools",
        name="ToolExecutor",
        alias=None,
        location=SourceLocation(
            path=PurePosixPath("src/hewn/agent.py"),
            start_line=5,
            end_line=5,
        ),
    )

    assert imported.module == "hewn.tools"
    assert imported.name == "ToolExecutor"


def test_source_file_contains_structural_information() -> None:
    location = SourceLocation(
        path=PurePosixPath("src/hewn/tools.py"),
        start_line=100,
        end_line=150,
    )

    symbol = Symbol(
        name="ToolExecutor",
        kind=SymbolKind.CLASS,
        qualified_name="ToolExecutor",
        location=location,
    )

    source_file = SourceFile(
        path=PurePosixPath("src/hewn/tools.py"),
        language="python",
        symbols=(symbol,),
        imports=(),
    )

    assert source_file.language == "python"
    assert source_file.symbols == (symbol,)

def test_source_location_rejects_parent_traversal() -> None:
    with pytest.raises(
        ValueError,
        match="repository-relative",
    ):
        SourceLocation(
            path=PurePosixPath("../../outside.py"),
            start_line=1,
            end_line=1,
        )