from __future__ import annotations

from pathlib import Path

import numpy as np
from bootstrap import build_repository_map_bootstrap

from hewn.agent import Agent
from hewn.authority import AuthorityGrant, AuthorityPolicy
from hewn.builtin_tools import make_builtin_tool_registry
from hewn.completion import CompletionRequirement
from hewn.context.builder import ContextBuilder
from hewn.models import FinalResponse, Message
from hewn.repository.index import RepositoryIndex
from hewn.retrieval.semantic import EmbeddingModel
from hewn.retrieval.semantic_index import SemanticIndex
from hewn.retrieval.symbol_documents import build_symbol_documents
from hewn.session import HewnSession
from hewn.tools import ToolExecutor
from hewn.workspace import Workspace


class FakeEmbeddingModel(EmbeddingModel):
    def encode(
        self,
        texts: list[str],
    ) -> np.ndarray:
        return np.ones(
            (len(texts), 4),
            dtype=np.float32,
        )


class RecordingFinalModel:
    def __init__(self) -> None:
        self.messages: list[Message] | None = None

    def respond(
        self,
        *,
        messages: list[Message],
        tools: object,
    ) -> FinalResponse:
        del tools
        self.messages = list(messages)
        return FinalResponse(text="done")


def test_repository_bootstrap_is_not_model_tool_call(
    tmp_path: Path,
) -> None:
    source = tmp_path / "sample.py"
    source.write_text(
        "def make_slug(text: str) -> str:\n"
        "    return text.lower()\n",
        encoding="utf-8",
    )

    workspace = Workspace(tmp_path)
    repository_index = RepositoryIndex.build(tmp_path)

    embedding_model = FakeEmbeddingModel()

    semantic_index = SemanticIndex.build(
        build_symbol_documents(repository_index),
        model=embedding_model,
    )

    context_builder = ContextBuilder(
        repository_root=tmp_path,
        repository_index=repository_index,
    )

    registry = make_builtin_tool_registry(
        workspace,
        repository_index,
    )

    executor = ToolExecutor(
        registry,
        authority_policy=AuthorityPolicy(
            AuthorityGrant(
                repository_read=True,
                repository_write=True,
                approved_checks=True,
            )
        ),
    )

    model = RecordingFinalModel()

    agent = Agent(
        model=model,
        registry=registry,
        executor=executor,
    )

    session = HewnSession(
        agent=agent,
        repository_index=repository_index,
        semantic_index=semantic_index,
        embedding_model=embedding_model,
        context_builder=context_builder,
    )

    request = "Inspect make_slug."

    prepared = session.prepare_context(request)

    messages, observation = build_repository_map_bootstrap(
        agent,
        request,
        context=prepared.context,
    )

    assert "sample.py" in observation
    assert "make_slug" in observation

    result = agent.run_messages(
        messages,
        completion_requirement=CompletionRequirement.NONE,
    )

    assert result.text == "done"

    # The repository_map call was controller-initiated,
    # not selected by the model.
    assert result.metrics.tool_calls == 0
    assert result.metrics.successful_tool_calls == 0
    assert result.metrics.failed_tool_calls == 0

    assert model.messages is not None
    assert len(model.messages) == 3

    assert model.messages[0].role == "user"

    assert model.messages[1].role == "assistant"
    assert model.messages[1].content == (
        '{"arguments":{},"name":"repository_map","type":"tool_call"}'
    )

    assert model.messages[2].role == "tool"
    assert "sample.py" in model.messages[2].content
    assert "make_slug" in model.messages[2].content