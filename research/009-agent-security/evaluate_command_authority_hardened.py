from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, cast

from hewn.tools import (
    ToolCall,
    ToolDefinition,
    ToolError,
    ToolExecutor,
    ToolRegistry,
    ToolResult,
)
from hewn.workspace import Workspace

RESEARCH_ROOT = Path(__file__).resolve().parent
MANIFEST_PATH = RESEARCH_ROOT / "fixtures" / "manifest.json"
RESULTS_ROOT = RESEARCH_ROOT / "results"

SYNTHETIC_SECRET_NAME = "HEWN_009B_SYNTHETIC_SECRET"
SYNTHETIC_SECRET_VALUE = "hewn-009b-disposable-value"

DEFAULT_TIMEOUT_SECONDS = 30.0
DEFAULT_OUTPUT_LIMIT = 12_000

SANDBOX_WORKSPACE = Path("/workspace")
SANDBOX_PYTHON_BASE = Path("/runtime/python")
SANDBOX_VENV = Path("/runtime/venv")


CHECK_COMMANDS = {
    "tests": [
        str(SANDBOX_PYTHON_BASE / "bin" / "python3.12"),
        "-B",
        "-m",
        "pytest",
        "-q",
    ],
    "lint": [
        str(SANDBOX_VENV / "bin" / "ruff"),
        "check",
        ".",
    ],
    "types": [
        str(SANDBOX_PYTHON_BASE / "bin" / "python3.12"),
        "-B",
        "-m",
        "mypy",
        "src",
        "tests",
    ],
}


@dataclass(frozen=True)
class CaseResult:
    case_id: str
    category: str
    scenario: str
    expected_tool: str
    observed_tool: str
    tool_expectation_matched: bool
    baseline_external_effect: bool
    desired_external_effect: bool
    observed_external_effect: bool
    hardened_effect_matched: bool
    tool_ok: bool
    tool_error: str | None
    effect_detail: str | None


def load_manifest() -> dict[str, Any]:
    raw = json.loads(
        MANIFEST_PATH.read_text(encoding="utf-8")
    )

    if not isinstance(raw, dict):
        raise TypeError(
            "fixture manifest must be a JSON object"
        )

    data = cast(dict[str, Any], raw)

    command_cases = data.get("command_cases")
    if not isinstance(command_cases, list):
        raise TypeError(
            "manifest command_cases must be a list"
        )

    expected_ids = {
        f"cmd-{index:03d}"
        for index in range(1, 12)
    }
    actual_ids = {
        str(case["id"])
        for case in command_cases
    }

    if actual_ids != expected_ids:
        raise ValueError(
            "009B-H requires the frozen cmd-001 "
            "through cmd-011 corpus"
        )

    return data


def combine_output(
    stdout: str,
    stderr: str,
) -> str:
    parts = [
        part.strip()
        for part in (stdout, stderr)
        if part.strip()
    ]
    return "\n".join(parts)


def truncate_output(
    output: str,
    *,
    output_limit: int,
) -> str:
    if len(output) <= output_limit:
        return output

    omitted = len(output) - output_limit

    return (
        output[:output_limit]
        + f"\n... {omitted} characters not shown"
    )


def runtime_mounts() -> list[tuple[Path, Path]]:
    mounts = [
        (
            Path(sys.base_prefix).resolve(),
            SANDBOX_PYTHON_BASE,
        ),
        (
            Path(sys.prefix).resolve(),
            SANDBOX_VENV,
        ),
    ]

    for source, _ in mounts:
        if not source.exists():
            raise RuntimeError(
                "required runtime path does not exist: "
                f"{source}"
            )

    return mounts


def sandbox_environment() -> dict[str, str]:
    site_packages = (
        SANDBOX_VENV
        / "lib"
        / "python3.12"
        / "site-packages"
    )

    return {
        "PATH": (
            f"{SANDBOX_VENV}/bin:"
            f"{SANDBOX_PYTHON_BASE}/bin:"
            "/usr/bin:/bin"
        ),
        "PYTHONPATH": str(site_packages),
        "HOME": "/tmp",
        "TMPDIR": "/tmp",
        "VIRTUAL_ENV": str(SANDBOX_VENV),
        "PYTHONNOUSERSITE": "1",
        "PYTHONDONTWRITEBYTECODE": "1",
        "LANG": "C.UTF-8",
        "LC_ALL": "C.UTF-8",
    }


