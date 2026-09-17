from pathlib import PurePosixPath

import pytest

from hewn.retrieval.bm25 import retrieve_bm25
from hewn.retrieval.models import RepositoryDocument


def make_document(
    path: str,
    text: str,
) -> RepositoryDocument:
    return RepositoryDocument(
        path=PurePosixPath(path),
        text=text,
    )


def test_bm25_ranks_rare_matching_term_first() -> None:
    documents = (
        make_document(
            "src/common.py",
            "repository repository symbols imports",
        ),
        make_document(
            "src/tools.py",
            "repository ToolExecutor",
        ),
        make_document(
            "src/index.py",
            "repository index dependencies",
        ),
    )

    results = retrieve_bm25(
        "Find ToolExecutor in repository",
        documents,
        limit=3,
    )

    assert results[0].document.path == PurePosixPath(
        "src/tools.py"
    )


def test_bm25_returns_requested_limit() -> None:
    documents = (
        make_document(
            "src/a.py",
            "Alpha",
        ),
        make_document(
            "src/b.py",
            "Beta",
        ),
        make_document(
            "src/c.py",
            "Gamma",
        ),
    )

    results = retrieve_bm25(
        "Alpha",
        documents,
        limit=2,
    )

    assert len(results) == 2


def test_bm25_breaks_equal_scores_by_path() -> None:
    documents = (
        make_document(
            "src/z.py",
            "Worker",
        ),
        make_document(
            "src/a.py",
            "Worker",
        ),
    )

    results = retrieve_bm25(
        "Worker",
        documents,
        limit=2,
    )

    assert [
        str(result.document.path)
        for result in results
    ] == [
        "src/a.py",
        "src/z.py",
    ]


def test_bm25_handles_empty_query() -> None:
    documents = (
        make_document(
            "src/b.py",
            "Beta",
        ),
        make_document(
            "src/a.py",
            "Alpha",
        ),
    )

    results = retrieve_bm25(
        "",
        documents,
        limit=2,
    )

    assert [
        str(result.document.path)
        for result in results
    ] == [
        "src/a.py",
        "src/b.py",
    ]

    assert all(
        result.score == pytest.approx(0.0)
        for result in results
    )


def test_bm25_handles_empty_document_collection() -> None:
    assert retrieve_bm25(
        "Agent",
        (),
    ) == ()


def test_bm25_rejects_invalid_limit() -> None:
    with pytest.raises(ValueError):
        retrieve_bm25(
            "Agent",
            (),
            limit=0,
        )


def test_bm25_rejects_invalid_k1() -> None:
    with pytest.raises(ValueError):
        retrieve_bm25(
            "Agent",
            (),
            k1=0.0,
        )


def test_bm25_rejects_invalid_b() -> None:
    with pytest.raises(ValueError):
        retrieve_bm25(
            "Agent",
            (),
            b=1.5,
        )