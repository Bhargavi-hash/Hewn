from __future__ import annotations

from pathlib import Path, PurePosixPath

import pytest

from hewn.context.builder import (
    ContextBuilder,
    ContextBuildError,
)
from hewn.context.policy import ContextPolicy
from hewn.repository.index import RepositoryIndex
from hewn.retrieval.models import (
    RepositoryDocument,
    RetrievalResult,
)
from hewn.retrieval.router import (
    RetrievalRoute,
    RoutedRetrievalResult,
)


def _write_repository(
    root: Path,
) -> RepositoryIndex:
    package = root / "src" / "sample"
    package.mkdir(
        parents=True,
    )

    (package / "__init__.py").write_text(
        "",
        encoding="utf-8",
    )

    (package / "alpha.py").write_text(
        "class Alpha:\n"
        "    def run(self) -> str:\n"
        '        return "alpha"\n',
        encoding="utf-8",
    )

    (package / "beta.py").write_text(
        "class Beta:\n"
        "    def run(self) -> str:\n"
        '        return "beta"\n',
        encoding="utf-8",
    )

    (package / "gamma.py").write_text(
        "class Gamma:\n"
        "    def run(self) -> str:\n"
        '        return "gamma"\n',
        encoding="utf-8",
    )

    (package / "delta.py").write_text(
        "class Delta:\n"
        "    def run(self) -> str:\n"
        '        return "delta"\n',
        encoding="utf-8",
    )

    return RepositoryIndex.build(
        root
    )

def _result(
    *,
    path: str,
    symbol: str,
    score: float,
    text: str = "structural evidence",
) -> RetrievalResult:
    return RetrievalResult(
        document=RepositoryDocument(
            path=PurePosixPath(path),
            symbol=symbol,
            text=text,
        ),
        score=score,
    )


def test_exact_context_preserves_structural_evidence(
    tmp_path: Path,
) -> None:
    repository_index = _write_repository(
        tmp_path
    )

    result = _result(
        path="src/sample/alpha.py",
        symbol="Alpha",
        score=1.0,
        text=(
            "path: src/sample/alpha.py\n"
            "symbol: Alpha\n"
            "kind: class"
        ),
    )

    retrieval = RoutedRetrievalResult(
        route=RetrievalRoute.EXACT_SYMBOL,
        results=(result,),
        matched_symbol="Alpha",
    )

    builder = ContextBuilder(
        repository_root=tmp_path,
        repository_index=repository_index,
    )

    bundle = builder.build(
        retrieval
    )

    assert bundle.evidence_count == 1
    assert (
        bundle.evidence[0].retrieval_result
        == result
    )
    assert (
        bundle.evidence[0].text
        == result.document.text
    )


def test_exact_context_requires_one_result(
    tmp_path: Path,
) -> None:
    repository_index = _write_repository(
        tmp_path
    )

    retrieval = RoutedRetrievalResult(
        route=RetrievalRoute.EXACT_SYMBOL,
        results=(),
        matched_symbol="Alpha",
    )

    builder = ContextBuilder(
        repository_root=tmp_path,
        repository_index=repository_index,
    )

    bundle = builder.build(
        retrieval
    )

    assert bundle.evidence == ()


def test_semantic_context_selects_unique_files_in_retrieval_order(
    tmp_path: Path,
) -> None:
    repository_index = _write_repository(
        tmp_path
    )

    retrieval = RoutedRetrievalResult(
        route=RetrievalRoute.SEMANTIC,
        results=(
            _result(
                path="src/sample/alpha.py",
                symbol="Alpha",
                score=0.90,
            ),
            _result(
                path="src/sample/alpha.py",
                symbol="Alpha.run",
                score=0.85,
            ),
            _result(
                path="src/sample/beta.py",
                symbol="Beta",
                score=0.80,
            ),
            _result(
                path="src/sample/gamma.py",
                symbol="Gamma",
                score=0.70,
            ),
            _result(
                path="src/sample/delta.py",
                symbol="Delta",
                score=0.60,
            ),
        ),
    )

    builder = ContextBuilder(
        repository_root=tmp_path,
        repository_index=repository_index,
    )

    bundle = builder.build(
        retrieval
    )

    paths = tuple(
        item.retrieval_result.document.path
        for item in bundle.evidence
    )

    assert paths == (
        PurePosixPath(
            "src/sample/alpha.py"
        ),
        PurePosixPath(
            "src/sample/beta.py"
        ),
        PurePosixPath(
            "src/sample/gamma.py"
        ),
    )

    assert bundle.evidence_count == 3
    assert bundle.unique_file_count == 3