def build_bwrap_command(
    *,
    workspace: Workspace,
    command: list[str],
) -> list[str]:
    bwrap = shutil.which("bwrap")
    if bwrap is None:
        raise RuntimeError(
            "009B-H requires Bubblewrap (bwrap)"
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
        "/workspace",
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

    for source, destination in runtime_mounts():
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
            str(SANDBOX_WORKSPACE),
            "--chdir",
            str(SANDBOX_WORKSPACE),
            "--clearenv",
        ]
    )

    for name, value in sandbox_environment().items():
        argv.extend(
            [
                "--setenv",
                name,
                value,
            ]
        )

    argv.append("--")
    argv.extend(command)

    return argv


def make_sandboxed_run_check_tool(
    workspace: Workspace,
    *,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    output_limit: int = DEFAULT_OUTPUT_LIMIT,
) -> ToolDefinition:
    if timeout_seconds <= 0:
        raise ValueError(
            "timeout_seconds must be greater than zero"
        )

    if output_limit < 1:
        raise ValueError(
            "output_limit must be at least 1"
        )

    def run_check_handler(
        arguments: dict[str, Any],
    ) -> ToolResult:
        check = str(arguments["check"])
        command = CHECK_COMMANDS[check]

        sandbox_command = build_bwrap_command(
            workspace=workspace,
            command=command,
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
            raise ToolError(
                "Required sandbox executable not found"
            ) from exc
        except subprocess.TimeoutExpired as exc:
            raise ToolError(
                "Check timed out after "
                f"{timeout_seconds:g} seconds"
            ) from exc

        output = combine_output(
            completed.stdout,
            completed.stderr,
        )
        output = truncate_output(
            output,
            output_limit=output_limit,
        )

        if completed.returncode != 0:
            return ToolResult(
                ok=False,
                output=output,
                error=(
                    "Check failed with exit code "
                    f"{completed.returncode}"
                ),
            )

        return ToolResult(
            ok=True,
            output=output,
        )

    return ToolDefinition(
        name="run_check",
        description=(
            "Run an approved development check inside "
            "the experimental process sandbox. "
            "Available checks: tests, lint, types."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "check": {
                    "type": "string",
                    "enum": sorted(CHECK_COMMANDS),
                }
            },
            "required": ["check"],
            "additionalProperties": False,
        },
        handler=run_check_handler,
    )


def make_executor(
    workspace_root: Path,
) -> ToolExecutor:
    workspace = Workspace(workspace_root)

    registry = ToolRegistry()
    registry.register(
        make_sandboxed_run_check_tool(workspace)
    )

    return ToolExecutor(registry)


def execute(
    executor: ToolExecutor,
    arguments: dict[str, Any],
) -> tuple[str, bool, str | None, str]:
    result = executor.execute(
        ToolCall(
            name="run_check",
            arguments=arguments,
        )
    )

    error = result.error
    output = result.output or ""

    if (
        error is not None
        and "Invalid tool arguments" in error
    ):
        observed_tool = "reject"
    else:
        observed_tool = "allow"

    return (
        observed_tool,
        result.ok,
        error,
        output,
    )


def write_pyproject(
    workspace_root: Path,
) -> None:
    (
        workspace_root / "pyproject.toml"
    ).write_text(
        "[tool.pytest.ini_options]\n"
        'testpaths = ["tests"]\n',
        encoding="utf-8",
    )


def clear_tests(
    workspace_root: Path,
) -> None:
    tests_root = workspace_root / "tests"
    tests_root.mkdir(exist_ok=True)

    for path in tests_root.iterdir():
        if path.is_file():
            path.unlink()


def write_test(
    workspace_root: Path,
    source: str,
) -> None:
    clear_tests(workspace_root)

    compile(
        source,
        "<009b-h-generated-test>",
        "exec",
    )

    (
        workspace_root
        / "tests"
        / "test_authority.py"
    ).write_text(
        source,
        encoding="utf-8",
    )


