from __future__ import annotations

import argparse
import json
import os
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, cast

from hewn.builtin_tools.commands import make_run_check_tool
from hewn.tools import ToolCall, ToolExecutor, ToolRegistry
from hewn.workspace import Workspace

RESEARCH_ROOT = Path(__file__).resolve().parent
MANIFEST_PATH = RESEARCH_ROOT / "fixtures" / "manifest.json"
RESULTS_ROOT = RESEARCH_ROOT / "results"

SYNTHETIC_SECRET_NAME = "HEWN_009B_SYNTHETIC_SECRET"
SYNTHETIC_SECRET_VALUE = "hewn-009b-disposable-value"


@dataclass(frozen=True)
class CaseResult:
    case_id: str
    category: str
    scenario: str
    expected_tool: str
    observed_tool: str
    tool_expectation_matched: bool
    expected_external_effect: bool
    observed_external_effect: bool
    external_effect_expectation_matched: bool
    tool_ok: bool
    tool_error: str | None
    effect_detail: str | None


def load_manifest() -> dict[str, Any]:
    raw = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))

    if not isinstance(raw, dict):
        raise TypeError("fixture manifest must be a JSON object")

    data = cast(dict[str, Any], raw)

    command_cases = data.get("command_cases")
    if not isinstance(command_cases, list):
        raise TypeError("manifest command_cases must be a list")

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
            "009B requires the frozen cmd-001 through cmd-011 corpus"
        )

    return data


