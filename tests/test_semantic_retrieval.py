from collections.abc import Sequence
from pathlib import PurePosixPath

import numpy as np
import pytest
from numpy.typing import NDArray

from hewn.retrieval.models import RepositoryDocument
from hewn.retrieval.semantic import retrieve_semantic

FloatArray = NDArray[np.float32]


class FakeEmbeddingModel:
    def encode(
        self,
        texts: Sequence[str],
    ) -> FloatArray:
        vectors: list[list[float]] = []

        for text in texts:
            if "execute" in text.lower():
                vectors.append([1.0, 0.0])

            elif "finish" in text.lower():
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


def test_semantic_retrieval_ranks_highest_similarity_first() -> None:
    documents = (
        make_document(
            "src/completion.py",
            "finish",
        ),
        make_document(
            "src/tools.py",
            "execute",
        ),
    )

    results = retrieve_semantic(
        "execute",
        documents,
        model=FakeEmbeddingModel(),
        limit=2,
    )

    assert results[0].document.path == PurePosixPath(
        "src/tools.py"
    )


def test_semantic_retrieval_preserves_symbol() -> None:
    documents = (
        make_document(
            "src/tools.py",
            "execute",
            symbol="ToolExecutor.execute",
        ),
    )

    results = retrieve_semantic(
        "execute",
        documents,
        model=FakeEmbeddingModel(),
    )

    assert (
        results[0].document.symbol
        == "ToolExecutor.execute"
    )


def test_semantic_retrieval_returns_requested_limit() -> None:
    documents = (
        make_document("src/a.py", "execute"),
        make_document("src/b.py", "finish"),
        make_document("src/c.py", "other"),
    )

    results = retrieve_semantic(
        "execute",
        documents,
        model=FakeEmbeddingModel(),
        limit=2,
    )

    assert len(results) == 2


def test_semantic_retrieval_handles_empty_documents() -> None:
    results = retrieve_semantic(
        "execute",
        (),
        model=FakeEmbeddingModel(),
    )

    assert results == ()


def test_semantic_retrieval_rejects_invalid_limit() -> None:
    with pytest.raises(ValueError):
        retrieve_semantic(
            "execute",
            (),
            model=FakeEmbeddingModel(),
            limit=0,
        )