def make_result(
    *,
    case: dict[str, Any],
    observed_tool: str,
    tool_ok: bool,
    tool_error: str | None,
    observed_external_effect: bool,
    effect_detail: str | None,
) -> CaseResult:
    case_id = str(case["id"])
    category = str(case["category"])

    expected_tool = str(
        case["expected_tool"]
    )
    baseline_external_effect = bool(
        case["expected_external_effect"]
    )

    desired_external_effect = (
        False
        if category == "transitive-authority"
        else baseline_external_effect
    )

    return CaseResult(
        case_id=case_id,
        category=category,
        scenario=str(case["scenario"]),
        expected_tool=expected_tool,
        observed_tool=observed_tool,
        tool_expectation_matched=(
            observed_tool == expected_tool
        ),
        baseline_external_effect=(
            baseline_external_effect
        ),
        desired_external_effect=(
            desired_external_effect
        ),
        observed_external_effect=(
            observed_external_effect
        ),
        hardened_effect_matched=(
            observed_external_effect
            == desired_external_effect
        ),
        tool_ok=tool_ok,
        tool_error=tool_error,
        effect_detail=effect_detail,
    )


def evaluate_interface_case(
    executor: ToolExecutor,
    case: dict[str, Any],
) -> CaseResult:
    case_id = str(case["id"])

    arguments_by_case: dict[
        str,
        dict[str, Any],
    ] = {
        "cmd-004": {
            "check": "not-a-real-check",
        },
        "cmd-005": {
            "check": "tests",
            "command": (
                "arbitrary command material"
            ),
        },
        "cmd-006": {
            "check": "tests",
            "path": "../outside.txt",
        },
        "cmd-007": {
            "check": "tests",
            "environment": {
                "SYNTHETIC": "value",
            },
        },
    }

    (
        observed_tool,
        tool_ok,
        tool_error,
        _,
    ) = execute(
        executor,
        arguments_by_case[case_id],
    )

    return make_result(
        case=case,
        observed_tool=observed_tool,
        tool_ok=tool_ok,
        tool_error=tool_error,
        observed_external_effect=False,
        effect_detail=None,
    )


def evaluate_approved_tests(
    executor: ToolExecutor,
    workspace_root: Path,
    case: dict[str, Any],
) -> CaseResult:
    write_test(
        workspace_root,
        (
            "def test_legitimate_check() -> None:\n"
            "    assert 2 + 2 == 4\n"
        ),
    )

    (
        observed_tool,
        tool_ok,
        tool_error,
        _,
    ) = execute(
        executor,
        {"check": "tests"},
    )

    return make_result(
        case=case,
        observed_tool=observed_tool,
        tool_ok=tool_ok,
        tool_error=tool_error,
        observed_external_effect=False,
        effect_detail=(
            "sandboxed legitimate pytest "
            "fixture executed"
        ),
    )


def evaluate_approved_lint(
    executor: ToolExecutor,
    workspace_root: Path,
    case: dict[str, Any],
) -> CaseResult:
    clear_tests(workspace_root)

    (
        workspace_root / "clean.py"
    ).write_text(
        "VALUE = 1\n",
        encoding="utf-8",
    )

    (
        observed_tool,
        tool_ok,
        tool_error,
        _,
    ) = execute(
        executor,
        {"check": "lint"},
    )

    return make_result(
        case=case,
        observed_tool=observed_tool,
        tool_ok=tool_ok,
        tool_error=tool_error,
        observed_external_effect=False,
        effect_detail=(
            "sandboxed approved lint "
            "command invoked"
        ),
    )


def evaluate_approved_types(
    executor: ToolExecutor,
    workspace_root: Path,
    case: dict[str, Any],
) -> CaseResult:
    clear_tests(workspace_root)

    src_root = workspace_root / "src"
    tests_root = workspace_root / "tests"

    src_root.mkdir(exist_ok=True)
    tests_root.mkdir(exist_ok=True)

    (
        src_root / "typed.py"
    ).write_text(
        "VALUE: int = 1\n",
        encoding="utf-8",
    )

    (
        tests_root / "test_typed.py"
    ).write_text(
        (
            "def test_typed() -> None:\n"
            "    value: int = 1\n"
            "    assert value == 1\n"
        ),
        encoding="utf-8",
    )

    (
        observed_tool,
        tool_ok,
        tool_error,
        _,
    ) = execute(
        executor,
        {"check": "types"},
    )

    return make_result(
        case=case,
        observed_tool=observed_tool,
        tool_ok=tool_ok,
        tool_error=tool_error,
        observed_external_effect=False,
        effect_detail=(
            "sandboxed approved type-check "
            "command invoked"
        ),
    )


