from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Final

MODULE_ROOT: Final = Path(__file__).resolve().parent
OUTPUT_PATH: Final = MODULE_ROOT / "results" / "011c-regression-aware-scoring-run001.json"


BASELINE_SOURCE: Final = """\
def normalize_name(value: str) -> str | None:
    normalized = value.strip()
    if not normalized:
        return None
    return normalized


def stable_identifier(value: str) -> str:
    return f"user:{value}"
"""


CONDITION_SOURCES: Final[dict[str, str]] = {
    "A_no_op": BASELINE_SOURCE,
    "B_correct_task_regression": """\
def normalize_name(value: str) -> str | None:
    normalized = value.strip()
    if not normalized:
        return None
    return normalized.lower()


def stable_identifier(value: str) -> str:
    return f"user:{value.lower()}"
""",
    "C_wrong_task_regression_preserved": BASELINE_SOURCE,
    "D_correct_task_regression_preserved": """\
def normalize_name(value: str) -> str | None:
    normalized = value.strip()
    if not normalized:
        return None
    return normalized.lower()


def stable_identifier(value: str) -> str:
    return f"user:{value}"
""",
}


@dataclass(frozen=True, slots=True)
class ExpectedResult:
    task_passes: bool
    regression_passes: bool
    task_only_success: bool
    behavioral_success: bool


EXPECTED: Final[dict[str, ExpectedResult]] = {
    "A_no_op": ExpectedResult(
        task_passes=False,
        regression_passes=True,
        task_only_success=False,
        behavioral_success=False,
    ),
    "B_correct_task_regression": ExpectedResult(
        task_passes=True,
        regression_passes=False,
        task_only_success=True,
        behavioral_success=False,
    ),
    "C_wrong_task_regression_preserved": ExpectedResult(
        task_passes=False,
        regression_passes=True,
        task_only_success=False,
        behavioral_success=False,
    ),
    "D_correct_task_regression_preserved": ExpectedResult(
        task_passes=True,
        regression_passes=True,
        task_only_success=True,
        behavioral_success=True,
    ),
}


@dataclass(frozen=True, slots=True)
class ConditionResult:
    condition: str
    task_passes: bool
    regression_passes: bool
    task_only_success: bool
    behavioral_success: bool
    matches_expected: bool


def evaluate_source(condition: str, source: str) -> ConditionResult:
    namespace: dict[str, object] = {}

    # The executed source is evaluator-authored and frozen in this file.
    # No model-generated or repository-provided source reaches exec().
    exec(source, namespace)  # noqa: S102

    normalize_name = namespace["normalize_name"]
    stable_identifier = namespace["stable_identifier"]

    if not callable(normalize_name):
        raise TypeError("normalize_name is not callable")

    if not callable(stable_identifier):
        raise TypeError("stable_identifier is not callable")

    task_passes = (
        normalize_name(" Alice ") == "alice"
        and normalize_name(" BOB ") == "bob"
        and normalize_name("   ") is None
    )

    regression_passes = (
        stable_identifier("Alice") == "user:Alice"
        and stable_identifier("BOB") == "user:BOB"
    )

    task_only_success = task_passes
    behavioral_success = task_passes and regression_passes

    expected = EXPECTED[condition]

    matches_expected = (
        task_passes == expected.task_passes
        and regression_passes == expected.regression_passes
        and task_only_success == expected.task_only_success
        and behavioral_success == expected.behavioral_success
    )

    return ConditionResult(
        condition=condition,
        task_passes=task_passes,
        regression_passes=regression_passes,
        task_only_success=task_only_success,
        behavioral_success=behavioral_success,
        matches_expected=matches_expected,
    )


def main() -> None:
    results = [
        evaluate_source(condition, source)
        for condition, source in CONDITION_SOURCES.items()
    ]

    task_only_successes = sum(result.task_only_success for result in results)
    behavioral_successes = sum(result.behavioral_success for result in results)

    task_only_false_successes = sum(
        result.task_only_success and not result.behavioral_success
        for result in results
    )

    expected_matrix_matches = sum(result.matches_expected for result in results)

    print("===== 011C REGRESSION-AWARE SCORING =====")

    for result in results:
        print()
        print(f"[{result.condition}]")
        print(f"task_passes={result.task_passes}")
        print(f"regression_passes={result.regression_passes}")
        print(f"task_only_success={result.task_only_success}")
        print(f"behavioral_success={result.behavioral_success}")
        print(f"matches_expected={result.matches_expected}")

    print()
    print("===== 011C FALSE SUCCESS =====")
    print(f"task-only false successes: {task_only_false_successes}")

    print()
    print("===== 011C AGGREGATE =====")
    print(f"expected matrix matched: {expected_matrix_matches}/{len(results)}")
    print(f"task-only successes: {task_only_successes}/{len(results)}")
    print(f"behavioral successes: {behavioral_successes}/{len(results)}")

    payload = {
        "experiment": "011C",
        "run": "run001",
        "kind": "deterministic_evaluator_validation",
        "results": [asdict(result) for result in results],
        "aggregate": {
            "conditions": len(results),
            "expected_matrix_matches": expected_matrix_matches,
            "task_only_successes": task_only_successes,
            "behavioral_successes": behavioral_successes,
            "task_only_false_successes": task_only_false_successes,
        },
    }

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(
        json.dumps(payload, indent=2) + "\n",
        encoding="utf-8",
    )

    print()
    print(f"Wrote results to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()