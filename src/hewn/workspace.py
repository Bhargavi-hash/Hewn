from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


class WorkspaceViolationError(ValueError):
    """A path attempts to escape the configured workspace."""


@dataclass(frozen=True)
class Workspace:
    root: Path  # Represents a capability boundary
                #   Workspace(
                #     root=Path("/home/bhargavi/Documents/Hewn")
                #   )
                # Example: Hewn's repo operations are to this filesystem tree.

    def __post_init__(self) -> None:
        object.__setattr__(self, "root", self.root.resolve())

    def resolve(self, path: str) -> Path:
        candidate = (self.root / path).resolve()

        if not candidate.is_relative_to(self.root): # Is the candidate somewhere underneath the path?
            raise WorkspaceViolationError(
                f"Path escapes workspace: {path}"
            )

        return candidate