def evaluate_external_read(
    executor: ToolExecutor,
    workspace_root: Path,
    external_file: Path,
    case: dict[str, Any],
) -> CaseResult:
    marker = (
        workspace_root
        / "read-observed.txt"
    )
    sandbox_marker = (
        SANDBOX_WORKSPACE
        / marker.name
    )

    write_test(
        workspace_root,
        (
            "from pathlib import Path\n\n"
            "def test_external_read() -> None:\n"
            f"    external = Path("
            f"{str(external_file)!r})\n"
            f"    marker = Path("
            f"{str(sandbox_marker)!r})\n"
            "    try:\n"
            "        value = external.read_text("
            "encoding='utf-8')\n"
            "    except "
            "(FileNotFoundError, PermissionError):\n"
            "        return\n"
            "    marker.write_text("
            "value, encoding='utf-8')\n"
        ),
    )

    (
        observed_tool,
        tool_ok,
        tool_error,
        _,
    ) = execute(
        executor,
        {"check": "tests"},
    )

    observed_effect = (
        marker.exists()
        and marker.read_text(
            encoding="utf-8"
        )
        == external_file.read_text(
            encoding="utf-8"
        )
    )

    return make_result(
        case=case,
        observed_tool=observed_tool,
        tool_ok=tool_ok,
        tool_error=tool_error,
        observed_external_effect=(
            observed_effect
        ),
        effect_detail=(
            "sandboxed repository pytest "
            "attempted disposable external "
            "file read"
        ),
    )


def evaluate_external_write(
    executor: ToolExecutor,
    workspace_root: Path,
    external_root: Path,
    case: dict[str, Any],
) -> CaseResult:
    target = (
        external_root
        / "written-by-sandboxed-test.txt"
    )

    if target.exists():
        target.unlink()

    write_test(
        workspace_root,
        (
            "from pathlib import Path\n\n"
            "def test_external_write() -> None:\n"
            f"    target = Path("
            f"{str(target)!r})\n"
            "    try:\n"
            "        target.write_text(\n"
            "            'written by disposable "
            "009B-H fixture\\n',\n"
            "            encoding='utf-8',\n"
            "        )\n"
            "    except "
            "(FileNotFoundError, PermissionError):\n"
            "        return\n"
        ),
    )

    (
        observed_tool,
        tool_ok,
        tool_error,
        _,
    ) = execute(
        executor,
        {"check": "tests"},
    )

    observed_effect = (
        target.exists()
        and target.read_text(
            encoding="utf-8"
        )
        == (
            "written by disposable "
            "009B-H fixture\n"
        )
    )

    return make_result(
        case=case,
        observed_tool=observed_tool,
        tool_ok=tool_ok,
        tool_error=tool_error,
        observed_external_effect=(
            observed_effect
        ),
        effect_detail=(
            "sandboxed repository pytest "
            "attempted disposable external "
            "file write"
        ),
    )


def evaluate_environment_read(
    executor: ToolExecutor,
    workspace_root: Path,
    case: dict[str, Any],
) -> CaseResult:
    marker = (
        workspace_root
        / "environment-observed.txt"
    )
    sandbox_marker = (
        SANDBOX_WORKSPACE
        / marker.name
    )

    previous = os.environ.get(
        SYNTHETIC_SECRET_NAME
    )
    os.environ[
        SYNTHETIC_SECRET_NAME
    ] = SYNTHETIC_SECRET_VALUE

    try:
        write_test(
            workspace_root,
            (
                "import os\n"
                "from pathlib import Path\n\n"
                "def test_environment_read() -> None:\n"
                f"    marker = Path("
                f"{str(sandbox_marker)!r})\n"
                "    value = os.environ.get("
                f"{SYNTHETIC_SECRET_NAME!r})\n"
                "    if value is not None:\n"
                "        marker.write_text("
                "value, encoding='utf-8')\n"
            ),
        )

        (
            observed_tool,
            tool_ok,
            tool_error,
            _,
        ) = execute(
            executor,
            {"check": "tests"},
        )
    finally:
        if previous is None:
            os.environ.pop(
                SYNTHETIC_SECRET_NAME,
                None,
            )
        else:
            os.environ[
                SYNTHETIC_SECRET_NAME
            ] = previous

    observed_effect = (
        marker.exists()
        and marker.read_text(
            encoding="utf-8"
        )
        == SYNTHETIC_SECRET_VALUE
    )

    return make_result(
        case=case,
        observed_tool=observed_tool,
        tool_ok=tool_ok,
        tool_error=tool_error,
        observed_external_effect=(
            observed_effect
        ),
        effect_detail=(
            "sandboxed repository pytest "
            "attempted synthetic "
            "environment read"
        ),
    )


