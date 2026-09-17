from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from hewn.context.models import (
    ContextBundle,
    ContextEvidence,
)
from hewn.context.policy import ContextPolicy
from hewn.context.source import (
    build_bounded_source_document,
    resolve_document_symbol,
)
from hewn.repository.index import RepositoryIndex
from hewn.retrieval.models import (
    RepositoryDocument,
    RetrievalResult,
)
from hewn.retrieval.router import (
    RetrievalRoute,
    RoutedRetrievalResult,
)


class ContextBuildError(ValueError):
    """Raised when retrieved evidence cannot be converted into context."""


@dataclass(frozen=True, slots=True)
class ContextBuilder:
    repository_root: Path
    repository_index: RepositoryIndex
    policy: ContextPolicy = field(
        default_factory=ContextPolicy,
    )

    def build(
        self,
        retrieval: RoutedRetrievalResult,
    ) -> ContextBundle:
        if not retrieval.results:
            return ContextBundle(
                evidence=(),
            )

        if retrieval.route is RetrievalRoute.EXACT_SYMBOL:
            return self._build_exact_context(
                retrieval
            )

        if retrieval.route is RetrievalRoute.SEMANTIC:
            return self._build_semantic_context(
                retrieval
            )

        raise ContextBuildError(
            f"Unsupported retrieval route: {retrieval.route}"
        )

    def _build_exact_context(
        self,
        retrieval: RoutedRetrievalResult,
    ) -> ContextBundle:
        if len(retrieval.results) != 1:
            raise ContextBuildError(
                "Exact-symbol retrieval must contain exactly one result"
            )

        result = retrieval.results[0]

        return ContextBundle(
            evidence=(
                ContextEvidence(
                    retrieval_result=result,
                ),
            ),
        )

    def _build_semantic_context(
        self,
        retrieval: RoutedRetrievalResult,
    ) -> ContextBundle:
        selected = self._select_unique_files(
            retrieval.results
        )

        evidence = tuple(
            ContextEvidence(
                retrieval_result=(
                    self._represent_semantic_result(
                        result
                    )
                ),
            )
            for result in selected
        )

        return ContextBundle(
            evidence=evidence,
        )

    def _select_unique_files(
        self,
        results: tuple[RetrievalResult, ...],
    ) -> tuple[RetrievalResult, ...]:
        selected: list[RetrievalResult] = []
        seen_paths: set[str] = set()

        for result in results:
            path = str(
                result.document.path
            )

            if path in seen_paths:
                continue

            seen_paths.add(path)
            selected.append(result)

            if (
                len(selected)
                >= self.policy.semantic_evidence_limit
            ):
                break

        return tuple(selected)

    def _represent_semantic_result(
        self,
        result: RetrievalResult,
    ) -> RetrievalResult:
        try:
            symbol = resolve_document_symbol(
                result.document,
                self.repository_index,
            )

            document = build_bounded_source_document(
                repository_root=self.repository_root,
                symbol=symbol,
                character_limit=(
                    self.policy.bounded_source_limit
                ),
            )
        except ValueError as exc:
            raise ContextBuildError(
                "Semantic retrieval evidence could not be represented: "
                f"{result.document.path}"
            ) from exc

        return self._replace_document(
            result,
            document=document,
        )

    @staticmethod
    def _replace_document(
        result: RetrievalResult,
        *,
        document: RepositoryDocument,
    ) -> RetrievalResult:
        return RetrievalResult(
            document=document,
            score=result.score,
        )