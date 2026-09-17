from pathlib import Path, PurePosixPath

import pytest

from hewn.context.source import (
    SourceEvidenceError,
    build_bounded_source_document,
    build_mixed_document,
    build_signature_document,
    build_source_document,
    resolve_document_symbol,
)
from hewn.repository.index import RepositoryIndex
from hewn.repository.models import Symbol
from hewn.retrieval.models import RepositoryDocument


def build_repository(
    tmp_path: Path,
) -> RepositoryIndex:
    source = tmp_path / "src" / "example"
    source.mkdir(parents=True)

    (source / "service.py").write_text(
        (
            "class Service:\n"
            "    def execute(self, value: int) -> int:\n"
            "        result = value + 1\n"
            "        adjusted = result * 2\n"
            "        return adjusted\n"
            "\n"
            "def helper() -> str:\n"
            '    return "ok"\n'
        ),
        encoding="utf-8",
    )

    return RepositoryIndex.build(
        tmp_path
    )


def get_symbol(
    index: RepositoryIndex,
    qualified_name: str,
) -> Symbol:
    matches = (
        index.find_qualified_symbol(
            qualified_name
        )
    )

    assert len(matches) == 1

    return matches[0]


def test_build_source_document_uses_exact_symbol_lines(
    tmp_path: Path,
) -> None:
    index = build_repository(
        tmp_path
    )

    symbol = get_symbol(
        index,
        "Service.execute",
    )

    document = build_source_document(
        repository_root=tmp_path,
        symbol=symbol,
    )

    assert document.path == PurePosixPath(
        "src/example/service.py"
    )
    assert (
        document.symbol
        == "Service.execute"
    )

    assert document.text == (
        "    def execute(self, value: int) -> int:\n"
        "        result = value + 1\n"
        "        adjusted = result * 2\n"
        "        return adjusted"
    )


def test_build_source_document_for_class(
    tmp_path: Path,
) -> None:
    index = build_repository(
        tmp_path
    )

    symbol = get_symbol(
        index,
        "Service",
    )

    document = build_source_document(
        repository_root=tmp_path,
        symbol=symbol,
    )

    assert "class Service:" in document.text
    assert "def execute" in document.text


def test_build_signature_document_for_method(
    tmp_path: Path,
) -> None:
    index = build_repository(
        tmp_path
    )

    symbol = get_symbol(
        index,
        "Service.execute",
    )

    document = build_signature_document(
        repository_root=tmp_path,
        symbol=symbol,
    )

    assert document.path == PurePosixPath(
        "src/example/service.py"
    )
    assert (
        document.symbol
        == "Service.execute"
    )

    assert document.text == (
        "def execute(self, value: int) -> int:"
    )


def test_build_signature_document_for_function(
    tmp_path: Path,
) -> None:
    index = build_repository(
        tmp_path
    )

    symbol = get_symbol(
        index,
        "helper",
    )

    document = build_signature_document(
        repository_root=tmp_path,
        symbol=symbol,
    )

    assert document.text == (
        "def helper() -> str:"
    )


def test_build_signature_document_for_class(
    tmp_path: Path,
) -> None:
    index = build_repository(
        tmp_path
    )

    symbol = get_symbol(
        index,
        "Service",
    )

    document = build_signature_document(
        repository_root=tmp_path,
        symbol=symbol,
    )

    assert document.text == (
        "class Service:"
    )


def test_bounded_source_returns_dedented_whole_source_when_it_fits(
    tmp_path: Path,
) -> None:
    index = build_repository(
        tmp_path
    )

    symbol = get_symbol(
        index,
        "Service.execute",
    )

    bounded = (
        build_bounded_source_document(
            repository_root=tmp_path,
            symbol=symbol,
            character_limit=1000,
        )
    )

    assert bounded.text == (
        "def execute(self, value: int) -> int:\n"
        "    result = value + 1\n"
        "    adjusted = result * 2\n"
        "    return adjusted"
    )


