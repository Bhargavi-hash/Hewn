from __future__ import annotations

from dataclasses import dataclass
from pathlib import PurePosixPath


@dataclass(frozen=True, slots=True)
class RepositoryDocument:
    path: PurePosixPath
    text: str
    symbol: str | None = None

    def __post_init__(self) -> None:
        if (
            self.path.is_absolute()
            or ".." in self.path.parts
        ):
            raise ValueError(
                "Repository document path must remain "
                "repository-relative"
            )

        if not self.text.strip():
            raise ValueError(
                "Repository document text must not be empty"
            )

        if self.symbol == "":
            raise ValueError(
                "Repository document symbol must not be empty"
            )


@dataclass(frozen=True, slots=True)
class RetrievalResult:
    document: RepositoryDocument
    score: float