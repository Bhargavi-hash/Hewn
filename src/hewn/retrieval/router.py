from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from pathlib import PurePosixPath

from hewn.repository.index import RepositoryIndex
from hewn.repository.models import Symbol
from hewn.retrieval.models import (
    RepositoryDocument,
    RetrievalResult,
)
from hewn.retrieval.semantic import EmbeddingModel
from hewn.retrieval.semantic_index import SemanticIndex

_IDENTIFIER_PATTERN = re.compile(
    r"\b[A-Za-z_][A-Za-z0-9_]*\b"
)


class RetrievalRoute(str, Enum):
    EXACT_SYMBOL = "exact_symbol"
    SEMANTIC = "semantic"


@dataclass(frozen=True, slots=True)
class RoutedRetrievalResult:
    route: RetrievalRoute
    results: tuple[RetrievalResult, ...]
    matched_symbol: str | None = None


def extract_identifier_candidates(
    query: str,
) -> tuple[str, ...]:
    seen: set[str] = set()
    candidates: list[str] = []

    for match in _IDENTIFIER_PATTERN.finditer(query):
        candidate = match.group(0)

        if candidate in seen:
            continue

        seen.add(candidate)
        candidates.append(candidate)

    return tuple(candidates)


def find_explicit_symbol(
    query: str,
    repository_index: RepositoryIndex,
) -> Symbol | None:
    matches: list[Symbol] = []

    for candidate in extract_identifier_candidates(query):
        symbols = repository_index.find_symbol(
            candidate
        )

        if len(symbols) != 1:
            continue

        matches.append(symbols[0])

    if len(matches) != 1:
        return None

    return matches[0]


def retrieve_routed(
    query: str,
    *,
    repository_index: RepositoryIndex,
    semantic_index: SemanticIndex,
    model: EmbeddingModel,
    semantic_limit: int,
) -> RoutedRetrievalResult:
    if semantic_limit < 1:
        raise ValueError(
            "Semantic retrieval limit must be at least 1"
        )

    symbol = find_explicit_symbol(
        query,
        repository_index,
    )

    if symbol is not None:
        result = RetrievalResult(
            document=_symbol_to_document(
                symbol
            ),
            score=1.0,
        )

        return RoutedRetrievalResult(
            route=RetrievalRoute.EXACT_SYMBOL,
            results=(result,),
            matched_symbol=symbol.qualified_name,
        )

    results = semantic_index.retrieve(
        query,
        model=model,
        limit=semantic_limit,
    )

    return RoutedRetrievalResult(
        route=RetrievalRoute.SEMANTIC,
        results=results,
    )


def _symbol_to_document(
    symbol: Symbol,
) -> RepositoryDocument:
    lines = [
        f"path: {symbol.location.path}",
        f"symbol: {symbol.qualified_name}",
        f"kind: {symbol.kind.value}",
    ]

    if symbol.signature is not None:
        lines.append(
            f"signature: {symbol.signature}"
        )

    return RepositoryDocument(
        path=PurePosixPath(
            symbol.location.path
        ),
        symbol=symbol.qualified_name,
        text="\n".join(lines),
    )