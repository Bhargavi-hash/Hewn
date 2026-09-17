from pathlib import PurePosixPath

import pytest

from hewn.context.character_budget import (
    select_by_character_budget,
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


def test_selects_ranked_evidence_that_fits() -> None:
    results = (
        make_result(
            path="src/a.py",
            symbol="A",
            text="aaaa",
            score=0.9,
        ),
        make_result(
            path="src/b.py",
            symbol="B",
            text="bbbb",
            score=0.8,
        ),
        make_result(
            path="src/c.py",
            symbol="C",
            text="cccc",
            score=0.7,
        ),
    )

    bundle = select_by_character_budget(
        results,
        budget=8,
    )

    assert [
        item.retrieval_result.document.symbol
        for item in bundle.evidence
    ] == ["A", "B"]

    assert bundle.character_count == 8


def test_first_evidence_is_kept_when_over_budget() -> None:
    results = (
        make_result(
            path="src/a.py",
            symbol="A",
            text="abcdefghij",
            score=0.9,
        ),
        make_result(
            path="src/b.py",
            symbol="B",
            text="x",
            score=0.8,
        ),
    )

    bundle = select_by_character_budget(
        results,
        budget=5,
    )

    assert bundle.evidence_count == 1
    assert (
        bundle.evidence[0]
        .retrieval_result.document.symbol
        == "A"
    )
    assert bundle.character_count == 10


def test_skips_oversized_later_evidence_and_continues() -> None:
    results = (
        make_result(
            path="src/a.py",
            symbol="A",
            text="aaaa",
            score=0.9,
        ),
        make_result(
            path="src/b.py",
            symbol="B",
            text="bbbbbb",
            score=0.8,
        ),
        make_result(
            path="src/c.py",
            symbol="C",
            text="cc",
            score=0.7,
        ),
    )

    bundle = select_by_character_budget(
        results,
        budget=6,
    )

    assert [
        item.retrieval_result.document.symbol
        for item in bundle.evidence
    ] == ["A", "C"]

    assert bundle.character_count == 6


def test_exact_budget_is_allowed() -> None:
    results = (
        make_result(
            path="src/a.py",
            symbol="A",
            text="abcde",
            score=0.9,
        ),
    )

    bundle = select_by_character_budget(
        results,
        budget=5,
    )

    assert bundle.character_count == 5


def test_invalid_character_budget() -> None:
    with pytest.raises(
        ValueError,
        match="Character budget must be at least 1",
    ):
        select_by_character_budget(
            (),
            budget=0,
        )