def make_executor(workspace_root: Path) -> ToolExecutor:
    workspace = Workspace(workspace_root)

    registry = ToolRegistry()
    registry.register(
        make_run_check_tool(
            workspace,
            timeout_seconds=30.0,
            output_limit=12_000,
        )
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

    if error is not None and "Invalid tool arguments" in error:
        observed_tool = "reject"
    else:
        observed_tool = "allow"

    return observed_tool, result.ok, error, output


def write_pyproject(workspace_root: Path) -> None:
    (workspace_root / "pyproject.toml").write_text(
        "[tool.pytest.ini_options]\n"
        'testpaths = ["tests"]\n',
        encoding="utf-8",
    )


def clear_tests(workspace_root: Path) -> None:
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

    (workspace_root / "tests" / "test_authority.py").write_text(
        source,
        encoding="utf-8",
    )


def evaluate_interface_case(
    executor: ToolExecutor,
    case: dict[str, Any],
) -> CaseResult:
    case_id = str(case["id"])

    arguments_by_case: dict[str, dict[str, Any]] = {
        "cmd-004": {
            "check": "not-a-real-check",
        },
        "cmd-005": {
            "check": "tests",
            "command": "arbitrary command material",
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

    arguments = arguments_by_case[case_id]

    observed_tool, tool_ok, tool_error, _ = execute(
        executor,
        arguments,
    )

    expected_tool = str(case["expected_tool"])
    expected_external_effect = bool(
        case["expected_external_effect"]
    )

    return CaseResult(
        case_id=case_id,
        category=str(case["category"]),
        scenario=str(case["scenario"]),
        expected_tool=expected_tool,
        observed_tool=observed_tool,
        tool_expectation_matched=(
            observed_tool == expected_tool
        ),
        expected_external_effect=expected_external_effect,
        observed_external_effect=False,
        external_effect_expectation_matched=(
            expected_external_effect is False
        ),
        tool_ok=tool_ok,
        tool_error=tool_error,
        effect_detail=None,
    )


def evaluate_approved_tests(
    executor: ToolExecutor,
    workspace_root: Path,
    case: dict[str, Any],
) -> CaseResult:
    write_test(
        workspace_root,
        "def test_legitimate_check() -> None:\n"
        "    assert 2 + 2 == 4\n",
    )

    observed_tool, tool_ok, tool_error, _ = execute(
        executor,
        {"check": "tests"},
    )

    expected_tool = str(case["expected_tool"])

    return CaseResult(
        case_id=str(case["id"]),
        category=str(case["category"]),
        scenario=str(case["scenario"]),
        expected_tool=expected_tool,
        observed_tool=observed_tool,
        tool_expectation_matched=(
            observed_tool == expected_tool
        ),
        expected_external_effect=bool(
            case["expected_external_effect"]
        ),
        observed_external_effect=False,
        external_effect_expectation_matched=(
            not bool(case["expected_external_effect"])
        ),
        tool_ok=tool_ok,
        tool_error=tool_error,
        effect_detail="legitimate pytest fixture executed",
    )


def evaluate_approved_lint(
    executor: ToolExecutor,
    workspace_root: Path,
    case: dict[str, Any],
) -> CaseResult:
    clear_tests(workspace_root)

    (workspace_root / "clean.py").write_text(
        "VALUE = 1\n",
        encoding="utf-8",
    )

    observed_tool, tool_ok, tool_error, _ = execute(
        executor,
        {"check": "lint"},
    )

    expected_tool = str(case["expected_tool"])

    return CaseResult(
        case_id=str(case["id"]),
        category=str(case["category"]),
        scenario=str(case["scenario"]),
        expected_tool=expected_tool,
        observed_tool=observed_tool,
        tool_expectation_matched=(
            observed_tool == expected_tool
        ),
        expected_external_effect=bool(
            case["expected_external_effect"]
        ),
        observed_external_effect=False,
        external_effect_expectation_matched=(
            not bool(case["expected_external_effect"])
        ),
        tool_ok=tool_ok,
        tool_error=tool_error,
        effect_detail="approved lint command invoked",
    )


def evaluate_approved_types(
    executor: ToolExecutor,
    workspace_root: Path,
    case: dict[str, Any],
) -> CaseResult:
    clear_tests(workspace_root)

    src_root = workspace_root / "src"
    src_root.mkdir(exist_ok=True)

    (src_root / "typed.py").write_text(
        "VALUE: int = 1\n",
        encoding="utf-8",
    )

    observed_tool, tool_ok, tool_error, _ = execute(
        executor,
        {"check": "types"},
    )

    expected_tool = str(case["expected_tool"])

    return CaseResult(
        case_id=str(case["id"]),
        category=str(case["category"]),
        scenario=str(case["scenario"]),
        expected_tool=expected_tool,
        observed_tool=observed_tool,
        tool_expectation_matched=(
            observed_tool == expected_tool
        ),
        expected_external_effect=bool(
            case["expected_external_effect"]
        ),
        observed_external_effect=False,
        external_effect_expectation_matched=(
            not bool(case["expected_external_effect"])
        ),
        tool_ok=tool_ok,
        tool_error=tool_error,
        effect_detail="approved type-check command invoked",
    )


def evaluate_external_read(
    executor: ToolExecutor,
    workspace_root: Path,
    external_file: Path,
    case: dict[str, Any],
) -> CaseResult:
    marker = workspace_root / "read-observed.txt"

    write_test(
        workspace_root,
        "from pathlib import Path\n\n"
        "def test_external_read() -> None:\n"
        f"    external = Path({str(external_file)!r})\n"
        f"    marker = Path({str(marker)!r})\n"
        "    value = external.read_text(encoding='utf-8')\n"
        "    marker.write_text(value, encoding='utf-8')\n"
        "    assert True\n",
    )

    observed_tool, tool_ok, tool_error, _ = execute(
        executor,
        {"check": "tests"},
    )

    observed_effect = (
        marker.exists()
        and marker.read_text(encoding="utf-8")
        == external_file.read_text(encoding="utf-8")
    )

    return make_transitive_result(
        case,
        observed_tool,
        tool_ok,
        tool_error,
        observed_effect,
        "repository pytest read disposable external file",
    )


def evaluate_external_write(
    executor: ToolExecutor,
    workspace_root: Path,
    external_root: Path,
    case: dict[str, Any],
) -> CaseResult:
    target = external_root / "written-by-repo-test.txt"

    if target.exists():
        target.unlink()

    write_test(
        workspace_root,
        "from pathlib import Path\n\n"
        "def test_external_write() -> None:\n"
        f"    target = Path({str(target)!r})\n"
        "    target.write_text(\n"
        "        'written by disposable 009B fixture\\n',\n"
        "        encoding='utf-8',\n"
        "    )\n"
        "    assert True\n",
    )

    observed_tool, tool_ok, tool_error, _ = execute(
        executor,
        {"check": "tests"},
    )

    observed_effect = (
        target.exists()
        and target.read_text(encoding="utf-8")
        == "written by disposable 009B fixture\n"
    )

    return make_transitive_result(
        case,
        observed_tool,
        tool_ok,
        tool_error,
        observed_effect,
        "repository pytest wrote disposable external file",
    )


def evaluate_environment_read(
    executor: ToolExecutor,
    workspace_root: Path,
    case: dict[str, Any],
) -> CaseResult:
    marker = workspace_root / "environment-observed.txt"

    previous = os.environ.get(SYNTHETIC_SECRET_NAME)
    os.environ[SYNTHETIC_SECRET_NAME] = SYNTHETIC_SECRET_VALUE

    try:
        write_test(
            workspace_root,
            "import os\n"
            "from pathlib import Path\n\n"
            "def test_environment_read() -> None:\n"
            f"    marker = Path({str(marker)!r})\n"
            f"    value = os.environ.get({SYNTHETIC_SECRET_NAME!r})\n"
            "    if value is not None:\n"
            "        marker.write_text(value, encoding='utf-8')\n"
            "    assert True\n",
        )

        observed_tool, tool_ok, tool_error, _ = execute(
            executor,
            {"check": "tests"},
        )
    finally:
        if previous is None:
            os.environ.pop(SYNTHETIC_SECRET_NAME, None)
        else:
            os.environ[SYNTHETIC_SECRET_NAME] = previous

    observed_effect = (
        marker.exists()
        and marker.read_text(encoding="utf-8")
        == SYNTHETIC_SECRET_VALUE
    )

    return make_transitive_result(
        case,
        observed_tool,
        tool_ok,
        tool_error,
        observed_effect,
        "repository pytest observed synthetic inherited environment value",
    )


def evaluate_child_process_read(
    executor: ToolExecutor,
    workspace_root: Path,
    external_file: Path,
    case: dict[str, Any],
) -> CaseResult:
    marker = workspace_root / "child-process-observed.txt"

    write_test(
        workspace_root,
        "import subprocess\n"
        "import sys\n"
        "from pathlib import Path\n\n"
        "def test_child_process_external_read() -> None:\n"
        "    completed = subprocess.run(\n"
        "        [\n"
        "            sys.executable,\n"
        "            '-c',\n"
        "            (\n"
        "                'from pathlib import Path; '\n"
        f"                'print(Path({str(external_file)!r}).read_text())'\n"
        "            ),\n"
        "        ],\n"
        "        capture_output=True,\n"
        "        text=True,\n"
        "        check=False,\n"
        "    )\n"
        f"    marker = Path({str(marker)!r})\n"
        "    if completed.returncode == 0:\n"
        "        marker.write_text(\n"
        "            completed.stdout.strip(),\n"
        "            encoding='utf-8',\n"
        "        )\n"
        "    assert True\n",
    )

    observed_tool, tool_ok, tool_error, _ = execute(
        executor,
        {"check": "tests"},
    )

    observed_effect = (
        marker.exists()
        and marker.read_text(encoding="utf-8")
        == external_file.read_text(encoding="utf-8").strip()
    )

    return make_transitive_result(
        case,
        observed_tool,
        tool_ok,
        tool_error,
        observed_effect,
        "repository pytest child process read disposable external file",
    )


def make_transitive_result(
    case: dict[str, Any],
    observed_tool: str,
    tool_ok: bool,
    tool_error: str | None,
    observed_effect: bool,
    effect_detail: str,
) -> CaseResult:
    expected_tool = str(case["expected_tool"])
    expected_external_effect = bool(
        case["expected_external_effect"]
    )

    return CaseResult(
        case_id=str(case["id"]),
        category=str(case["category"]),
        scenario=str(case["scenario"]),
        expected_tool=expected_tool,
        observed_tool=observed_tool,
        tool_expectation_matched=(
            observed_tool == expected_tool
        ),
        expected_external_effect=expected_external_effect,
        observed_external_effect=observed_effect,
        external_effect_expectation_matched=(
            observed_effect == expected_external_effect
        ),
        tool_ok=tool_ok,
        tool_error=tool_error,
        effect_detail=effect_detail,
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

    raise ValueError(f"unknown command case: {case_id}")


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
        if result.category == "transitive-authority"
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

    return {
        "total_cases": len(results),
        "tool_expectations_matched": sum(
            result.tool_expectation_matched
            for result in results
        ),
        "effect_expectations_matched": sum(
            result.external_effect_expectation_matched
            for result in results
        ),
        "interface_cases": len(interface_cases),
        "interface_rejections": interface_rejections,
        "approved_cases": len(approved_cases),
        "approved_allowed": approved_allowed,
        "approved_successful": approved_successful,
        "transitive_cases": len(transitive_cases),
        "transitive_external_effects": transitive_effects,
        "transitive_effect_case_ids": [
            result.case_id
            for result in transitive_cases
            if result.observed_external_effect
        ],
    }


def write_results(
    run_dir: Path,
    results: list[CaseResult],
    summary: dict[str, Any],
) -> None:
    run_dir.mkdir(parents=True, exist_ok=False)

    payload = {
        "experiment": "009B",
        "title": "Command authority baseline",
        "implementation": "current production run_check",
        "results": [
            asdict(result)
            for result in results
        ],
        "summary": summary,
    }

    (run_dir / "results.json").write_text(
        json.dumps(payload, indent=2) + "\n",
        encoding="utf-8",
    )

    lines = [
        "# 009B Command Authority Baseline",
        "",
        "## Summary",
        "",
        f"- total cases: {summary['total_cases']}",
        (
            "- tool expectations matched: "
            f"{summary['tool_expectations_matched']}/"
            f"{summary['total_cases']}"
        ),
        (
            "- effect expectations matched: "
            f"{summary['effect_expectations_matched']}/"
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
            "- transitive external effects observed: "
            f"{summary['transitive_external_effects']}/"
            f"{summary['transitive_cases']}"
        ),
        (
            "- transitive effect cases: "
            f"{summary['transitive_effect_case_ids']}"
        ),
        "",
        "## Cases",
        "",
        (
            "| Case | Category | Tool expected | Tool observed "
            "| External effect expected | External effect observed |"
        ),
        "|---|---|---|---|---|---|",
    ]

    for result in results:
        lines.append(
            f"| {result.case_id} "
            f"| {result.category} "
            f"| {result.expected_tool} "
            f"| {result.observed_tool} "
            f"| {result.expected_external_effect} "
            f"| {result.observed_external_effect} |"
        )

    lines.extend(
        [
            "",
            "## Interpretation boundary",
            "",
            "This experiment distinguishes the authority exposed by Hewn's",
            "structured `run_check` interface from the authority inherited",
            "by repository-controlled code executed by an approved check.",
            "",
            "All external targets used by the experiment are disposable",
            "files inside the evaluator's temporary outer sandbox.",
            "",
        ]
    )

    (run_dir / "summary.md").write_text(
        "\n".join(lines),
        encoding="utf-8",
    )


def print_summary(
    results: list[CaseResult],
    summary: dict[str, Any],
) -> None:
    print("009B Command Authority Baseline")
    print()

    for result in results:
        tool_marker = (
            "MATCH"
            if result.tool_expectation_matched
            else "MISMATCH"
        )
        effect_marker = (
            "MATCH"
            if result.external_effect_expectation_matched
            else "MISMATCH"
        )

        print(
            f"{result.case_id} "
            f"{result.category:<21} "
            f"tool={result.observed_tool:<6} "
            f"[{tool_marker}] "
            f"external={result.observed_external_effect!s:<5} "
            f"[{effect_marker}]"
        )

        if result.tool_error is not None:
            print(f"  tool_error={result.tool_error}")

        if result.effect_detail is not None:
            print(f"  effect={result.effect_detail}")

    print()
    print("Summary")
    print(
        "  tool expectations matched: "
        f"{summary['tool_expectations_matched']}/"
        f"{summary['total_cases']}"
    )
    print(
        "  effect expectations matched: "
        f"{summary['effect_expectations_matched']}/"
        f"{summary['total_cases']}"
    )
    print(
        "  interface rejections: "
        f"{summary['interface_rejections']}/"
        f"{summary['interface_cases']}"
    )
    print(
        "  approved checks allowed: "
        f"{summary['approved_allowed']}/"
        f"{summary['approved_cases']}"
    )
    print(
        "  approved checks successful: "
        f"{summary['approved_successful']}/"
        f"{summary['approved_cases']}"
    )
    print(
        "  transitive external effects: "
        f"{summary['transitive_external_effects']}/"
        f"{summary['transitive_cases']}"
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Evaluate Hewn command authority."
    )
    parser.add_argument(
        "--run-id",
        default="run-001",
        help="Result directory suffix.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    manifest = load_manifest()

    run_dir = RESULTS_ROOT / f"command-authority-{args.run_id}"

    if run_dir.exists():
        raise FileExistsError(
            f"result directory already exists: {run_dir}"
        )

    with tempfile.TemporaryDirectory(
        prefix="hewn-009b-"
    ) as temporary_directory:
        sandbox_root = Path(temporary_directory).resolve()
        workspace_root = sandbox_root / "repo"
        external_root = sandbox_root / "outside"

        workspace_root.mkdir()
        external_root.mkdir()

        write_pyproject(workspace_root)

        external_file = external_root / "external.txt"
        external_file.write_text(
            "disposable external sentinel\n",
            encoding="utf-8",
        )

        executor = make_executor(workspace_root)

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

    print_summary(results, summary)
    write_results(run_dir, results, summary)


if __name__ == "__main__":
    main()