from __future__ import annotations

import argparse
import json
import statistics
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

MODULE_ROOT = Path(__file__).resolve().parent
TASKS_PATH = MODULE_ROOT / "012f2-tasks.json"
RESULTS_DIR = MODULE_ROOT / "results"

QUANTIZATIONS = (
    "Q3_K_M",
    "Q4_K_M",
    "Q5_K_M",
    "Q6_K",
    "Q8_0",
)


@dataclass(frozen=True, slots=True)
class Evaluation:
    quantization: str
    task_id: str
    category: str
    repetition: int
    protocol_valid: bool
    predicted_answer: str | None
    expected_answer: str
    behavioral_success: bool
    generated_tokens: int
    finish_reason: str | None
    wall_time_seconds: float


def load_manifest() -> dict[str, Any]:
    payload = json.loads(
        TASKS_PATH.read_text(encoding="utf-8")
    )

    if not isinstance(payload, dict):
        raise TypeError(
            "task manifest must be a JSON object"
        )

    return cast(dict[str, Any], payload)

def parse_exact_answer(
    content: str,
) -> tuple[bool, str | None]:
    try:
        payload = json.loads(content)
    except json.JSONDecodeError:
        return False, None

    if not isinstance(payload, dict):
        return False, None

    if set(payload) != {"answer"}:
        return False, None

    answer = payload["answer"]

    if answer not in {"A", "B", "C", "D"}:
        return False, None

    return True, answer


def result_path(
    quantization: str,
    task_id: str,
    repetition: int,
) -> Path:
    return RESULTS_DIR / (
        "012f2-"
        f"{quantization.lower()}-"
        f"{task_id}-"
        f"run{repetition}.json"
    )


def evaluate_one(
    *,
    quantization: str,
    task: dict[str, Any],
    repetition: int,
) -> Evaluation:
    path = result_path(
        quantization,
        task["task_id"],
        repetition,
    )

    if not path.exists():
        raise FileNotFoundError(
            f"missing observation: {path}"
        )

    payload = json.loads(
        path.read_text(encoding="utf-8")
    )

    measurements = payload["measurements"]
    content = measurements["content"]

    protocol_valid, predicted = (
        parse_exact_answer(content)
    )

    expected = task["oracle"]["answer"]

    behavioral_success = (
        protocol_valid
        and predicted == expected
    )

    return Evaluation(
        quantization=quantization,
        task_id=task["task_id"],
        category=task["category"],
        repetition=repetition,
        protocol_valid=protocol_valid,
        predicted_answer=predicted,
        expected_answer=expected,
        behavioral_success=behavioral_success,
        generated_tokens=measurements[
            "completion_tokens"
        ],
        finish_reason=measurements[
            "finish_reason"
        ],
        wall_time_seconds=measurements[
            "wall_time_seconds"
        ],
    )


def evaluate_repetitions(
    repetitions: tuple[int, ...],
) -> list[Evaluation]:
    manifest = load_manifest()
    tasks = manifest["tasks"]

    evaluations: list[Evaluation] = []

    for repetition in repetitions:
        for quantization in QUANTIZATIONS:
            for task in tasks:
                evaluations.append(
                    evaluate_one(
                        quantization=quantization,
                        task=task,
                        repetition=repetition,
                    )
                )

    return evaluations


def print_quantization_summary(
    evaluations: list[Evaluation],
) -> None:
    print()
    print("QUANTIZATION SUMMARY")
    print()

    print(
        "quant | n | success | protocol | "
        "median_gen | median_wall_s"
    )
    print("-" * 67)

    for quantization in QUANTIZATIONS:
        rows = [
            row
            for row in evaluations
            if row.quantization == quantization
        ]

        successes = sum(
            row.behavioral_success
            for row in rows
        )

        protocol = sum(
            row.protocol_valid
            for row in rows
        )

        generated = statistics.median(
            row.generated_tokens
            for row in rows
        )

        wall = statistics.median(
            row.wall_time_seconds
            for row in rows
        )

        print(
            f"{quantization:7} | "
            f"{len(rows):2d} | "
            f"{successes:7d} | "
            f"{protocol:8d} | "
            f"{generated:10.1f} | "
            f"{wall:13.2f}"
        )


def print_task_matrix(
    evaluations: list[Evaluation],
    repetition: int,
) -> bool:
    print()
    print(
        f"TASK OUTCOME MATRIX — REPETITION "
        f"{repetition}"
    )
    print()

    rows = [
        row
        for row in evaluations
        if row.repetition == repetition
    ]

    task_ids = sorted(
        {row.task_id for row in rows}
    )

    disagreement_exists = False

    print(
        "task          "
        + " ".join(
            f"{quant:>7}"
            for quant in QUANTIZATIONS
        )
    )

    for task_id in task_ids:
        outcomes = []

        for quantization in QUANTIZATIONS:
            matches = [
                row
                for row in rows
                if (
                    row.task_id == task_id
                    and row.quantization
                    == quantization
                )
            ]

            if len(matches) != 1:
                raise ValueError(
                    f"{task_id}/{quantization}: "
                    "expected one observation"
                )

            row = matches[0]

            if not row.protocol_valid:
                display = "PROTO"
            elif row.behavioral_success:
                display = "PASS"
            else:
                display = (
                    f"FAIL:{row.predicted_answer}"
                )

            outcomes.append(
                row.behavioral_success
            )

            print_value = f"{display:>7}"

            if quantization == QUANTIZATIONS[0]:
                line = (
                    f"{task_id:13}{print_value}"
                )
            else:
                line += f" {print_value}"

        print(line)

        if len(set(outcomes)) > 1:
            disagreement_exists = True

    return disagreement_exists


