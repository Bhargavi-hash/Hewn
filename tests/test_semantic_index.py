from collections.abc import Sequence
from pathlib import PurePosixPath

import numpy as np
import pytest
from numpy.typing import NDArray

from hewn.retrieval.models import RepositoryDocument
from hewn.retrieval.semantic_index import SemanticIndex

FloatArray = NDArray[np.float32]


class FakeEmbeddingModel:
    def encode(
        self,
        texts: Sequence[str],
    ) -> FloatArray:
        vectors: list[list[float]] = []

        for text in texts:
            lowered = text.lower()

            if "execute" in lowered:
                vectors.append([1.0, 0.0])

            elif "finish" in lowered:
                vectors.append([0.0, 1.0])

            else:
                vectors.append([0.0, 0.0])

        return np.asarray(
            vectors,
            dtype=np.float32,
        )


def make_document(
    path: str,
    text: str,
    *,
    symbol: str | None = None,
) -> RepositoryDocument:
    return RepositoryDocument(
        path=PurePosixPath(path),
        text=text,
        symbol=symbol,
    )


def test_build_records_index_metadata() -> None:
    documents = (
        make_document(
            "src/tools.py",
            "execute",
        ),
        make_document(
            "src/completion.py",
            "finish",
        ),
    )

    index = SemanticIndex.build(
        documents,
        model=FakeEmbeddingModel(),
    )

    assert index.stats.document_count == 2
    assert index.stats.embedding_dimension == 2
    assert index.stats.indexing_seconds >= 0.0


def test_retrieve_uses_precomputed_documents() -> None:
    documents = (
        make_document(
            "src/completion.py",
            "finish",
        ),
        make_document(
            "src/tools.py",
            "execute",
            symbol="ToolExecutor.execute",
        ),
    )

    model = FakeEmbeddingModel()

    index = SemanticIndex.build(
        documents,
        model=model,
    )

    results = index.retrieve(
        "execute",
        model=model,
        limit=2,
    )

    assert results[0].document.path == PurePosixPath(
        "src/tools.py"
    )
    assert (
        results[0].document.symbol
        == "ToolExecutor.execute"
    )


def test_retrieve_rejects_invalid_limit() -> None:
    documents = (
        make_document(
            "src/tools.py",
            "execute",
        ),
    )

    model = FakeEmbeddingModel()

    index = SemanticIndex.build(
        documents,
        model=model,
    )

    with pytest.raises(ValueError):
        index.retrieve(
            "execute",
            model=model,
            limit=0,
        )


def test_build_rejects_empty_documents() -> None:
    with pytest.raises(ValueError):
        SemanticIndex.build(
            (),
            model=FakeEmbeddingModel(),
        )