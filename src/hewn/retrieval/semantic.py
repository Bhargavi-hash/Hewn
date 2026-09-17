from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol

import numpy as np
from numpy.typing import NDArray

from hewn.retrieval.models import (
    RepositoryDocument,
    RetrievalResult,
)

FloatArray = NDArray[np.float32]


class EmbeddingModel(Protocol):
    def encode(
        self,
        texts: Sequence[str],
    ) -> FloatArray: ...


def retrieve_semantic(
    query: str,
    documents: tuple[RepositoryDocument, ...],
    *,
    model: EmbeddingModel,
    limit: int = 5,
) -> tuple[RetrievalResult, ...]:
    if limit < 1:
        raise ValueError(
            "Retrieval limit must be at least 1"
        )

    if not documents:
        return ()

    document_embeddings = model.encode(
        [document.text for document in documents]
    )

    query_embeddings = model.encode([query])

    if document_embeddings.ndim != 2:
        raise ValueError(
            "Document embeddings must be two-dimensional"
        )

    if query_embeddings.ndim != 2:
        raise ValueError(
            "Query embeddings must be two-dimensional"
        )

    if query_embeddings.shape[0] != 1:
        raise ValueError(
            "Expected exactly one query embedding"
        )

    if document_embeddings.shape[0] != len(documents):
        raise ValueError(
            "Embedding count does not match document count"
        )

    if (
        document_embeddings.shape[1]
        != query_embeddings.shape[1]
    ):
        raise ValueError(
            "Query and document embedding dimensions differ"
        )

    scores = (
        document_embeddings
        @ query_embeddings[0]
    )

    results = [
        RetrievalResult(
            document=document,
            score=float(score),
        )
        for document, score in zip(
            documents,
            scores,
            strict=True,
        )
    ]

    results.sort(
        key=lambda result: (
            -result.score,
            str(result.document.path),
            result.document.symbol or "",
        )
    )

    return tuple(results[:limit])