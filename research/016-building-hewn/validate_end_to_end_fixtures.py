from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class CommandResult:
    returncode: int
    stdout: str
    stderr: str


def load_cases(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text().splitlines()
        if line.strip()
    ]


def run_pytest(
    repository: Path,
    test_path: Path,
) -> CommandResult:
    env = dict(os.environ)
    source_path = str(repository / "src")

    existing = env.get("PYTHONPATH")
    env["PYTHONPATH"] = (
        source_path
        if not existing
        else f"{source_path}{os.pathsep}{existing}"
    )

    result = subprocess.run(
        [
            "python",
            "-m",
            "pytest",
            "-q",
            str(test_path),
        ],
        cwd=repository,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    return CommandResult(
        returncode=result.returncode,
        stdout=result.stdout,
        stderr=result.stderr,
    )


def copy_for_validation(source: Path) -> Path:
    temporary = Path(
        tempfile.mkdtemp(prefix="hewn-16c-")
    )
    destination = temporary / "repository"
    shutil.copytree(source, destination)
    return destination


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--cases",
        type=Path,
        required=True,
    )
    parser.add_argument(
        "--fixtures",
        type=Path,
        required=True,
    )
    parser.add_argument(
        "--out",
        type=Path,
        required=True,
    )
    args = parser.parse_args()

    cases = load_cases(args.cases)
    records: list[dict[str, Any]] = []

    for case in cases:
        fixture = args.fixtures / case["fixture"]

        buggy_source = fixture / "repository"
        reference_source = fixture / "reference"
        hidden_test = (
            fixture
            / "evaluator"
            / "test_task.py"
        )

        buggy = copy_for_validation(buggy_source)
        reference = copy_for_validation(reference_source)

        try:
            buggy_behavior = run_pytest(
                buggy,
                hidden_test.resolve(),
            )
            buggy_regression = run_pytest(
                buggy,
                buggy / "tests",
            )

            reference_behavior = run_pytest(
                reference,
                hidden_test.resolve(),
            )
            reference_regression = run_pytest(
                reference,
                reference / "tests",
            )
        finally:
            shutil.rmtree(buggy.parent)
            shutil.rmtree(reference.parent)

        family = case["family"]

        expected_buggy_regression_pass = (
            family != "test_driven_fix"
        )

        correct = (
            buggy_behavior.returncode != 0
            and (
                (buggy_regression.returncode == 0)
                == expected_buggy_regression_pass
            )
            and reference_behavior.returncode == 0
            and reference_regression.returncode == 0
        )

        records.append(
            {
                "task_id": case["task_id"],
                "family": family,
                "buggy_behavior_fails": (
                    buggy_behavior.returncode != 0
                ),
                "buggy_regression_passes": (
                    buggy_regression.returncode == 0
                ),
                "expected_buggy_regression_passes": (
                    expected_buggy_regression_pass
                ),
                "reference_behavior_passes": (
                    reference_behavior.returncode == 0
                ),
                "reference_regression_passes": (
                    reference_regression.returncode == 0
                ),
                "correct": correct,
            }
        )

    valid = sum(
        bool(record["correct"])
        for record in records
    )

    result = {
        "tasks": len(records),
        "valid": valid,
        "all_valid": valid == len(records),
        "records": records,
    }

    args.out.parent.mkdir(
        parents=True,
        exist_ok=True,
    )
    args.out.write_text(
        json.dumps(result, indent=2) + "\n"
    )

    print(f"tasks={len(records)}")
    print(f"valid={valid}")
    print(f"all_valid={result['all_valid']}")

    for record in records:
        status = "PASS" if record["correct"] else "FAIL"
        print(
            f"{status} "
            f"{record['task_id']} "
            f"({record['family']})"
        )

    if not result["all_valid"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()