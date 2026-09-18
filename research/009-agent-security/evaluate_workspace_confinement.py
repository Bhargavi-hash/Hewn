from __future__ import annotations

import argparse
import json
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, cast

from hewn.workspace import Workspace, WorkspaceViolationError

RESEARCH_ROOT = Path(__file__).resolve().parent
MANIFEST_PATH = RESEARCH_ROOT / "fixtures" / "manifest.json"
RESULTS_ROOT = RESEARCH_ROOT / "results"


@dataclass(frozen=True)
class CaseResult:
    case_id: str
    category: str
    requested_path: str
    expected: str
    observed: str
    matched_expectation: bool
    resolved_path: str | None
    rejection_type: str | None
    rejection_message: str | None
    escaped_workspace: bool
    external_side_effect: bool


def load_manifest() -> dict[str, Any]:
    raw = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))

    if not isinstance(raw, dict):
        raise TypeError("fixture manifest must be a JSON object")

    data = cast(dict[str, Any], raw)
    
    if data.get("module") != "009-agent-security":
        raise ValueError("unexpected fixture manifest module")

    path_cases = data.get("path_cases")
    if not isinstance(path_cases, list):
        raise TypeError("manifest path_cases must be a list")

    expected_ids = {
        f"path-{index:03d}"
        for index in range(1, 12)
    }
    actual_ids = {
        str(case["id"])
        for case in path_cases
    }

    if actual_ids != expected_ids:
        raise ValueError(
            "009A requires the frozen path-001 through path-011 corpus"
        )

    return data


def materialize_fixture(base: Path) -> tuple[Path, Path]:
    workspace_root = base / "repo"
    external_root = base / "outside"
    sibling_root = base / "repo-evil"

    (workspace_root / "src").mkdir(parents=True)
    (workspace_root / "tests" / "unit").mkdir(parents=True)
    (workspace_root / "links").mkdir(parents=True)

    external_root.mkdir()
    sibling_root.mkdir()

    (workspace_root / "src" / "main.py").write_text(
        "def main() -> str:\n"
        '    return "ok"\n',
        encoding="utf-8",
    )

    (workspace_root / "tests" / "unit" / "test_main.py").write_text(
        "def test_main() -> None:\n"
        "    assert True\n",
        encoding="utf-8",
    )

    (workspace_root / "README.md").write_text(
        "# fixture\n",
        encoding="utf-8",
    )

    internal_target = workspace_root / "src" / "main.py"
    external_target = external_root / "outside.txt"

    external_target.write_text(
        "outside sentinel\n",
        encoding="utf-8",
    )

    (sibling_root / "target.txt").write_text(
        "sibling sentinel\n",
        encoding="utf-8",
    )

    (workspace_root / "links" / "internal.txt").symlink_to(
        internal_target
    )

    (workspace_root / "links" / "external.txt").symlink_to(
        external_target
    )

    (workspace_root / "links" / "external-dir").symlink_to(
        external_root,
        target_is_directory=True,
    )

    return workspace_root, external_root


def external_snapshot(external_root: Path) -> dict[str, bytes]:
    snapshot: dict[str, bytes] = {}

    for path in sorted(external_root.rglob("*")):
        if path.is_file():
            relative = path.relative_to(external_root).as_posix()
            snapshot[relative] = path.read_bytes()

    return snapshot


def evaluate_case(
    workspace: Workspace,
    workspace_root: Path,
    external_root: Path,
    case: dict[str, Any],
) -> CaseResult:
    case_id = str(case["id"])
    category = str(case["category"])
    requested_path = str(case["path"])
    expected = str(case["expected"])

    before = external_snapshot(external_root)

    observed: str
    resolved_path: str | None = None
    rejection_type: str | None = None
    rejection_message: str | None = None
    escaped_workspace = False

    try:
        resolved = workspace.resolve(requested_path)
        observed = "allow"
        resolved_path = str(resolved)
        escaped_workspace = not resolved.is_relative_to(
            workspace_root.resolve()
        )
    except WorkspaceViolationError as exc:
        observed = "reject"
        rejection_type = type(exc).__name__
        rejection_message = str(exc)
    
    after = external_snapshot(external_root)

    return CaseResult(
        case_id=case_id,
        category=category,
        requested_path=requested_path,
        expected=expected,
        observed=observed,
        matched_expectation=observed == expected,
        resolved_path=resolved_path,
        rejection_type=rejection_type,
        rejection_message=rejection_message,
        escaped_workspace=escaped_workspace,
        external_side_effect=before != after,
    )


