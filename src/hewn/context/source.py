from __future__ import annotations

from pathlib import Path

from hewn.repository.index import RepositoryIndex
from hewn.repository.models import Symbol
from hewn.retrieval.models import RepositoryDocument


class SourceEvidenceError(ValueError):
    """Raised when source evidence cannot be constructed safely."""


def build_source_document(
    *,
    repository_root: Path,
    symbol: Symbol,
) -> RepositoryDocument:
    source_path = (
        repository_root
        / Path(*symbol.location.path.parts)
    ).resolve()

    root = repository_root.resolve()

    try:
        source_path.relative_to(root)
    except ValueError as exc:
        raise SourceEvidenceError(
            "Symbol source path escapes repository root"
        ) from exc

    if not source_path.is_file():
        raise SourceEvidenceError(
            f"Symbol source file does not exist: "
            f"{symbol.location.path}"
        )

    lines = source_path.read_text(
        encoding="utf-8",
    ).splitlines()

    start_line = symbol.location.start_line
    end_line = symbol.location.end_line

    if start_line < 1:
        raise SourceEvidenceError(
            "Symbol start line must be at least 1"
        )

    if end_line < start_line:
        raise SourceEvidenceError(
            "Symbol end line precedes start line"
        )

    if end_line > len(lines):
        raise SourceEvidenceError(
            "Symbol source location exceeds file length"
        )

    source = "\n".join(
        lines[start_line - 1 : end_line]
    )

    if not source.strip():
        raise SourceEvidenceError(
            "Symbol source evidence is empty"
        )

    return RepositoryDocument(
        path=symbol.location.path,
        symbol=symbol.qualified_name,
        text=source,
    )


def build_mixed_document(
    *,
    structural_document: RepositoryDocument,
    source_document: RepositoryDocument,
) -> RepositoryDocument:
    if (
        structural_document.path
        != source_document.path
    ):
        raise SourceEvidenceError(
            "Structural and source documents "
            "must reference the same file"
        )

    if (
        structural_document.symbol
        != source_document.symbol
    ):
        raise SourceEvidenceError(
            "Structural and source documents "
            "must reference the same symbol"
        )

    return RepositoryDocument(
        path=structural_document.path,
        symbol=structural_document.symbol,
        text=(
            f"{structural_document.text}\n"
            "\n"
            "source:\n"
            f"{source_document.text}"
        ),
    )


def resolve_document_symbol(
    document: RepositoryDocument,
    repository_index: RepositoryIndex,
) -> Symbol:
    if document.symbol is None:
        raise SourceEvidenceError(
            "Source evidence requires a symbol document"
        )

    matches = repository_index.find_qualified_symbol(
        document.symbol
    )

    if not matches:
        raise SourceEvidenceError(
            f"Unknown repository symbol: "
            f"{document.symbol}"
        )

    path_matches = tuple(
        symbol
        for symbol in matches
        if symbol.location.path == document.path
    )

    if len(path_matches) == 1:
        return path_matches[0]

    if not path_matches:
        raise SourceEvidenceError(
            "Retrieved document path does not match "
            "resolved symbol path"
        )

    raise SourceEvidenceError(
        f"Repository symbol is ambiguous: "
        f"{document.symbol}"
    )