def test_semantic_context_uses_bounded_source(
    tmp_path: Path,
) -> None:
    repository_index = _write_repository(
        tmp_path
    )

    retrieval = RoutedRetrievalResult(
        route=RetrievalRoute.SEMANTIC,
        results=(
            _result(
                path="src/sample/alpha.py",
                symbol="Alpha",
                score=0.90,
            ),
        ),
    )

    builder = ContextBuilder(
        repository_root=tmp_path,
        repository_index=repository_index,
        policy=ContextPolicy(
            bounded_source_limit=800,
        ),
    )

    bundle = builder.build(
        retrieval
    )

    evidence = bundle.evidence[0]

    assert "class Alpha:" in evidence.text
    assert 'return "alpha"' in evidence.text
    assert evidence.retrieval_result.score == 0.90


def test_semantic_context_respects_evidence_limit(
    tmp_path: Path,
) -> None:
    repository_index = _write_repository(
        tmp_path
    )

    retrieval = RoutedRetrievalResult(
        route=RetrievalRoute.SEMANTIC,
        results=(
            _result(
                path="src/sample/alpha.py",
                symbol="Alpha",
                score=0.90,
            ),
            _result(
                path="src/sample/beta.py",
                symbol="Beta",
                score=0.80,
            ),
            _result(
                path="src/sample/gamma.py",
                symbol="Gamma",
                score=0.70,
            ),
        ),
    )

    builder = ContextBuilder(
        repository_root=tmp_path,
        repository_index=repository_index,
        policy=ContextPolicy(
            semantic_evidence_limit=2,
        ),
    )

    bundle = builder.build(
        retrieval
    )

    assert bundle.evidence_count == 2

    assert tuple(
        item.retrieval_result.document.path
        for item in bundle.evidence
    ) == (
        PurePosixPath(
            "src/sample/alpha.py"
        ),
        PurePosixPath(
            "src/sample/beta.py"
        ),
    )


def test_semantic_context_preserves_retrieval_scores(
    tmp_path: Path,
) -> None:
    repository_index = _write_repository(
        tmp_path
    )

    retrieval = RoutedRetrievalResult(
        route=RetrievalRoute.SEMANTIC,
        results=(
            _result(
                path="src/sample/alpha.py",
                symbol="Alpha",
                score=0.91,
            ),
            _result(
                path="src/sample/beta.py",
                symbol="Beta",
                score=0.72,
            ),
        ),
    )

    builder = ContextBuilder(
        repository_root=tmp_path,
        repository_index=repository_index,
    )

    bundle = builder.build(
        retrieval
    )

    assert tuple(
        item.retrieval_result.score
        for item in bundle.evidence
    ) == (
        0.91,
        0.72,
    )


def test_semantic_context_rejects_unknown_symbol(
    tmp_path: Path,
) -> None:
    repository_index = _write_repository(
        tmp_path
    )

    retrieval = RoutedRetrievalResult(
        route=RetrievalRoute.SEMANTIC,
        results=(
            _result(
                path="src/sample/alpha.py",
                symbol="Missing",
                score=0.90,
            ),
        ),
    )

    builder = ContextBuilder(
        repository_root=tmp_path,
        repository_index=repository_index,
    )

    with pytest.raises(
        ContextBuildError,
        match=(
            "Semantic retrieval evidence "
            "could not be represented"
        ),
    ):
        builder.build(
            retrieval
        )


def test_empty_semantic_retrieval_produces_empty_context(
    tmp_path: Path,
) -> None:
    repository_index = _write_repository(
        tmp_path
    )

    retrieval = RoutedRetrievalResult(
        route=RetrievalRoute.SEMANTIC,
        results=(),
    )

    builder = ContextBuilder(
        repository_root=tmp_path,
        repository_index=repository_index,
    )

    bundle = builder.build(
        retrieval
    )

    assert bundle.evidence_count == 0
    assert bundle.character_count == 0
    assert bundle.unique_file_count == 0

def test_exact_context_rejects_multiple_results(
    tmp_path: Path,
) -> None:
    repository_index = _write_repository(
        tmp_path
    )

    first = _result(
        path="src/sample/alpha.py",
        symbol="Alpha",
        score=1.0,
    )

    second = _result(
        path="src/sample/beta.py",
        symbol="Beta",
        score=1.0,
    )

    retrieval = RoutedRetrievalResult(
        route=RetrievalRoute.EXACT_SYMBOL,
        results=(
            first,
            second,
        ),
    )

    builder = ContextBuilder(
        repository_root=tmp_path,
        repository_index=repository_index,
    )

    with pytest.raises(
        ContextBuildError,
        match=(
            "Exact-symbol retrieval must "
            "contain exactly one result"
        ),
    ):
        builder.build(
            retrieval
        )