def test_bounded_source_keeps_complete_statements(
    tmp_path: Path,
) -> None:
    index = build_repository(
        tmp_path
    )

    symbol = get_symbol(
        index,
        "Service.execute",
    )

    signature = (
        build_signature_document(
            repository_root=tmp_path,
            symbol=symbol,
        )
    )

    first_statement = (
        "def execute(self, value: int) -> int:\n"
        "    result = value + 1"
    )

    bounded = (
        build_bounded_source_document(
            repository_root=tmp_path,
            symbol=symbol,
            character_limit=len(
                first_statement
            ),
        )
    )

    assert (
        bounded.text
        == first_statement
    )

    assert len(
        bounded.text
    ) <= len(
        first_statement
    )

    assert bounded.text.startswith(
        signature.text
    )

    assert (
        "adjusted ="
        not in bounded.text
    )


def test_bounded_source_does_not_split_statement(
    tmp_path: Path,
) -> None:
    index = build_repository(
        tmp_path
    )

    symbol = get_symbol(
        index,
        "Service.execute",
    )

    first_statement = (
        "def execute(self, value: int) -> int:\n"
        "    result = value + 1"
    )

    bounded = (
        build_bounded_source_document(
            repository_root=tmp_path,
            symbol=symbol,
            character_limit=(
                len(first_statement)
                - 1
            ),
        )
    )

    assert bounded.text == (
        "def execute(self, value: int) -> int:"
    )


def test_bounded_source_never_splits_later_statement(
    tmp_path: Path,
) -> None:
    index = build_repository(
        tmp_path
    )

    symbol = get_symbol(
        index,
        "Service.execute",
    )

    first_statement = (
        "def execute(self, value: int) -> int:\n"
        "    result = value + 1"
    )

    second_statement = (
        f"{first_statement}\n"
        "    adjusted = result * 2"
    )

    bounded = (
        build_bounded_source_document(
            repository_root=tmp_path,
            symbol=symbol,
            character_limit=(
                len(second_statement)
                - 1
            ),
        )
    )

    assert (
        bounded.text
        == first_statement
    )


def test_bounded_source_rejects_invalid_limit(
    tmp_path: Path,
) -> None:
    index = build_repository(
        tmp_path
    )

    symbol = get_symbol(
        index,
        "Service.execute",
    )

    with pytest.raises(
        ValueError,
        match="Character limit",
    ):
        build_bounded_source_document(
            repository_root=tmp_path,
            symbol=symbol,
            character_limit=0,
        )


def test_resolve_document_symbol(
    tmp_path: Path,
) -> None:
    index = build_repository(
        tmp_path
    )

    document = RepositoryDocument(
        path=PurePosixPath(
            "src/example/service.py"
        ),
        symbol="Service.execute",
        text=(
            "symbol: Service.execute"
        ),
    )

    symbol = resolve_document_symbol(
        document,
        index,
    )

    assert (
        symbol.qualified_name
        == "Service.execute"
    )


def test_resolve_unknown_symbol_fails(
    tmp_path: Path,
) -> None:
    index = build_repository(
        tmp_path
    )

    document = RepositoryDocument(
        path=PurePosixPath(
            "src/example/service.py"
        ),
        symbol="Missing.execute",
        text="symbol: Missing.execute",
    )

    with pytest.raises(
        SourceEvidenceError,
        match="Unknown repository symbol",
    ):
        resolve_document_symbol(
            document,
            index,
        )


def test_build_mixed_document() -> None:
    structural = RepositoryDocument(
        path=PurePosixPath(
            "src/service.py"
        ),
        symbol="Service.execute",
        text=(
            "path: src/service.py\n"
            "symbol: Service.execute\n"
            "kind: method"
        ),
    )

    source = RepositoryDocument(
        path=PurePosixPath(
            "src/service.py"
        ),
        symbol="Service.execute",
        text=(
            "def execute(self):\n"
            "    return True"
        ),
    )

    mixed = build_mixed_document(
        structural_document=structural,
        source_document=source,
    )

    assert "kind: method" in mixed.text
    assert "source:" in mixed.text
    assert "return True" in mixed.text


def test_mixed_document_rejects_different_symbols() -> None:
    structural = RepositoryDocument(
        path=PurePosixPath(
            "src/service.py"
        ),
        symbol="Service.execute",
        text="symbol: Service.execute",
    )

    source = RepositoryDocument(
        path=PurePosixPath(
            "src/service.py"
        ),
        symbol="Service.other",
        text="def other(): pass",
    )

    with pytest.raises(
        SourceEvidenceError,
        match="same symbol",
    ):
        build_mixed_document(
            structural_document=structural,
            source_document=source,
        )