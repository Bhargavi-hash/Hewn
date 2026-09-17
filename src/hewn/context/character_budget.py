from __future__ import annotations

from collections.abc import Sequence

from hewn.context.models import (
    ContextBundle,
    ContextEvidence,
)
from hewn.retrieval.models import RetrievalResult


def select_by_character_budget(
    results: Sequence[RetrievalResult],
    *,
    budget: int,
) -> ContextBundle:
    if budget < 1:
        raise ValueError(
            "Character budget must be at least 1"
        )

    selected: list[ContextEvidence] = []
    used_characters = 0

    for result in results:
        evidence = ContextEvidence(result)
        evidence_characters = len(
            evidence.text
        )

        if not selected:
            selected.append(evidence)
            used_characters += (
                evidence_characters
            )
            continue

        if (
            used_characters
            + evidence_characters
            > budget
        ):
            continue

        selected.append(evidence)
        used_characters += evidence_characters

    return ContextBundle(
        evidence=tuple(selected)
    )