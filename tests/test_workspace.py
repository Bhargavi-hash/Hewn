from pathlib import Path

import pytest

from hewn.workspace import Workspace, WorkspaceViolationError


def test_workspace_resolves_internal_path(tmp_path: Path) -> None:
    workspace = Workspace(tmp_path)

    result = workspace.resolve("src/hewn/tools.py")

    assert result == tmp_path / "src/hewn/tools.py"


def test_workspace_allows_normalized_internal_path(tmp_path: Path) -> None:
    workspace = Workspace(tmp_path)

    result = workspace.resolve("src/../README.md")

    assert result == tmp_path / "README.md"


def test_workspace_rejects_parent_escape(tmp_path: Path) -> None:
    workspace = Workspace(tmp_path)

    with pytest.raises(
        WorkspaceViolationError,
        match="Path escapes workspace",
    ):
        workspace.resolve("../secret.txt")


def test_workspace_rejects_absolute_external_path(tmp_path: Path) -> None:
    workspace = Workspace(tmp_path)

    with pytest.raises(
        WorkspaceViolationError,
        match="Path escapes workspace",
    ):
        workspace.resolve("/etc/passwd")

def test_workspace_rejects_symlink_escape(tmp_path: Path) -> None:
    outside = tmp_path.parent / "outside-secret.txt"
    outside.write_text("secret")

    link = tmp_path / "innocent.txt"
    link.symlink_to(outside)

    workspace = Workspace(tmp_path)

    with pytest.raises(
        WorkspaceViolationError,
        match="Path escapes workspace",
    ):
        workspace.resolve("innocent.txt")