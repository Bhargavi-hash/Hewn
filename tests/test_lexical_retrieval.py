from pathlib import PurePosixPath

import pytest

from hewn.retrieval.lexical import (
    lexical_score,
    retrieve_lexical,
    tokenize,
)
from hewn.retrieval.models import RepositoryDocument


def make_document(
    path: str,
    text: str,
) -> RepositoryDocument:
    return RepositoryDocument(
        path=PurePosixPath(path),
        text=text,
    )


def test_tokenize_normalizes_case_and_punctuation() -> None:
    assert tokenize(
        "CompletionPolicy.can_finish()"
    ) == (
        "completionpolicy",
        "can",
        "finish",
    )


def test_lexical_score_uses_query_overlap() -> None:
    document = make_document(
        "src/hewn/completion.py",
        (
            "path: src/hewn/completion.py\n"
            "symbols:\n"
            "  class: CompletionPolicy\n"
            "  method: CompletionPolicy.can_finish"
        ),
    )

    score = lexical_score(
        "Find CompletionPolicy",
        document,
    )

    assert score == pytest.approx(0.5)


def test_retrieve_lexical_ranks_matching_document_first() -> None:
    documents = (
        make_document(
            "src/hewn/workspace.py",
            "path: src/hewn/workspace.py\nclass: Workspace",
        ),
        make_document(
            "src/hewn/completion.py",
            "path: src/hewn/completion.py\nclass: CompletionPolicy",
        ),
    )

    results = retrieve_lexical(
        "Find CompletionPolicy",
        documents,
        limit=2,
    )

    assert results[0].document.path == PurePosixPath(
        "src/hewn/completion.py"
    )
    assert results[0].score > results[1].score


def test_retrieve_lexical_breaks_ties_by_path() -> None:
    documents = (
        make_document(
            "src/z.py",
            "class: Worker",
        ),
        make_document(
            "src/a.py",
            "class: Worker",
        ),
    )

    results = retrieve_lexical(
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


def test_retrieve_lexical_rejects_invalid_limit() -> None:
    documents = (
        make_document(
            "src/agent.py",
            "class: Agent",
        ),
    )

    with pytest.raises(ValueError):
        retrieve_lexical(
            "Agent",
            documents,
            limit=0,
        )