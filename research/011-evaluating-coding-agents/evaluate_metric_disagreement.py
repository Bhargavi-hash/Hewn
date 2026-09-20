from __future__ import annotations

import json
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path

MODULE_ROOT = Path(__file__).resolve().parent
RESULTS_ROOT = MODULE_ROOT / "results"
OUTPUT_PATH = RESULTS_ROOT / "011a-metric-disagreement-run001.json"


BASELINE_SOURCE = """\
def normalize_name(value: str) -> str:
    return value.strip()


def stable_identifier(value: str) -> str:
    return f"user:{value}"
"""


@dataclass(frozen=True, slots=True)
class ExpectedOutcome:
    protocol_valid: bool
    edit_applied: bool
    task_passes: bool
    regression_passes: bool
    behavioral_success: bool


@dataclass(frozen=True, slots=True)
class Condition:
    condition_id: str
    protocol_valid: bool
    replacement_source: str | None
    expected: ExpectedOutcome


@dataclass(frozen=True, slots=True)
class ConditionResult:
    condition_id: str

    protocol_valid: bool
    edit_applied: bool

    task_passes: bool
    regression_passes: bool
    behavioral_success: bool

    protocol_proxy_success: bool
    edit_proxy_success: bool
    task_only_proxy_success: bool

    expected: ExpectedOutcome
    matches_expected: bool


WRONG_VALID_SOURCE = """\
def normalize_name(value: str) -> str:
    return value.upper()


def stable_identifier(value: str) -> str:
    return f"user:{value}"
"""


REGRESSION_SOURCE = """\
def normalize_name(value: str) -> str:
    return value.strip().lower()


def stable_identifier(value: str) -> str:
    return f"account:{value}"
"""


CORRECT_SOURCE = """\
def normalize_name(value: str) -> str:
    return value.strip().lower()


def stable_identifier(value: str) -> str:
    return f"user:{value}"
"""


CONDITIONS = (
    Condition(
        condition_id="protocol_failure",
        protocol_valid=False,
        replacement_source=None,
        expected=ExpectedOutcome(
            protocol_valid=False,
            edit_applied=False,
            task_passes=False,
            regression_passes=True,
            behavioral_success=False,
        ),
    ),
    Condition(
        condition_id="wrong_valid_patch",
        protocol_valid=True,
        replacement_source=WRONG_VALID_SOURCE,
        expected=ExpectedOutcome(
            protocol_valid=True,
            edit_applied=True,
            task_passes=False,
            regression_passes=True,
            behavioral_success=False,
        ),
    ),
    Condition(
        condition_id="regression_patch",
        protocol_valid=True,
        replacement_source=REGRESSION_SOURCE,
        expected=ExpectedOutcome(
            protocol_valid=True,
            edit_applied=True,
            task_passes=True,
            regression_passes=False,
            behavioral_success=False,
        ),
    ),
    Condition(
        condition_id="correct_patch",
        protocol_valid=True,
        replacement_source=CORRECT_SOURCE,
        expected=ExpectedOutcome(
            protocol_valid=True,
            edit_applied=True,
            task_passes=True,
            regression_passes=True,
            behavioral_success=True,
        ),
    ),
)


def write_fixture(root: Path) -> Path:
    source_path = root / "sample.py"
    source_path.write_text(
        BASELINE_SOURCE,
        encoding="utf-8",
    )
    return source_path


def load_namespace(source_path: Path) -> dict[str, object]:
    namespace: dict[str, object] = {}

    source = source_path.read_text(
        encoding="utf-8",
    )

    exec(  # noqa: S102 - executes only frozen evaluator-authored fixture source
        compile(
            source,
            str(source_path),
            "exec",
        ),
        namespace,
    )

    return namespace


def task_oracle(source_path: Path) -> bool:
    namespace = load_namespace(source_path)

    normalize_name = namespace["normalize_name"]

    if not callable(normalize_name):
        return False

    return normalize_name(" Alice ") == "alice"


def regression_oracle(source_path: Path) -> bool:
    namespace = load_namespace(source_path)

    stable_identifier = namespace["stable_identifier"]

    if not callable(stable_identifier):
        return False

    return stable_identifier("Alice") == "user:Alice"


def apply_condition(
    source_path: Path,
    condition: Condition,
) -> bool:
    if not condition.protocol_valid:
        return False

    if condition.replacement_source is None:
        return False

    source_path.write_text(
        condition.replacement_source,
        encoding="utf-8",
    )

    return True


