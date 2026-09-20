from __future__ import annotations

import shutil
import sys
from pathlib import Path

import pytest

from hewn.authority import AuthorityGrant, AuthorityPolicy
from hewn.builtin_tools import make_builtin_tool_registry
from hewn.execution import BubblewrapExecutionBackend
from hewn.tools import ToolCall, ToolExecutor
from hewn.workspace import Workspace


def make_secure_executor(
    workspace_root: Path,
    *,
    repository_read: bool = True,
    repository_write: bool = True,
    approved_checks: bool = True,
) -> ToolExecutor:
    workspace = Workspace(workspace_root)

    registry = make_builtin_tool_registry(
        workspace,
        execution_backend=BubblewrapExecutionBackend(),
    )

    policy = AuthorityPolicy(
        AuthorityGrant(
            repository_read=repository_read,
            repository_write=repository_write,
            approved_checks=approved_checks,
        )
    )

    return ToolExecutor(
        registry,
        authority_policy=policy,
    )


def test_authority_denial_prevents_repository_mutation(
    tmp_path: Path,
) -> None:
    target = tmp_path / "state.txt"
    target.write_text(
        "SAFE_MARKER=unchanged\n",
        encoding="utf-8",
    )

    executor = make_secure_executor(
        tmp_path,
        repository_write=False,
    )

    result = executor.execute(
        ToolCall(
            name="replace_text",
            arguments={
                "path": "state.txt",
                "old": "SAFE_MARKER=unchanged",
                "new": "SAFE_MARKER=modified",
            },
        )
    )

    assert result.ok is False
    assert result.error is not None
    assert result.error.startswith("Authority denied:")

    assert target.read_text(
        encoding="utf-8"
    ) == "SAFE_MARKER=unchanged\n"


def test_workspace_confinement_remains_independent_of_authority(
    tmp_path: Path,
) -> None:
    workspace_root = tmp_path / "repo"
    workspace_root.mkdir()

    outside = tmp_path / "outside.txt"
    outside.write_text(
        "outside\n",
        encoding="utf-8",
    )

    executor = make_secure_executor(
        workspace_root,
        repository_read=True,
    )

    result = executor.execute(
        ToolCall(
            name="read_file",
            arguments={
                "path": "../outside.txt",
            },
        )
    )

    assert result.ok is False
    assert result.error is not None
    assert "escapes workspace" in result.error.lower()


def test_check_authority_denial_prevents_process_execution(
    tmp_path: Path,
) -> None:
    executor = make_secure_executor(
        tmp_path,
        approved_checks=False,
    )

    result = executor.execute(
        ToolCall(
            name="run_check",
            arguments={
                "check": "tests",
            },
        )
    )

    assert result.ok is False
    assert result.error is not None
    assert result.error.startswith("Authority denied:")


def test_authorized_check_executes_inside_sandbox(
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

    executor = make_secure_executor(tmp_path)

    result = executor.execute(
        ToolCall(
            name="run_check",
            arguments={
                "check": "tests",
            },
        )
    )

    assert result.ok is True
    assert "1 passed" in (result.output or "")


def test_sandboxed_check_cannot_read_external_file(
    tmp_path: Path,
) -> None:
    if sys.platform != "linux":
        pytest.skip("Bubblewrap integration test requires Linux")

    if shutil.which("bwrap") is None:
        pytest.skip("Bubblewrap is not installed")

    workspace_root = tmp_path / "repo"
    workspace_root.mkdir()

    outside = tmp_path / "outside.txt"
    outside.write_text(
        "external sentinel\n",
        encoding="utf-8",
    )

    marker = workspace_root / "external-read-observed.txt"

    sandbox_marker = (
        Path("/workspace")
        / marker.name
    )

    test_source = (
        "from pathlib import Path\n\n"
        "def test_external_read() -> None:\n"
        f"    external = Path({str(outside)!r})\n"
        f"    marker = Path({str(sandbox_marker)!r})\n"
        "    try:\n"
        "        value = external.read_text(encoding='utf-8')\n"
        "    except (FileNotFoundError, PermissionError):\n"
        "        return\n"
        "    marker.write_text(value, encoding='utf-8')\n"
    )

    (
        workspace_root / "test_external.py"
    ).write_text(
        test_source,
        encoding="utf-8",
    )

    executor = make_secure_executor(
        workspace_root,
        approved_checks=True,
    )

    result = executor.execute(
        ToolCall(
            name="run_check",
            arguments={
                "check": "tests",
            },
        )
    )

    assert result.ok is True
    assert marker.exists() is False