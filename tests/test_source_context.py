from pathlib import Path, PurePosixPath

import pytest

from hewn.context.source import (
    SourceEvidenceError,
    build_mixed_document,
    build_source_document,
    resolve_document_symbol,
)
from hewn.repository.index import RepositoryIndex
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
            "        return result\n"
            "\n"
            "def helper() -> str:\n"
            '    return "ok"\n'
        ),
        encoding="utf-8",
    )

    return RepositoryIndex.build(tmp_path)


def test_build_source_document_uses_exact_symbol_lines(
    tmp_path: Path,
) -> None:
    index = build_repository(tmp_path)

    matches = index.find_qualified_symbol(
        "Service.execute"
    )

    assert len(matches) == 1
    symbol = matches[0]

    assert symbol is not None

    document = build_source_document(
        repository_root=tmp_path,
        symbol=symbol,
    )

    assert document.path == PurePosixPath(
        "src/example/service.py"
    )
    assert document.symbol == "Service.execute"

    assert document.text == (
        "    def execute(self, value: int) -> int:\n"
        "        result = value + 1\n"
        "        return result"
    )


def test_build_source_document_for_class(
    tmp_path: Path,
) -> None:
    index = build_repository(tmp_path)

    matches = index.find_qualified_symbol(
        "Service"
    )
    
    assert len(matches) == 1
    symbol = matches[0]

    assert symbol is not None

    document = build_source_document(
        repository_root=tmp_path,
        symbol=symbol,
    )

    assert "class Service:" in document.text
    assert "def execute" in document.text


def test_resolve_document_symbol(
    tmp_path: Path,
) -> None:
    index = build_repository(tmp_path)

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
    index = build_repository(tmp_path)

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
        path=PurePosixPath("src/service.py"),
        symbol="Service.execute",
        text=(
            "path: src/service.py\n"
            "symbol: Service.execute\n"
            "kind: method"
        ),
    )

    source = RepositoryDocument(
        path=PurePosixPath("src/service.py"),
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
        path=PurePosixPath("src/service.py"),
        symbol="Service.execute",
        text="symbol: Service.execute",
    )

    source = RepositoryDocument(
        path=PurePosixPath("src/service.py"),
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