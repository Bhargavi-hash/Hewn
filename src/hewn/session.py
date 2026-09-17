from __future__ import annotations

from dataclasses import dataclass

from hewn.agent import Agent, AgentRunResult
from hewn.completion import CompletionRequirement
from hewn.context.builder import ContextBuilder
from hewn.context.models import ContextBundle
from hewn.repository.index import RepositoryIndex
from hewn.retrieval.router import (
    RoutedRetrievalResult,
    retrieve_routed,
)
from hewn.retrieval.semantic import EmbeddingModel
from hewn.retrieval.semantic_index import SemanticIndex


@dataclass(frozen=True, slots=True)
class PreparedContext:
    retrieval: RoutedRetrievalResult
    context: ContextBundle


@dataclass(slots=True)
class HewnSession:
    agent: Agent
    repository_index: RepositoryIndex
    semantic_index: SemanticIndex
    embedding_model: EmbeddingModel
    context_builder: ContextBuilder
    semantic_candidate_limit: int = 12

    def __post_init__(self) -> None:
        if self.semantic_candidate_limit < 1:
            raise ValueError(
                "Semantic candidate limit must be at least 1"
            )

    def prepare_context(
        self,
        user_request: str,
    ) -> PreparedContext:
        retrieval = retrieve_routed(
            user_request,
            repository_index=self.repository_index,
            semantic_index=self.semantic_index,
            model=self.embedding_model,
            semantic_limit=self.semantic_candidate_limit,
        )

        context = self.context_builder.build(
            retrieval
        )

        return PreparedContext(
            retrieval=retrieval,
            context=context,
        )

    def run(
        self,
        user_request: str,
        *,
        completion_requirement: CompletionRequirement = (
            CompletionRequirement.NONE
        ),
    ) -> AgentRunResult:
        prepared = self.prepare_context(
            user_request
        )

        return self.agent.run(
            user_request,
            completion_requirement=completion_requirement,
            context=prepared.context,
        )