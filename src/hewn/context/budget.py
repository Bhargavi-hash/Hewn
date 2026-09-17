from __future__ import annotations

from collections.abc import Sequence

from hewn.context.models import (
    ContextBundle,
    ContextEvidence,
)
from hewn.retrieval.models import RetrievalResult


def select_by_evidence_count(
    results: Sequence[RetrievalResult],
    *,
    limit: int,
) -> ContextBundle:
    if limit < 1:
        raise ValueError(
            "Evidence limit must be at least 1"
        )

    selected = tuple(
        ContextEvidence(result)
        for result in results[:limit]
    )

    return ContextBundle(
        evidence=selected
    )