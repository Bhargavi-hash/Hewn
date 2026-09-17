from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

import numpy as np
import pytest
from numpy.typing import NDArray

from hewn.agent import Agent
from hewn.context.builder import ContextBuilder
from hewn.models import (
    FinalResponse,
    Message,
    ModelResponse,
)
from hewn.repository.index import RepositoryIndex
from hewn.retrieval.models import RepositoryDocument
from hewn.retrieval.router import RetrievalRoute
from hewn.retrieval.semantic_index import SemanticIndex
from hewn.session import HewnSession
from hewn.tools import (
    ToolDefinition,
    ToolExecutor,
    ToolRegistry,
)

FloatArray = NDArray[np.float32]


class RecordingModel:
    def __init__(self) -> None:
        self.messages: Sequence[Message] | None = None

    def respond(
        self,
        messages: Sequence[Message],
        tools: Sequence[ToolDefinition],
    ) -> ModelResponse:
        self.messages = messages

        return FinalResponse(
            text="done"
        )


class FixedEmbeddingModel:
    def encode(
        self,
        texts: Sequence[str],
    ) -> FloatArray:
        embeddings: list[list[float]] = []

        for text in texts:
            if "Alpha" in text:
                embeddings.append(
                    [1.0, 0.0]
                )
            elif "Beta" in text:
                embeddings.append(
                    [0.8, 0.2]
                )
            else:
                embeddings.append(
                    [0.0, 1.0]
                )

        return np.asarray(
            embeddings,
            dtype=np.float32,
        )


def _build_repository(
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

    return RepositoryIndex.build(
        root
    )


def _build_documents(
    repository_index: RepositoryIndex,
) -> tuple[RepositoryDocument, ...]:
    documents: list[RepositoryDocument] = []

    for source_file in repository_index.files.values():
        for symbol in source_file.symbols:
            documents.append(
                RepositoryDocument(
                    path=symbol.location.path,
                    symbol=symbol.qualified_name,
                    text=(
                        f"path: {symbol.location.path}\n"
                        f"symbol: {symbol.qualified_name}\n"
                        f"kind: {symbol.kind.value}"
                    ),
                )
            )

    return tuple(documents)


def _build_session(
    root: Path,
) -> tuple[
    HewnSession,
    RecordingModel,
]:
    repository_index = _build_repository(
        root
    )

    documents = _build_documents(
        repository_index
    )

    embedding_model = FixedEmbeddingModel()

    semantic_index = SemanticIndex.build(
        documents,
        model=embedding_model,
    )

    model = RecordingModel()
    registry = ToolRegistry()

    agent = Agent(
        model=model,
        registry=registry,
        executor=ToolExecutor(
            registry
        ),
    )

    context_builder = ContextBuilder(
        repository_root=root,
        repository_index=repository_index,
    )

    session = HewnSession(
        agent=agent,
        repository_index=repository_index,
        semantic_index=semantic_index,
        embedding_model=embedding_model,
        context_builder=context_builder,
    )

    return session, model


def test_session_rejects_invalid_candidate_limit(
    tmp_path: Path,
) -> None:
    session, _ = _build_session(
        tmp_path
    )

    with pytest.raises(
        ValueError,
        match=(
            "Semantic candidate limit "
            "must be at least 1"
        ),
    ):
        HewnSession(
            agent=session.agent,
            repository_index=session.repository_index,
            semantic_index=session.semantic_index,
            embedding_model=session.embedding_model,
            context_builder=session.context_builder,
            semantic_candidate_limit=0,
        )


def test_session_prepares_exact_symbol_context(
    tmp_path: Path,
) -> None:
    session, _ = _build_session(
        tmp_path
    )

    prepared = session.prepare_context(
        "Where is Alpha defined?"
    )

    assert (
        prepared.retrieval.route
        is RetrievalRoute.EXACT_SYMBOL
    )

    assert prepared.context.evidence_count == 1

    document = (
        prepared.context
        .evidence[0]
        .retrieval_result
        .document
    )

    assert str(document.path) == (
        "src/sample/alpha.py"
    )

    assert document.symbol == "Alpha"


def test_session_prepares_semantic_context(
    tmp_path: Path,
) -> None:
    session, _ = _build_session(
        tmp_path
    )

    prepared = session.prepare_context(
        "Which code returns the alpha value?"
    )

    assert (
        prepared.retrieval.route
        is RetrievalRoute.SEMANTIC
    )

    assert prepared.context.evidence_count >= 1
    assert prepared.context.unique_file_count >= 1


def test_session_injects_prepared_context_into_agent(
    tmp_path: Path,
) -> None:
    session, model = _build_session(
        tmp_path
    )

    result = session.run(
        "Where is Alpha defined?"
    )

    assert result.text == "done"
    assert model.messages is not None

    initial_message = model.messages[0].content

    assert "Where is Alpha defined?" in initial_message
    assert "Relevant repository evidence" in initial_message
    assert "src/sample/alpha.py" in initial_message
    assert "Alpha" in initial_message


def test_prepare_context_does_not_call_coding_model(
    tmp_path: Path,
) -> None:
    session, model = _build_session(
        tmp_path
    )

    prepared = session.prepare_context(
        "Where is Alpha defined?"
    )

    assert prepared.context.evidence_count == 1
    assert model.messages is None