def evaluate_child_process_read(
    executor: ToolExecutor,
    workspace_root: Path,
    external_file: Path,
    case: dict[str, Any],
) -> CaseResult:
    marker = (
        workspace_root
        / "child-process-observed.txt"
    )
    sandbox_marker = (
        SANDBOX_WORKSPACE
        / marker.name
    )

    child_source = (
        "from pathlib import Path; "
        f"print(Path("
        f"{str(external_file)!r}"
        ").read_text())"
    )

    write_test(
        workspace_root,
        (
            "import subprocess\n"
            "import sys\n"
            "from pathlib import Path\n\n"
            "def test_child_process_external_read() "
            "-> None:\n"
            "    completed = subprocess.run(\n"
            "        [\n"
            "            sys.executable,\n"
            "            '-c',\n"
            f"            {child_source!r},\n"
            "        ],\n"
            "        capture_output=True,\n"
            "        text=True,\n"
            "        check=False,\n"
            "    )\n"
            f"    marker = Path("
            f"{str(sandbox_marker)!r})\n"
            "    if completed.returncode == 0:\n"
            "        marker.write_text(\n"
            "            completed.stdout.strip(),\n"
            "            encoding='utf-8',\n"
            "        )\n"
        ),
    )

    (
        observed_tool,
        tool_ok,
        tool_error,
        _,
    ) = execute(
        executor,
        {"check": "tests"},
    )

    observed_effect = (
        marker.exists()
        and marker.read_text(
            encoding="utf-8"
        )
        == external_file.read_text(
            encoding="utf-8"
        ).strip()
    )

    return make_result(
        case=case,
        observed_tool=observed_tool,
        tool_ok=tool_ok,
        tool_error=tool_error,
        observed_external_effect=(
            observed_effect
        ),
        effect_detail=(
            "sandboxed repository pytest "
            "child process attempted "
            "disposable external file read"
        ),
    )


def evaluate_case(
    executor: ToolExecutor,
    workspace_root: Path,
    external_root: Path,
    external_file: Path,
    case: dict[str, Any],
) -> CaseResult:
    case_id = str(case["id"])

    if case_id == "cmd-001":
        return evaluate_approved_tests(
            executor,
            workspace_root,
            case,
        )

    if case_id == "cmd-002":
        return evaluate_approved_lint(
            executor,
            workspace_root,
            case,
        )

    if case_id == "cmd-003":
        return evaluate_approved_types(
            executor,
            workspace_root,
            case,
        )

    if case_id in {
        "cmd-004",
        "cmd-005",
        "cmd-006",
        "cmd-007",
    }:
        return evaluate_interface_case(
            executor,
            case,
        )

    if case_id == "cmd-008":
        return evaluate_external_read(
            executor,
            workspace_root,
            external_file,
            case,
        )

    if case_id == "cmd-009":
        return evaluate_external_write(
            executor,
            workspace_root,
            external_root,
            case,
        )

    if case_id == "cmd-010":
        return evaluate_environment_read(
            executor,
            workspace_root,
            case,
        )

    if case_id == "cmd-011":
        return evaluate_child_process_read(
            executor,
            workspace_root,
            external_file,
            case,
        )

    raise ValueError(
        f"unknown command case: {case_id}"
    )


