from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ContextPolicy:
    """Configuration for converting retrieved evidence into model context."""

    semantic_evidence_limit: int = 3
    bounded_source_limit: int = 800

    def __post_init__(self) -> None:
        if self.semantic_evidence_limit < 1:
            raise ValueError(
                "Semantic evidence limit must be at least 1"
            )

        if self.bounded_source_limit < 1:
            raise ValueError(
                "Bounded source limit must be at least 1"
            )