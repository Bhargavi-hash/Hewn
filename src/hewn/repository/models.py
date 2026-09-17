from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from pathlib import PurePosixPath


class SymbolKind(StrEnum):
    CLASS = "class"
    FUNCTION = "function"
    METHOD = "method"


def _validate_repository_path(path: PurePosixPath) -> None:
    if path.is_absolute() or ".." in path.parts:
        raise ValueError(
            "Repository path must remain repository-relative"
        )


@dataclass(frozen=True, slots=True)
class SourceLocation:
    path: PurePosixPath
    start_line: int
    end_line: int

    def __post_init__(self) -> None:
        _validate_repository_path(self.path)

        if self.start_line < 1:
            raise ValueError("start_line must be at least 1")

        if self.end_line < self.start_line:
            raise ValueError(
                "end_line must not precede start_line"
            )


@dataclass(frozen=True, slots=True)
class Symbol:
    name: str
    kind: SymbolKind
    location: SourceLocation
    qualified_name: str
    signature: str | None = None

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError(
                "Symbol name must not be empty"
            )

        if not self.qualified_name:
            raise ValueError(
                "Symbol qualified_name must not be empty"
            )

        if (
            self.kind is SymbolKind.CLASS
            and self.signature is not None
        ):
            raise ValueError(
                "Class symbols must not have signatures"
            )

@dataclass(frozen=True, slots=True)
class Import:
    module: str
    name: str | None
    alias: str | None
    location: SourceLocation

    def __post_init__(self) -> None:
        if not self.module and self.name is None:
            raise ValueError(
                "Import must identify a module or imported name"
            )


@dataclass(frozen=True, slots=True)
class SourceFile:
    path: PurePosixPath
    language: str
    symbols: tuple[Symbol, ...]
    imports: tuple[Import, ...]

    def __post_init__(self) -> None:
        _validate_repository_path(self.path)

        if not self.language:
            raise ValueError(
                "Source file language must not be empty"
            )


@dataclass(frozen=True, slots=True)
class FileDependency:
    source: PurePosixPath
    target: PurePosixPath

    def __post_init__(self) -> None:
        _validate_repository_path(self.source)
        _validate_repository_path(self.target)