def print_failure_details(
    evaluations: list[Evaluation],
) -> None:
    failures = [
        row
        for row in evaluations
        if not row.behavioral_success
    ]

    print()
    print("FAILURE DETAILS")
    print()

    if not failures:
        print("none")
        return

    for row in failures:
        predicted = (
            row.predicted_answer
            if row.predicted_answer is not None
            else "protocol_failure"
        )

        print(
            f"{row.quantization} "
            f"{row.task_id} "
            f"run={row.repetition} "
            f"predicted={predicted} "
            f"expected={row.expected_answer}"
        )


def print_repeated_run_disagreement(
    evaluations: list[Evaluation],
) -> None:
    repetitions = sorted(
        {row.repetition for row in evaluations}
    )

    if len(repetitions) < 2:
        return

    print()
    print("REPEATED-RUN BEHAVIORAL DISAGREEMENT")
    print()

    disagreement_count = 0

    for quantization in QUANTIZATIONS:
        task_ids = sorted(
            {
                row.task_id
                for row in evaluations
                if row.quantization
                == quantization
            }
        )

        for task_id in task_ids:
            rows = [
                row
                for row in evaluations
                if (
                    row.quantization
                    == quantization
                    and row.task_id == task_id
                )
            ]

            outcomes = {
                row.behavioral_success
                for row in rows
            }

            if len(outcomes) > 1:
                disagreement_count += 1
                print(
                    f"{quantization} {task_id}: "
                    f"{[(r.repetition, r.behavioral_success) for r in rows]}"
                )

    if disagreement_count == 0:
        print("none")


def write_evaluated_results(
    evaluations: list[Evaluation],
    repetitions: tuple[int, ...],
) -> Path:
    output = {
        "experiment": "012F-2",
        "repetitions": list(repetitions),
        "observations": [
            {
                "quantization": row.quantization,
                "task_id": row.task_id,
                "category": row.category,
                "repetition": row.repetition,
                "protocol_valid": (
                    row.protocol_valid
                ),
                "predicted_answer": (
                    row.predicted_answer
                ),
                "expected_answer": (
                    row.expected_answer
                ),
                "behavioral_success": (
                    row.behavioral_success
                ),
                "generated_tokens": (
                    row.generated_tokens
                ),
                "finish_reason": (
                    row.finish_reason
                ),
                "wall_time_seconds": (
                    row.wall_time_seconds
                ),
            }
            for row in evaluations
        ],
    }

    suffix = "-".join(
        str(value)
        for value in repetitions
    )

    path = (
        RESULTS_DIR
        / f"012f2-evaluation-runs-{suffix}.json"
    )

    path.write_text(
        json.dumps(output, indent=2) + "\n",
        encoding="utf-8",
    )

    return path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--repetitions",
        nargs="+",
        type=int,
        required=True,
        choices=(1, 2, 3),
    )

    return parser.parse_args()


def main() -> None:
    args = parse_args()

    repetitions = tuple(
        sorted(set(args.repetitions))
    )

    evaluations = evaluate_repetitions(
        repetitions
    )

    expected_count = (
        len(QUANTIZATIONS)
        * 10
        * len(repetitions)
    )

    if len(evaluations) != expected_count:
        raise ValueError(
            f"expected {expected_count} observations, "
            f"found {len(evaluations)}"
        )

    print(
        f"012F-2 evaluated "
        f"{len(evaluations)} observations."
    )

    print_quantization_summary(evaluations)

    first_run_disagreement = print_task_matrix(
        evaluations,
        repetition=1,
    )

    print_failure_details(evaluations)
    print_repeated_run_disagreement(evaluations)

    output = write_evaluated_results(
        evaluations,
        repetitions,
    )

    print()
    print(f"Wrote {output}")

    if repetitions == (1,):
        print()
        print("FROZEN ESCALATION DECISION")
        print()

        if first_run_disagreement:
            print(
                "ESCALATE: at least one task has "
                "different behavioral outcomes across "
                "quantizations."
            )
            print(
                "Run repetitions 2 and 3 for ALL "
                "tasks and ALL quantizations."
            )
        else:
            print(
                "STOP: all ten tasks have identical "
                "behavioral classifications across "
                "all five quantizations."
            )
            print(
                "Under the frozen rule, no additional "
                "repetitions are required."
            )


if __name__ == "__main__":
    main()