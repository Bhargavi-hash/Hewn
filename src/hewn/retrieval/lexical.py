from __future__ import annotations

import re

from hewn.retrieval.models import RepositoryDocument, RetrievalResult

_TOKEN_PATTERN = re.compile(r"[A-Za-z0-9]+")


def tokenize(text: str) -> tuple[str, ...]:
    return tuple(
        token.lower()
        for token in _TOKEN_PATTERN.findall(text)
    )


def lexical_score(
    query: str,
    document: RepositoryDocument,
) -> float:
    query_tokens = set(tokenize(query))

    if not query_tokens:
        return 0.0

    document_tokens = set(tokenize(document.text))

    overlap = query_tokens & document_tokens

    return len(overlap) / len(query_tokens)


def retrieve_lexical(
    query: str,
    documents: tuple[RepositoryDocument, ...],
    *,
    limit: int = 5,
) -> tuple[RetrievalResult, ...]:
    if limit < 1:
        raise ValueError("Retrieval limit must be at least 1")

    results = [
        RetrievalResult(
            document=document,
            score=lexical_score(query, document),
        )
        for document in documents
    ]

    ranked = sorted(
        results,
        key=lambda result: (
            -result.score,
            str(result.document.path),
        ),
    )

    return tuple(ranked[:limit])