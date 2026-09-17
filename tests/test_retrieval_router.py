from collections.abc import Sequence
from pathlib import Path

import numpy as np
from numpy.typing import NDArray

from hewn.repository.index import RepositoryIndex
from hewn.retrieval.router import (
    RetrievalRoute,
    extract_identifier_candidates,
    find_explicit_symbol,
    retrieve_routed,
)
from hewn.retrieval.semantic_index import SemanticIndex
from hewn.retrieval.symbol_documents import (
    build_symbol_documents,
)

FloatArray = NDArray[np.float32]


class FakeEmbeddingModel:
    def encode(
        self,
        texts: Sequence[str],
    ) -> FloatArray:
        vectors: list[list[float]] = []

        for text in texts:
            lowered = text.lower()

            if "workspace" in lowered:
                vectors.append([1.0, 0.0])

            elif "executor" in lowered:
                vectors.append([0.0, 1.0])

            else:
                vectors.append([0.0, 0.0])

        return np.asarray(
            vectors,
            dtype=np.float32,
        )


def build_test_repository(
    tmp_path: Path,
) -> RepositoryIndex:
    package = tmp_path / "src" / "example"
    package.mkdir(parents=True)

    (package / "tools.py").write_text(
        (
            "class ToolExecutor:\n"
            "    def execute(self) -> None:\n"
            "        pass\n"
        ),
        encoding="utf-8",
    )

    (package / "workspace.py").write_text(
        (
            "class Workspace:\n"
            "    def resolve(self, path: str) -> str:\n"
            "        return path\n"
        ),
        encoding="utf-8",
    )

    return RepositoryIndex.build(tmp_path)


def test_extract_identifier_candidates() -> None:
    candidates = extract_identifier_candidates(
        "Find where ToolExecutor is defined."
    )

    assert candidates == (
        "Find",
        "where",
        "ToolExecutor",
        "is",
        "defined",
    )


def test_find_explicit_symbol_resolves_unique_symbol(
    tmp_path: Path,
) -> None:
    index = build_test_repository(
        tmp_path
    )

    symbol = find_explicit_symbol(
        "Find where ToolExecutor is defined.",
        index,
    )

    assert symbol is not None
    assert symbol.name == "ToolExecutor"


def test_find_explicit_symbol_returns_none_without_match(
    tmp_path: Path,
) -> None:
    index = build_test_repository(
        tmp_path
    )

    symbol = find_explicit_symbol(
        "What prevents file operations from escaping?",
        index,
    )

    assert symbol is None


def test_multiple_explicit_symbols_fall_back(
    tmp_path: Path,
) -> None:
    index = build_test_repository(
        tmp_path
    )

    symbol = find_explicit_symbol(
        "How does Workspace interact with ToolExecutor?",
        index,
    )

    assert symbol is None


def test_router_uses_exact_symbol_without_semantic_search(
    tmp_path: Path,
) -> None:
    index = build_test_repository(
        tmp_path
    )

    documents = build_symbol_documents(
        index,
        path_prefix="src",
    )

    model = FakeEmbeddingModel()

    semantic_index = SemanticIndex.build(
        documents,
        model=model,
    )

    routed = retrieve_routed(
        "Find where ToolExecutor is defined.",
        repository_index=index,
        semantic_index=semantic_index,
        model=model,
        semantic_limit=len(documents),
    )

    assert routed.route == RetrievalRoute.EXACT_SYMBOL
    assert routed.matched_symbol == "ToolExecutor"
    assert len(routed.results) == 1
    assert (
        str(routed.results[0].document.path)
        == "src/example/tools.py"
    )


def test_router_uses_semantic_for_conceptual_query(
    tmp_path: Path,
) -> None:
    index = build_test_repository(
        tmp_path
    )

    documents = build_symbol_documents(
        index,
        path_prefix="src",
    )

    model = FakeEmbeddingModel()

    semantic_index = SemanticIndex.build(
        documents,
        model=model,
    )

    routed = retrieve_routed(
        "What protects workspace paths?",
        repository_index=index,
        semantic_index=semantic_index,
        model=model,
        semantic_limit=len(documents),
    )

    assert routed.route == RetrievalRoute.SEMANTIC
    assert routed.matched_symbol is None