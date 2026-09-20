from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Final

MODULE_ROOT: Final = Path(__file__).resolve().parent
OUTPUT_PATH: Final = (
    MODULE_ROOT
    / "results"
    / "011d-efficiency-accounting-run001.json"
)


@dataclass(frozen=True, slots=True)
class RunRecord:
    condition: str
    behavioral_success: bool
    model_calls: int
    tool_calls: int
    execution_calls: int
    context_chars: int
    wall_time_seconds: float


@dataclass(frozen=True, slots=True)
class ResourceTotals:
    model_calls: int
    tool_calls: int
    execution_calls: int
    context_chars: int
    wall_time_seconds: float


@dataclass(frozen=True, slots=True)
class ResourceMeans:
    model_calls: float
    tool_calls: float
    execution_calls: float
    context_chars: float
    wall_time_seconds: float


@dataclass(frozen=True, slots=True)
class Aggregate:
    count: int
    totals: ResourceTotals
    means: ResourceMeans


RUNS: Final[tuple[RunRecord, ...]] = (
    RunRecord(
        condition="A_correct_lower_cost",
        behavioral_success=True,
        model_calls=2,
        tool_calls=2,
        execution_calls=1,
        context_chars=1000,
        wall_time_seconds=4.0,
    ),
    RunRecord(
        condition="B_correct_higher_cost",
        behavioral_success=True,
        model_calls=5,
        tool_calls=6,
        execution_calls=3,
        context_chars=3000,
        wall_time_seconds=12.0,
    ),
    RunRecord(
        condition="C_incorrect_lower_cost",
        behavioral_success=False,
        model_calls=1,
        tool_calls=0,
        execution_calls=0,
        context_chars=500,
        wall_time_seconds=2.0,
    ),
    RunRecord(
        condition="D_incorrect_higher_cost",
        behavioral_success=False,
        model_calls=4,
        tool_calls=5,
        execution_calls=2,
        context_chars=2500,
        wall_time_seconds=10.0,
    ),
)


EXPECTED_CLASSIFICATIONS: Final[dict[str, bool]] = {
    "A_correct_lower_cost": True,
    "B_correct_higher_cost": True,
    "C_incorrect_lower_cost": False,
    "D_incorrect_higher_cost": False,
}


EXPECTED_ALL_TOTALS: Final = ResourceTotals(
    model_calls=12,
    tool_calls=13,
    execution_calls=6,
    context_chars=7000,
    wall_time_seconds=28.0,
)

EXPECTED_ALL_MEANS: Final = ResourceMeans(
    model_calls=3.0,
    tool_calls=3.25,
    execution_calls=1.5,
    context_chars=1750.0,
    wall_time_seconds=7.0,
)

EXPECTED_SUCCESS_TOTALS: Final = ResourceTotals(
    model_calls=7,
    tool_calls=8,
    execution_calls=4,
    context_chars=4000,
    wall_time_seconds=16.0,
)

EXPECTED_FAILURE_TOTALS: Final = ResourceTotals(
    model_calls=5,
    tool_calls=5,
    execution_calls=2,
    context_chars=3000,
    wall_time_seconds=12.0,
)


def aggregate(records: tuple[RunRecord, ...]) -> Aggregate:
    if not records:
        raise ValueError("Cannot aggregate an empty run set")

    count = len(records)

    totals = ResourceTotals(
        model_calls=sum(record.model_calls for record in records),
        tool_calls=sum(record.tool_calls for record in records),
        execution_calls=sum(record.execution_calls for record in records),
        context_chars=sum(record.context_chars for record in records),
        wall_time_seconds=sum(
            record.wall_time_seconds for record in records
        ),
    )

    means = ResourceMeans(
        model_calls=totals.model_calls / count,
        tool_calls=totals.tool_calls / count,
        execution_calls=totals.execution_calls / count,
        context_chars=totals.context_chars / count,
        wall_time_seconds=totals.wall_time_seconds / count,
    )

    return Aggregate(
        count=count,
        totals=totals,
        means=means,
    )


def resource_dominates(
    left: RunRecord,
    right: RunRecord,
) -> bool | None:
    if left.behavioral_success != right.behavioral_success:
        return None

    left_resources = (
        left.model_calls,
        left.tool_calls,
        left.execution_calls,
        left.context_chars,
        left.wall_time_seconds,
    )

    right_resources = (
        right.model_calls,
        right.tool_calls,
        right.execution_calls,
        right.context_chars,
        right.wall_time_seconds,
    )

    no_more_of_every_resource = all(
        left_value <= right_value
        for left_value, right_value in zip(
            left_resources,
            right_resources,
            strict=True,
        )
    )

    strictly_less_of_at_least_one = any(
        left_value < right_value
        for left_value, right_value in zip(
            left_resources,
            right_resources,
            strict=True,
        )
    )

    return no_more_of_every_resource and strictly_less_of_at_least_one


