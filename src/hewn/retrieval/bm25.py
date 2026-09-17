from __future__ import annotations

import math
from collections import Counter

from hewn.retrieval.lexical import tokenize
from hewn.retrieval.models import RepositoryDocument, RetrievalResult


def _inverse_document_frequency(
    *,
    document_count: int,
    document_frequency: int,
) -> float:
    return math.log(
        1.0
        + (
            document_count
            - document_frequency
            + 0.5
        )
        / (
            document_frequency
            + 0.5
        )
    )


def retrieve_bm25(
    query: str,
    documents: tuple[RepositoryDocument, ...],
    *,
    limit: int = 5,
    k1: float = 1.5,
    b: float = 0.75,
) -> tuple[RetrievalResult, ...]:
    if limit < 1:
        raise ValueError("Retrieval limit must be at least 1")

    if k1 <= 0:
        raise ValueError("BM25 k1 must be greater than 0")

    if not 0.0 <= b <= 1.0:
        raise ValueError("BM25 b must be between 0 and 1")

    if not documents:
        return ()

    query_tokens = tokenize(query)

    document_tokens = [
        tokenize(document.text)
        for document in documents
    ]

    document_lengths = [
        len(tokens)
        for tokens in document_tokens
    ]

    average_document_length = (
        sum(document_lengths)
        / len(document_lengths)
    )

    document_frequency: Counter[str] = Counter()

    for tokens in document_tokens:
        document_frequency.update(set(tokens))

    results: list[RetrievalResult] = []

    for document, tokens in zip(
        documents,
        document_tokens,
        strict=True,
    ):
        term_frequency = Counter(tokens)
        document_length = len(tokens)

        score = 0.0

        for token in query_tokens:
            frequency = term_frequency[token]

            if frequency == 0:
                continue

            idf = _inverse_document_frequency(
                document_count=len(documents),
                document_frequency=document_frequency[token],
            )

            denominator = frequency + k1 * (
                1.0
                - b
                + b
                * document_length
                / average_document_length
            )

            score += idf * (
                frequency * (k1 + 1.0)
                / denominator
            )

        results.append(
            RetrievalResult(
                document=document,
                score=score,
            )
        )

    ranked = sorted(
        results,
        key=lambda result: (
            -result.score,
            str(result.document.path),
        ),
    )

    return tuple(ranked[:limit])