from pathlib import PurePosixPath

import pytest

from hewn.context.budget import (
    select_by_evidence_count,
)
from hewn.retrieval.models import (
    RepositoryDocument,
    RetrievalResult,
)


def make_result(
    *,
    path: str,
    symbol: str,
    text: str,
    score: float,
) -> RetrievalResult:
    return RetrievalResult(
        document=RepositoryDocument(
            path=PurePosixPath(path),
            symbol=symbol,
            text=text,
        ),
        score=score,
    )


def test_select_by_evidence_count_preserves_rank() -> None:
    results = (
        make_result(
            path="src/a.py",
            symbol="A",
            text="first",
            score=0.9,
        ),
        make_result(
            path="src/b.py",
            symbol="B",
            text="second",
            score=0.8,
        ),
        make_result(
            path="src/c.py",
            symbol="C",
            text="third",
            score=0.7,
        ),
    )

    bundle = select_by_evidence_count(
        results,
        limit=2,
    )

    assert bundle.evidence_count == 2

    assert [
        item.retrieval_result.document.symbol
        for item in bundle.evidence
    ] == ["A", "B"]


def test_context_bundle_counts_characters() -> None:
    results = (
        make_result(
            path="src/a.py",
            symbol="A",
            text="abcd",
            score=0.9,
        ),
        make_result(
            path="src/b.py",
            symbol="B",
            text="123456",
            score=0.8,
        ),
    )

    bundle = select_by_evidence_count(
        results,
        limit=2,
    )

    assert bundle.character_count == 10


def test_context_bundle_counts_unique_files() -> None:
    results = (
        make_result(
            path="src/a.py",
            symbol="A.one",
            text="one",
            score=0.9,
        ),
        make_result(
            path="src/a.py",
            symbol="A.two",
            text="two",
            score=0.8,
        ),
        make_result(
            path="src/b.py",
            symbol="B",
            text="three",
            score=0.7,
        ),
    )

    bundle = select_by_evidence_count(
        results,
        limit=3,
    )

    assert bundle.evidence_count == 3
    assert bundle.unique_file_count == 2


def test_limit_larger_than_results_uses_all() -> None:
    results = (
        make_result(
            path="src/a.py",
            symbol="A",
            text="first",
            score=0.9,
        ),
    )

    bundle = select_by_evidence_count(
        results,
        limit=5,
    )

    assert bundle.evidence_count == 1


def test_invalid_evidence_limit() -> None:
    with pytest.raises(
        ValueError,
        match="Evidence limit must be at least 1",
    ):
        select_by_evidence_count(
            (),
            limit=0,
        )