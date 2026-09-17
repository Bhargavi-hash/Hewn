from __future__ import annotations

import ast
import textwrap
from pathlib import Path

from hewn.repository.index import RepositoryIndex
from hewn.repository.models import Symbol
from hewn.retrieval.models import RepositoryDocument

SourceNode = ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef


class SourceEvidenceError(ValueError):
    """Raised when source evidence cannot be constructed safely."""


def _read_symbol_source(
    *,
    repository_root: Path,
    symbol: Symbol,
) -> str:
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

    return source


def _dedent_symbol_source(
    source: str,
) -> str:
    dedented = textwrap.dedent(
        source
    ).rstrip()

    if not dedented.strip():
        raise SourceEvidenceError(
            "Dedented symbol source is empty"
        )

    return dedented


def _parse_single_symbol(
    source: str,
) -> SourceNode:
    try:
        module = ast.parse(
            source
        )
    except SyntaxError as exc:
        raise SourceEvidenceError(
            "Symbol source could not be parsed"
        ) from exc

    if len(module.body) != 1:
        raise SourceEvidenceError(
            "Expected exactly one top-level symbol"
        )

    node = module.body[0]

    if not isinstance(
        node,
        (
            ast.ClassDef,
            ast.FunctionDef,
            ast.AsyncFunctionDef,
        ),
    ):
        raise SourceEvidenceError(
            "Source evidence does not describe "
            "a class or function"
        )

    return node


def _line_offsets(
    source: str,
) -> tuple[int, ...]:
    offsets = [0]

    for index, character in enumerate(source):
        if character == "\n":
            offsets.append(index + 1)

    return tuple(offsets)


def _node_end_offset(
    *,
    source: str,
    node: ast.stmt,
) -> int:
    end_lineno = node.end_lineno
    end_col_offset = node.end_col_offset

    if (
        end_lineno is None
        or end_col_offset is None
    ):
        raise SourceEvidenceError(
            "AST node has no source end position"
        )

    lines = source.splitlines(
        keepends=True
    )
    offsets = _line_offsets(source)

    if (
        end_lineno < 1
        or end_lineno > len(lines)
        or end_lineno > len(offsets)
    ):
        raise SourceEvidenceError(
            "AST source position exceeds symbol source"
        )

    line_start = offsets[
        end_lineno - 1
    ]

    line = lines[
        end_lineno - 1
    ]

    encoded_line = line.encode(
        "utf-8"
    )

    if end_col_offset > len(encoded_line):
        raise SourceEvidenceError(
            "AST column position exceeds source line"
        )

    decoded_prefix = encoded_line[
        :end_col_offset
    ].decode(
        "utf-8"
    )

    return (
        line_start
        + len(decoded_prefix)
    )


def _signature_text(
    *,
    source: str,
    node: SourceNode,
) -> str:
    if not node.body:
        raise SourceEvidenceError(
            "Symbol has no body"
        )

    body_start_line = node.body[0].lineno

    lines = source.splitlines()

    signature = "\n".join(
        lines[
            : max(
                1,
                body_start_line - 1,
            )
        ]
    ).rstrip()

    if not signature:
        raise SourceEvidenceError(
            "Symbol signature evidence is empty"
        )

    return signature


def build_source_document(
    *,
    repository_root: Path,
    symbol: Symbol,
) -> RepositoryDocument:
    source = _read_symbol_source(
        repository_root=repository_root,
        symbol=symbol,
    )

    return RepositoryDocument(
        path=symbol.location.path,
        symbol=symbol.qualified_name,
        text=source,
    )


def build_signature_document(
    *,
    repository_root: Path,
    symbol: Symbol,
) -> RepositoryDocument:
    source = _read_symbol_source(
        repository_root=repository_root,
        symbol=symbol,
    )

    dedented_source = (
        _dedent_symbol_source(
            source
        )
    )

    node = _parse_single_symbol(
        dedented_source
    )

    signature = _signature_text(
        source=dedented_source,
        node=node,
    )

    return RepositoryDocument(
        path=symbol.location.path,
        symbol=symbol.qualified_name,
        text=signature,
    )


def build_bounded_source_document(
    *,
    repository_root: Path,
    symbol: Symbol,
    character_limit: int,
) -> RepositoryDocument:
    if character_limit < 1:
        raise ValueError(
            "Character limit must be at least 1"
        )

    source = _read_symbol_source(
        repository_root=repository_root,
        symbol=symbol,
    )

    dedented_source = (
        _dedent_symbol_source(
            source
        )
    )

    if (
        len(dedented_source)
        <= character_limit
    ):
        return RepositoryDocument(
            path=symbol.location.path,
            symbol=symbol.qualified_name,
            text=dedented_source,
        )

    node = _parse_single_symbol(
        dedented_source
    )

    signature = _signature_text(
        source=dedented_source,
        node=node,
    )

    if len(signature) > character_limit:
        return RepositoryDocument(
            path=symbol.location.path,
            symbol=symbol.qualified_name,
            text=signature,
        )

    candidates: list[str] = [
        signature
    ]

    for body_node in node.body:
        end_offset = _node_end_offset(
            source=dedented_source,
            node=body_node,
        )

        candidate = dedented_source[
            :end_offset
        ].rstrip()

        if len(candidate) > character_limit:
            break

        candidates.append(
            candidate
        )

    bounded = max(
        candidates,
        key=len,
    )

    if not bounded.strip():
        raise SourceEvidenceError(
            "Bounded source evidence is empty"
        )

    return RepositoryDocument(
        path=symbol.location.path,
        symbol=symbol.qualified_name,
        text=bounded,
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