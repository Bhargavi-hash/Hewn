from __future__ import annotations

from dataclasses import dataclass
from time import perf_counter

import numpy as np
from numpy.typing import NDArray

from hewn.retrieval.models import (
    RepositoryDocument,
    RetrievalResult,
)
from hewn.retrieval.semantic import EmbeddingModel

FloatArray = NDArray[np.float32]


@dataclass(frozen=True, slots=True)
class SemanticIndexStats:
    document_count: int
    embedding_dimension: int
    indexing_seconds: float


class SemanticIndex:
    def __init__(
        self,
        *,
        documents: tuple[RepositoryDocument, ...],
        embeddings: FloatArray,
        stats: SemanticIndexStats,
    ) -> None:
        self._documents = documents
        self._embeddings = embeddings
        self._stats = stats

    @classmethod
    def build(
        cls,
        documents: tuple[RepositoryDocument, ...],
        *,
        model: EmbeddingModel,
    ) -> SemanticIndex:
        if not documents:
            raise ValueError(
                "Cannot build semantic index without documents"
            )

        start = perf_counter()

        embeddings = model.encode(
            [document.text for document in documents]
        )

        elapsed = perf_counter() - start

        if embeddings.ndim != 2:
            raise ValueError(
                "Document embeddings must be two-dimensional"
            )

        if embeddings.shape[0] != len(documents):
            raise ValueError(
                "Embedding count does not match document count"
            )

        if embeddings.shape[1] < 1:
            raise ValueError(
                "Embedding dimension must be positive"
            )

        return cls(
            documents=documents,
            embeddings=embeddings,
            stats=SemanticIndexStats(
                document_count=len(documents),
                embedding_dimension=embeddings.shape[1],
                indexing_seconds=elapsed,
            ),
        )

    @property
    def stats(self) -> SemanticIndexStats:
        return self._stats

    def retrieve(
        self,
        query: str,
        *,
        model: EmbeddingModel,
        limit: int = 5,
    ) -> tuple[RetrievalResult, ...]:
        if limit < 1:
            raise ValueError(
                "Retrieval limit must be at least 1"
            )

        query_embeddings = model.encode([query])

        if query_embeddings.ndim != 2:
            raise ValueError(
                "Query embeddings must be two-dimensional"
            )

        if query_embeddings.shape != (
            1,
            self._stats.embedding_dimension,
        ):
            raise ValueError(
                "Query embedding dimension does not match index"
            )

        scores = (
            self._embeddings
            @ query_embeddings[0]
        )

        results = [
            RetrievalResult(
                document=document,
                score=float(score),
            )
            for document, score in zip(
                self._documents,
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