def find_run(condition: str) -> RunRecord:
    for record in RUNS:
        if record.condition == condition:
            return record

    raise KeyError(condition)


def main() -> None:
    classification_matches = sum(
        record.behavioral_success
        == EXPECTED_CLASSIFICATIONS[record.condition]
        for record in RUNS
    )

    successful_runs = tuple(
        record for record in RUNS if record.behavioral_success
    )
    unsuccessful_runs = tuple(
        record for record in RUNS if not record.behavioral_success
    )

    all_aggregate = aggregate(RUNS)
    successful_aggregate = aggregate(successful_runs)
    unsuccessful_aggregate = aggregate(unsuccessful_runs)

    aggregate_accounting_matched = (
        all_aggregate.totals == EXPECTED_ALL_TOTALS
        and all_aggregate.means == EXPECTED_ALL_MEANS
        and successful_aggregate.totals == EXPECTED_SUCCESS_TOTALS
        and unsuccessful_aggregate.totals == EXPECTED_FAILURE_TOTALS
    )

    condition_a = find_run("A_correct_lower_cost")
    condition_b = find_run("B_correct_higher_cost")
    condition_c = find_run("C_incorrect_lower_cost")
    condition_d = find_run("D_incorrect_higher_cost")

    a_dominates_b = resource_dominates(
        condition_a,
        condition_b,
    )
    c_dominates_d = resource_dominates(
        condition_c,
        condition_d,
    )
    c_dominates_a = resource_dominates(
        condition_c,
        condition_a,
    )

    print("===== 011D EFFICIENCY ACCOUNTING =====")

    for record in RUNS:
        outcome = (
            "successful"
            if record.behavioral_success
            else "unsuccessful"
        )

        print()
        print(f"[{record.condition}]")
        print(f"behavioral_class={outcome}")
        print(f"model_calls={record.model_calls}")
        print(f"tool_calls={record.tool_calls}")
        print(f"execution_calls={record.execution_calls}")
        print(f"context_chars={record.context_chars}")
        print(f"wall_time_seconds={record.wall_time_seconds:.1f}")

    print()
    print("===== 011D DOMINANCE =====")
    print(
        "A dominates B within successful class: "
        f"{a_dominates_b}"
    )
    print(
        "C dominates D within unsuccessful class: "
        f"{c_dominates_d}"
    )
    print(
        "C dominates A across correctness classes: "
        f"{c_dominates_a}"
    )

    print()
    print("===== 011D ALL-RUN ACCOUNTING =====")
    print(f"totals={all_aggregate.totals}")
    print(f"means={all_aggregate.means}")

    print()
    print("===== 011D SUCCESSFUL-RUN ACCOUNTING =====")
    print(f"totals={successful_aggregate.totals}")
    print(f"means={successful_aggregate.means}")

    print()
    print("===== 011D UNSUCCESSFUL-RUN ACCOUNTING =====")
    print(f"totals={unsuccessful_aggregate.totals}")
    print(f"means={unsuccessful_aggregate.means}")

    print()
    print("===== 011D AGGREGATE =====")
    print(
        "behavioral classifications matched: "
        f"{classification_matches}/{len(RUNS)}"
    )
    print(
        f"successful runs: {len(successful_runs)}/{len(RUNS)}"
    )
    print(
        "A dominates B within successful class: "
        f"{a_dominates_b}"
    )
    print(
        "C dominates D within unsuccessful class: "
        f"{c_dominates_d}"
    )
    print(
        "C dominates A across correctness classes: "
        f"{'not evaluated' if c_dominates_a is None else c_dominates_a}"
    )
    print(
        "aggregate accounting matched: "
        f"{aggregate_accounting_matched}"
    )

    payload = {
        "experiment": "011D",
        "run": "run001",
        "kind": "deterministic_efficiency_accounting_validation",
        "runs": [asdict(record) for record in RUNS],
        "dominance": {
            "A_over_B": a_dominates_b,
            "C_over_D": c_dominates_d,
            "C_over_A": c_dominates_a,
        },
        "aggregates": {
            "all": asdict(all_aggregate),
            "successful": asdict(successful_aggregate),
            "unsuccessful": asdict(unsuccessful_aggregate),
        },
        "validation": {
            "behavioral_classifications_matched": (
                classification_matches
            ),
            "behavioral_classifications_total": len(RUNS),
            "aggregate_accounting_matched": (
                aggregate_accounting_matched
            ),
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