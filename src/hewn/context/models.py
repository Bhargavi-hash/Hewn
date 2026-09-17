from __future__ import annotations

from dataclasses import dataclass

from hewn.retrieval.models import RetrievalResult


@dataclass(frozen=True, slots=True)
class ContextEvidence:
    retrieval_result: RetrievalResult

    @property
    def text(self) -> str:
        return self.retrieval_result.document.text


@dataclass(frozen=True, slots=True)
class ContextBundle:
    evidence: tuple[ContextEvidence, ...]

    @property
    def character_count(self) -> int:
        return sum(
            len(item.text)
            for item in self.evidence
        )

    @property
    def evidence_count(self) -> int:
        return len(self.evidence)

    @property
    def unique_file_count(self) -> int:
        return len(
            {
                item.retrieval_result.document.path
                for item in self.evidence
            }
        )