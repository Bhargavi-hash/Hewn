from __future__ import annotations

import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from hewn.workspace import Workspace


@dataclass(frozen=True)
class ExecutionResult:
    returncode: int
    stdout: str
    stderr: str


class ExecutionError(RuntimeError):
    """Execution could not be started safely."""


class ExecutionTimeoutError(ExecutionError):
    """Execution exceeded its configured timeout."""


class ProcessExecutionBackend(Protocol):
    """Execution boundary used by process-capable Hewn tools."""

    def run(
        self,
        command: list[str],
        *,
        workspace: Workspace,
        timeout_seconds: float,
    ) -> ExecutionResult: ...


class DirectExecutionBackend:
    """Execute a command directly with the authority of the Hewn process."""

    def run(
        self,
        command: list[str],
        *,
        workspace: Workspace,
        timeout_seconds: float,
    ) -> ExecutionResult:
        try:
            completed = subprocess.run(
                command,
                cwd=workspace.root,
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
                check=False,
            )
        except FileNotFoundError as exc:
            raise ExecutionError(
                f"Required executable not found: {command[0]}"
            ) from exc
        except subprocess.TimeoutExpired as exc:
            raise ExecutionTimeoutError(
                f"Execution timed out after {timeout_seconds:g} seconds"
            ) from exc

        return ExecutionResult(
            returncode=completed.returncode,
            stdout=completed.stdout,
            stderr=completed.stderr,
        )


class BubblewrapExecutionBackend:
    """Run approved development commands inside a Linux Bubblewrap boundary."""

    _SANDBOX_WORKSPACE = Path("/workspace")
    _SANDBOX_PYTHON_BASE = Path("/runtime/python")
    _SANDBOX_VENV = Path("/runtime/venv")

    def run(
        self,
        command: list[str],
        *,
        workspace: Workspace,
        timeout_seconds: float,
    ) -> ExecutionResult:
        sandbox_command = self.build_command(
            command,
            workspace=workspace,
        )

        try:
            completed = subprocess.run(
                sandbox_command,
                cwd=workspace.root,
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
                check=False,
            )
        except FileNotFoundError as exc:
            raise ExecutionError(
                "Required sandbox executable not found: bwrap"
            ) from exc
        except subprocess.TimeoutExpired as exc:
            raise ExecutionTimeoutError(
                f"Execution timed out after {timeout_seconds:g} seconds"
            ) from exc

        return ExecutionResult(
            returncode=completed.returncode,
            stdout=completed.stdout,
            stderr=completed.stderr,
        )

    def build_command(
        self,
        command: list[str],
        *,
        workspace: Workspace,
    ) -> list[str]:
        bwrap = shutil.which("bwrap")

        if bwrap is None:
            raise ExecutionError(
                "Sandboxed execution requires Bubblewrap (bwrap); "
                "refusing to fall back to direct execution."
            )

        argv = [
            bwrap,
            "--die-with-parent",
            "--new-session",
            "--unshare-user",
            "--unshare-pid",
            "--unshare-ipc",
            "--unshare-uts",
            "--unshare-net",
            "--proc",
            "/proc",
            "--dev",
            "/dev",
            "--tmpfs",
            "/tmp",
            "--dir",
            "/runtime",
            "--dir",
            str(self._SANDBOX_WORKSPACE),
            "--ro-bind",
            "/usr",
            "/usr",
            "--symlink",
            "usr/bin",
            "/bin",
            "--symlink",
            "usr/lib",
            "/lib",
            "--symlink",
            "usr/lib64",
            "/lib64",
        ]

        for source, destination in self._runtime_mounts():
            argv.extend(
                [
                    "--ro-bind",
                    str(source),
                    str(destination),
                ]
            )

        argv.extend(
            [
                "--bind",
                str(workspace.root),
                str(self._SANDBOX_WORKSPACE),
                "--chdir",
                str(self._SANDBOX_WORKSPACE),
                "--clearenv",
            ]
        )

        for name, value in self._sandbox_environment().items():
            argv.extend(
                [
                    "--setenv",
                    name,
                    value,
                ]
            )

        argv.append("--")
        argv.extend(self._translate_command(command))

        return argv

    def _runtime_mounts(self) -> list[tuple[Path, Path]]:
        mounts = [
            (
                Path(sys.base_prefix).resolve(),
                self._SANDBOX_PYTHON_BASE,
            ),
            (
                Path(sys.prefix).resolve(),
                self._SANDBOX_VENV,
            ),
        ]

        for source, _ in mounts:
            if not source.exists():
                raise ExecutionError(
                    "Required runtime path does not exist: "
                    f"{source}"
                )

        return mounts

    def _sandbox_environment(self) -> dict[str, str]:
        site_packages = (
            self._SANDBOX_VENV
            / "lib"
            / f"python{sys.version_info.major}.{sys.version_info.minor}"
            / "site-packages"
        )

        return {
            "PATH": (
                f"{self._SANDBOX_VENV}/bin:"
                f"{self._SANDBOX_PYTHON_BASE}/bin:"
                "/usr/bin:/bin"
            ),
            "PYTHONPATH": str(site_packages),
            "HOME": "/tmp",
            "TMPDIR": "/tmp",
            "VIRTUAL_ENV": str(self._SANDBOX_VENV),
            "PYTHONNOUSERSITE": "1",
            "PYTHONDONTWRITEBYTECODE": "1",
            "LANG": "C.UTF-8",
            "LC_ALL": "C.UTF-8",
        }

    def _translate_command(
        self,
        command: list[str],
    ) -> list[str]:
        if not command:
            raise ExecutionError("Cannot execute an empty command.")

        executable = Path(command[0]).resolve()

        current_python = Path(sys.executable).resolve()
        if executable == current_python:
            return [
                str(self._SANDBOX_PYTHON_BASE / "bin" / "python3"),
                *command[1:],
            ]

        current_ruff = shutil.which("ruff")
        if (
            current_ruff is not None
            and executable == Path(current_ruff).resolve()
        ):
            return [
                str(self._SANDBOX_VENV / "bin" / "ruff"),
                *command[1:],
            ]

        current_mypy = shutil.which("mypy")
        if (
            current_mypy is not None
            and executable == Path(current_mypy).resolve()
        ):
            return [
                str(self._SANDBOX_PYTHON_BASE / "bin" / "python3"),
                "-B",
                "-m",
                "mypy",
                *command[1:],
            ]

        raise ExecutionError(
            "Sandboxed execution has no runtime mapping for executable: "
            f"{command[0]}"
        )