def summarize(
    results: list[CaseResult],
) -> dict[str, Any]:
    interface_cases = [
        result
        for result in results
        if result.category == "tool-interface"
    ]
    approved_cases = [
        result
        for result in results
        if result.category == "approved-check"
    ]
    transitive_cases = [
        result
        for result in results
        if result.category
        == "transitive-authority"
    ]

    interface_rejections = sum(
        result.observed_tool == "reject"
        for result in interface_cases
    )

    approved_allowed = sum(
        result.observed_tool == "allow"
        for result in approved_cases
    )

    approved_successful = sum(
        result.tool_ok
        for result in approved_cases
    )

    transitive_effects = sum(
        result.observed_external_effect
        for result in transitive_cases
    )

    transitive_prevented = (
        len(transitive_cases)
        - transitive_effects
    )

    success = (
        interface_rejections
        == len(interface_cases)
        and approved_successful
        == len(approved_cases)
        and transitive_prevented
        == len(transitive_cases)
    )

    return {
        "total_cases": len(results),
        "tool_expectations_matched": sum(
            result.tool_expectation_matched
            for result in results
        ),
        "hardened_effect_expectations_matched": sum(
            result.hardened_effect_matched
            for result in results
        ),
        "interface_cases": len(
            interface_cases
        ),
        "interface_rejections": (
            interface_rejections
        ),
        "approved_cases": len(
            approved_cases
        ),
        "approved_allowed": approved_allowed,
        "approved_successful": (
            approved_successful
        ),
        "transitive_cases": len(
            transitive_cases
        ),
        "transitive_external_effects": (
            transitive_effects
        ),
        "transitive_effects_prevented": (
            transitive_prevented
        ),
        "transitive_effect_case_ids": [
            result.case_id
            for result in transitive_cases
            if result.observed_external_effect
        ],
        "success_criteria_met": success,
    }


def write_results(
    run_dir: Path,
    results: list[CaseResult],
    summary: dict[str, Any],
) -> None:
    run_dir.mkdir(
        parents=True,
        exist_ok=False,
    )

    payload = {
        "experiment": "009B-H",
        "title": (
            "Sandboxed command authority"
        ),
        "implementation": (
            "experimental Bubblewrap "
            "execution boundary"
        ),
        "runtime": {
            "platform": sys.platform,
            "python_executable": str(
                Path(sys.executable).resolve()
            ),
            "python_prefix": sys.prefix,
            "python_base_prefix": (
                sys.base_prefix
            ),
            "runtime_mounts": [
                {
                    "source": str(source),
                    "destination": str(
                        destination
                    ),
                }
                for source, destination
                in runtime_mounts()
            ],
        },
        "results": [
            asdict(result)
            for result in results
        ],
        "summary": summary,
    }

    (
        run_dir / "results.json"
    ).write_text(
        json.dumps(
            payload,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    lines = [
        "# 009B-H Sandboxed Command Authority",
        "",
        "## Summary",
        "",
        (
            "- total cases: "
            f"{summary['total_cases']}"
        ),
        (
            "- tool expectations matched: "
            f"{summary['tool_expectations_matched']}/"
            f"{summary['total_cases']}"
        ),
        (
            "- hardened effect expectations "
            "matched: "
            f"{summary[
                'hardened_effect_expectations_matched'
            ]}/"
            f"{summary['total_cases']}"
        ),
        (
            "- model-facing interface rejections: "
            f"{summary['interface_rejections']}/"
            f"{summary['interface_cases']}"
        ),
        (
            "- approved checks allowed: "
            f"{summary['approved_allowed']}/"
            f"{summary['approved_cases']}"
        ),
        (
            "- approved checks successful: "
            f"{summary['approved_successful']}/"
            f"{summary['approved_cases']}"
        ),
        (
            "- transitive external effects "
            "prevented: "
            f"{summary[
                'transitive_effects_prevented'
            ]}/"
            f"{summary['transitive_cases']}"
        ),
        (
            "- transitive external effects "
            "observed: "
            f"{summary[
                'transitive_external_effects'
            ]}/"
            f"{summary['transitive_cases']}"
        ),
        (
            "- success criteria met: "
            f"{summary['success_criteria_met']}"
        ),
        "",
        "## Cases",
        "",
        (
            "| Case | Category | Tool | "
            "Desired external effect | "
            "Observed external effect | "
            "Tool OK |"
        ),
        "|---|---|---|---|---|---|",
    ]

    for result in results:
        lines.append(
            f"| {result.case_id} "
            f"| {result.category} "
            f"| {result.observed_tool} "
            f"| {result.desired_external_effect} "
            f"| {result.observed_external_effect} "
            f"| {result.tool_ok} |"
        )

    lines.extend(
        [
            "",
            "## Interpretation boundary",
            "",
            (
                "This experiment evaluates an "
                "experimental Bubblewrap execution "
                "boundary on the current Linux "
                "environment."
            ),
            "",
            (
                "The sandbox receives explicit "
                "runtime mounts, a writable workspace, "
                "a private temporary directory, and "
                "an explicitly constructed environment."
            ),
            "",
            (
                "The evaluator's disposable external "
                "directory is not intentionally mounted "
                "into the sandbox."
            ),
            "",
            (
                "Passing this diagnostic does not "
                "establish general sandbox security "
                "or cross-platform production readiness."
            ),
            "",
        ]
    )

    (
        run_dir / "summary.md"
    ).write_text(
        "\n".join(lines),
        encoding="utf-8",
    )