def summarize(results: list[CaseResult]) -> dict[str, Any]:
    unauthorized = [
        result
        for result in results
        if result.expected == "reject"
    ]
    authorized = [
        result
        for result in results
        if result.expected == "allow"
    ]

    unauthorized_blocked = sum(
        result.observed == "reject"
        for result in unauthorized
    )
    authorized_allowed = sum(
        result.observed == "allow"
        for result in authorized
    )

    false_accepts = [
        result.case_id
        for result in unauthorized
        if result.observed == "allow"
    ]
    false_rejects = [
        result.case_id
        for result in authorized
        if result.observed != "allow"
    ]
    unexpected_errors = [
        result.case_id
        for result in results
        if result.observed == "error"
    ]
    escaped_paths = [
        result.case_id
        for result in results
        if result.escaped_workspace
    ]
    external_side_effects = [
        result.case_id
        for result in results
        if result.external_side_effect
    ]

    return {
        "total_cases": len(results),
        "matched_expectation": sum(
            result.matched_expectation
            for result in results
        ),
        "authorized_cases": len(authorized),
        "authorized_allowed": authorized_allowed,
        "legitimate_operation_acceptance": (
            authorized_allowed / len(authorized)
            if authorized
            else None
        ),
        "unauthorized_cases": len(unauthorized),
        "unauthorized_blocked": unauthorized_blocked,
        "security_recall": (
            unauthorized_blocked / len(unauthorized)
            if unauthorized
            else None
        ),
        "false_accepts": false_accepts,
        "false_rejects": false_rejects,
        "unexpected_errors": unexpected_errors,
        "escaped_paths": escaped_paths,
        "external_side_effects": external_side_effects,
    }


def write_results(
    run_dir: Path,
    results: list[CaseResult],
    summary: dict[str, Any],
) -> None:
    run_dir.mkdir(parents=True, exist_ok=False)

    payload = {
        "experiment": "009A",
        "title": "Workspace confinement baseline",
        "implementation": "current production Workspace.resolve",
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
        "# 009A Workspace Confinement Baseline",
        "",
        "## Summary",
        "",
        f"- total cases: {summary['total_cases']}",
        (
            "- matched expectation: "
            f"{summary['matched_expectation']}/{summary['total_cases']}"
        ),
        (
            "- authorized allowed: "
            f"{summary['authorized_allowed']}/"
            f"{summary['authorized_cases']}"
        ),
        (
            "- unauthorized blocked: "
            f"{summary['unauthorized_blocked']}/"
            f"{summary['unauthorized_cases']}"
        ),
        f"- false accepts: {summary['false_accepts']}",
        f"- false rejects: {summary['false_rejects']}",
        f"- unexpected errors: {summary['unexpected_errors']}",
        f"- escaped paths: {summary['escaped_paths']}",
        (
            "- external side effects: "
            f"{summary['external_side_effects']}"
        ),
        "",
        "## Cases",
        "",
        "| Case | Category | Expected | Observed | Match |",
        "|---|---|---|---|---|",
    ]

    for result in results:
        lines.append(
            f"| {result.case_id} "
            f"| {result.category} "
            f"| {result.expected} "
            f"| {result.observed} "
            f"| {'yes' if result.matched_expectation else 'no'} |"
        )

    lines.extend(
        [
            "",
            "## Interpretation boundary",
            "",
            "This experiment measures path resolution through the current",
            "`Workspace.resolve` implementation only. It does not establish",
            "shell-command confinement, process isolation, or general agent",
            "security.",
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
    print("009A Workspace Confinement Baseline")
    print()

    for result in results:
        marker = "PASS" if result.matched_expectation else "FAIL"
        print(
            f"{result.case_id} "
            f"{result.category:<28} "
            f"expected={result.expected:<6} "
            f"observed={result.observed:<6} "
            f"{marker}"
        )

        if result.rejection_message is not None:
            print(
                f"  {result.rejection_type}: "
                f"{result.rejection_message}"
            )

        if result.resolved_path is not None:
            print(f"  resolved={result.resolved_path}")

    print()
    print("Summary")
    print(
        "  matched expectation: "
        f"{summary['matched_expectation']}/"
        f"{summary['total_cases']}"
    )
    print(
        "  authorized allowed: "
        f"{summary['authorized_allowed']}/"
        f"{summary['authorized_cases']}"
    )
    print(
        "  unauthorized blocked: "
        f"{summary['unauthorized_blocked']}/"
        f"{summary['unauthorized_cases']}"
    )
    print(
        "  legitimate-operation acceptance: "
        f"{summary['legitimate_operation_acceptance']}"
    )
    print(
        "  security recall: "
        f"{summary['security_recall']}"
    )
    print(f"  false accepts: {summary['false_accepts']}")
    print(f"  false rejects: {summary['false_rejects']}")
    print(
        "  unexpected errors: "
        f"{summary['unexpected_errors']}"
    )
    print(f"  escaped paths: {summary['escaped_paths']}")
    print(
        "  external side effects: "
        f"{summary['external_side_effects']}"
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Evaluate Hewn workspace confinement."
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

    run_dir = RESULTS_ROOT / f"workspace-confinement-{args.run_id}"

    if run_dir.exists():
        raise FileExistsError(
            f"result directory already exists: {run_dir}"
        )

    with tempfile.TemporaryDirectory(
        prefix="hewn-009a-"
    ) as temporary_directory:
        base = Path(temporary_directory).resolve()
        workspace_root, external_root = materialize_fixture(base)
        workspace = Workspace(workspace_root)

        results = [
            evaluate_case(
                workspace,
                workspace_root,
                external_root,
                case,
            )
            for case in manifest["path_cases"]
        ]

    summary = summarize(results)

    print_summary(results, summary)
    write_results(run_dir, results, summary)


if __name__ == "__main__":
    main()