def evaluate_condition(
    condition: Condition,
) -> ConditionResult:
    with tempfile.TemporaryDirectory(
        prefix=f"hewn-011a-{condition.condition_id}-"
    ) as temporary_directory:
        root = Path(temporary_directory)
        source_path = write_fixture(root)

        edit_applied = apply_condition(
            source_path,
            condition,
        )

        task_passes = task_oracle(source_path)
        regression_passes = regression_oracle(
            source_path
        )

        behavioral_success = (
            task_passes
            and regression_passes
        )

        observed = ExpectedOutcome(
            protocol_valid=condition.protocol_valid,
            edit_applied=edit_applied,
            task_passes=task_passes,
            regression_passes=regression_passes,
            behavioral_success=behavioral_success,
        )

        return ConditionResult(
            condition_id=condition.condition_id,
            protocol_valid=condition.protocol_valid,
            edit_applied=edit_applied,
            task_passes=task_passes,
            regression_passes=regression_passes,
            behavioral_success=behavioral_success,
            protocol_proxy_success=(
                condition.protocol_valid
            ),
            edit_proxy_success=edit_applied,
            task_only_proxy_success=task_passes,
            expected=condition.expected,
            matches_expected=(
                observed == condition.expected
            ),
        )


def validate_results(
    results: list[ConditionResult],
) -> None:
    failures = [
        result.condition_id
        for result in results
        if not result.matches_expected
    ]

    if failures:
        raise AssertionError(
            "011A evaluator disagreed with frozen "
            f"expectations: {failures}"
        )


def false_success_count(
    results: list[ConditionResult],
    attribute: str,
) -> int:
    count = 0

    for result in results:
        proxy_success = getattr(
            result,
            attribute,
        )

        if (
            proxy_success
            and not result.behavioral_success
        ):
            count += 1

    return count


def print_summary(
    results: list[ConditionResult],
) -> None:
    print("\n===== 011A SUMMARY =====")

    for result in results:
        print(f"\n[{result.condition_id}]")
        print(
            f"protocol_valid={result.protocol_valid}"
        )
        print(
            f"edit_applied={result.edit_applied}"
        )
        print(
            f"task_passes={result.task_passes}"
        )
        print(
            "regression_passes="
            f"{result.regression_passes}"
        )
        print(
            "behavioral_success="
            f"{result.behavioral_success}"
        )
        print(
            f"matches_expected={result.matches_expected}"
        )

    print("\n===== 011A PROXY DISAGREEMENT =====")

    protocol_false_successes = false_success_count(
        results,
        "protocol_proxy_success",
    )
    edit_false_successes = false_success_count(
        results,
        "edit_proxy_success",
    )
    task_false_successes = false_success_count(
        results,
        "task_only_proxy_success",
    )

    print(
        "protocol-valid false successes: "
        f"{protocol_false_successes}"
    )
    print(
        "edit-applied false successes: "
        f"{edit_false_successes}"
    )
    print(
        "task-only false successes: "
        f"{task_false_successes}"
    )

    print("\n===== 011A AGGREGATE =====")

    print(
        "expected matrix matched: "
        f"{sum(result.matches_expected for result in results)}"
        f"/{len(results)}"
    )

    print(
        "behavioral successes: "
        f"{sum(result.behavioral_success for result in results)}"
        f"/{len(results)}"
    )


def main() -> None:
    results = [
        evaluate_condition(condition)
        for condition in CONDITIONS
    ]

    validate_results(results)

    payload = {
        "experiment": "011A",
        "run": "run001",
        "model_invoked": False,
        "results": [
            asdict(result)
            for result in results
        ],
        "proxy_false_successes": {
            "protocol_valid": false_success_count(
                results,
                "protocol_proxy_success",
            ),
            "edit_applied": false_success_count(
                results,
                "edit_proxy_success",
            ),
            "task_only": false_success_count(
                results,
                "task_only_proxy_success",
            ),
        },
    }

    RESULTS_ROOT.mkdir(
        parents=True,
        exist_ok=True,
    )

    OUTPUT_PATH.write_text(
        json.dumps(
            payload,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    print_summary(results)

    print(
        "\nWrote results to "
        f"{OUTPUT_PATH}"
    )


if __name__ == "__main__":
    main()