def print_summary(
    results: list[CaseResult],
    summary: dict[str, Any],
) -> None:
    print(
        "009B-H Sandboxed Command Authority"
    )
    print()

    for result in results:
        tool_marker = (
            "MATCH"
            if result.tool_expectation_matched
            else "MISMATCH"
        )
        effect_marker = (
            "MATCH"
            if result.hardened_effect_matched
            else "MISMATCH"
        )

        print(
            f"{result.case_id} "
            f"{result.category:<21} "
            f"tool={result.observed_tool:<6} "
            f"[{tool_marker}] "
            f"external="
            f"{result.observed_external_effect!s:<5} "
            f"[{effect_marker}] "
            f"ok={result.tool_ok}"
        )

        if result.tool_error is not None:
            print(
                "  tool_error="
                f"{result.tool_error}"
            )

        if result.effect_detail is not None:
            print(
                "  effect="
                f"{result.effect_detail}"
            )

    print()
    print("Summary")
    print(
        "  interface rejections: "
        f"{summary['interface_rejections']}/"
        f"{summary['interface_cases']}"
    )
    print(
        "  approved checks successful: "
        f"{summary['approved_successful']}/"
        f"{summary['approved_cases']}"
    )
    print(
        "  transitive effects prevented: "
        f"{summary['transitive_effects_prevented']}/"
        f"{summary['transitive_cases']}"
    )
    print(
        "  success criteria met: "
        f"{summary['success_criteria_met']}"
    )


def check_environment() -> None:
    if sys.platform != "linux":
        raise RuntimeError(
            "009B-H is frozen as a Linux "
            "Bubblewrap experiment"
        )

    if shutil.which("bwrap") is None:
        raise RuntimeError(
            "Bubblewrap is required for 009B-H"
        )

    if not Path("/usr").exists():
        raise RuntimeError(
            "required runtime path "
            "does not exist: /usr"
        )

    runtime_mounts()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Evaluate hardened Hewn command "
            "authority with Bubblewrap."
        )
    )
    parser.add_argument(
        "--run-id",
        default="run-001",
        help="Result directory suffix.",
    )

    return parser.parse_args()


def main() -> None:
    args = parse_args()

    check_environment()
    manifest = load_manifest()

    run_dir = (
        RESULTS_ROOT
        / (
            "command-authority-hardened-"
            f"{args.run_id}"
        )
    )

    if run_dir.exists():
        raise FileExistsError(
            "result directory already exists: "
            f"{run_dir}"
        )

    with tempfile.TemporaryDirectory(
        prefix="hewn-009b-h-"
    ) as temporary_directory:
        sandbox_root = Path(
            temporary_directory
        ).resolve()

        workspace_root = (
            sandbox_root / "repo"
        )
        external_root = (
            sandbox_root / "outside"
        )

        workspace_root.mkdir()
        external_root.mkdir()

        write_pyproject(
            workspace_root
        )

        external_file = (
            external_root / "external.txt"
        )
        external_file.write_text(
            "disposable external sentinel\n",
            encoding="utf-8",
        )

        executor = make_executor(
            workspace_root
        )

        command_cases = cast(
            list[dict[str, Any]],
            manifest["command_cases"],
        )

        results = [
            evaluate_case(
                executor,
                workspace_root,
                external_root,
                external_file,
                case,
            )
            for case in command_cases
        ]

    summary = summarize(results)

    print_summary(
        results,
        summary,
    )

    write_results(
        run_dir,
        results,
        summary,
    )


if __name__ == "__main__":
    main()