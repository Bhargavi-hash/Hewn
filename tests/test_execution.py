from __future__ import annotations

import shutil
import sys
from pathlib import Path

import pytest

from hewn.execution import (
    BubblewrapExecutionBackend,
    DirectExecutionBackend,
    ExecutionError,
)
from hewn.workspace import Workspace


def test_direct_backend_executes_in_workspace(
    tmp_path: Path,
) -> None:
    workspace = Workspace(tmp_path)
    backend = DirectExecutionBackend()

    result = backend.run(
        [
            sys.executable,
            "-c",
            (
                "from pathlib import Path; "
                "print(Path.cwd().name)"
            ),
        ],
        workspace=workspace,
        timeout_seconds=10.0,
    )

    assert result.returncode == 0
    assert result.stdout.strip() == tmp_path.name


def test_bubblewrap_command_uses_expected_isolation_boundaries(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace = Workspace(tmp_path)
    backend = BubblewrapExecutionBackend()

    real_which = shutil.which

    def fake_which(name: str) -> str | None:
        if name == "bwrap":
            return "/usr/bin/bwrap"
        return real_which(name)

    monkeypatch.setattr(shutil, "which", fake_which)

    command = backend.build_command(
        [sys.executable, "-c", "print('ok')"],
        workspace=workspace,
    )

    assert command[0] == "/usr/bin/bwrap"
    assert "--die-with-parent" in command
    assert "--new-session" in command
    assert "--unshare-user" in command
    assert "--unshare-pid" in command
    assert "--unshare-ipc" in command
    assert "--unshare-uts" in command
    assert "--unshare-net" in command
    assert "--clearenv" in command
    assert "--tmpfs" in command

    assert str(workspace.root) in command
    assert "/workspace" in command

    separator = command.index("--")
    sandboxed_command = command[separator + 1 :]

    assert sandboxed_command[0].startswith(
        "/runtime/python/bin/python"
    )


def test_bubblewrap_missing_fails_closed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace = Workspace(tmp_path)
    backend = BubblewrapExecutionBackend()

    real_which = shutil.which

    def fake_which(name: str) -> str | None:
        if name == "bwrap":
            return None
        return real_which(name)

    monkeypatch.setattr(shutil, "which", fake_which)

    with pytest.raises(
        ExecutionError,
        match="refusing to fall back",
    ):
        backend.build_command(
            [sys.executable, "-c", "print('ok')"],
            workspace=workspace,
        )


def test_bubblewrap_rejects_unmapped_executable(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace = Workspace(tmp_path)
    backend = BubblewrapExecutionBackend()

    real_which = shutil.which

    def fake_which(name: str) -> str | None:
        if name == "bwrap":
            return "/usr/bin/bwrap"
        return real_which(name)

    monkeypatch.setattr(shutil, "which", fake_which)

    with pytest.raises(
        ExecutionError,
        match="no runtime mapping",
    ):
        backend.build_command(
            ["/some/unapproved/executable"],
            workspace=workspace,
        )


def test_bubblewrap_clears_inherited_environment(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace = Workspace(tmp_path)
    backend = BubblewrapExecutionBackend()

    real_which = shutil.which

    def fake_which(name: str) -> str | None:
        if name == "bwrap":
            return "/usr/bin/bwrap"
        return real_which(name)

    monkeypatch.setattr(shutil, "which", fake_which)

    command = backend.build_command(
        [sys.executable, "-c", "print('ok')"],
        workspace=workspace,
    )

    clear_index = command.index("--clearenv")
    separator = command.index("--")

    assert clear_index < separator
    assert "--setenv" in command

def test_bubblewrap_executes_real_pytest(
    tmp_path: Path,
) -> None:
    if sys.platform != "linux":
        pytest.skip("Bubblewrap integration test requires Linux")

    if shutil.which("bwrap") is None:
        pytest.skip("Bubblewrap is not installed")

    (tmp_path / "test_example.py").write_text(
        "def test_example() -> None:\n"
        "    assert 2 + 2 == 4\n",
        encoding="utf-8",
    )

    workspace = Workspace(tmp_path)
    backend = BubblewrapExecutionBackend()

    result = backend.run(
        [
            sys.executable,
            "-B",
            "-m",
            "pytest",
            "-q",
        ],
        workspace=workspace,
        timeout_seconds=30.0,
    )

    assert result.returncode == 0
    assert "1 passed" in result.stdout