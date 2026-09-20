from __future__ import annotations

from collections import Counter
from dataclasses import dataclass

from hewn.bench.models import BenchmarkRun


@dataclass(frozen=True, slots=True)
class ResourceSummary:
    count: int
    total: int | float
    minimum: int | float
    maximum: int | float


@dataclass(frozen=True, slots=True)
class BenchmarkAggregate:
    total_runs: int
    behavioral_successes: int
    protocol_valid_runs: int
    runs_with_edits: int
    terminal_status_counts: dict[str, int]
    model_calls: ResourceSummary | None
    tool_calls: ResourceSummary | None
    execution_calls: ResourceSummary | None
    context_chars: ResourceSummary | None
    wall_time_seconds: ResourceSummary | None


def aggregate_runs(
    runs: tuple[BenchmarkRun, ...],
) -> BenchmarkAggregate:
    return BenchmarkAggregate(
        total_runs=len(runs),
        behavioral_successes=sum(
            run.outcome.behavioral_success
            for run in runs
        ),
        protocol_valid_runs=sum(
            run.outcome.protocol_valid
            for run in runs
        ),
        runs_with_edits=sum(
            run.outcome.edit_applied
            for run in runs
        ),
        terminal_status_counts=dict(
            Counter(
                run.terminal_status
                for run in runs
            )
        ),
        model_calls=_summarize(
            tuple(
                run.resources.model_calls
                for run in runs
            )
        ),
        tool_calls=_summarize(
            tuple(
                run.resources.tool_calls
                for run in runs
            )
        ),
        execution_calls=_summarize(
            tuple(
                run.resources.execution_calls
                for run in runs
            )
        ),
        context_chars=_summarize(
            tuple(
                run.resources.context_chars
                for run in runs
            )
        ),
        wall_time_seconds=_summarize(
            tuple(
                run.resources.wall_time_seconds
                for run in runs
            )
        ),
    )


def _summarize(
    values: tuple[int | float | None, ...],
) -> ResourceSummary | None:
    observed = tuple(
        value
        for value in values
        if value is not None
    )

    if not observed:
        return None

    return ResourceSummary(
        count=len(observed),
        total=sum(observed),
        minimum=min(observed),
        maximum=max(observed),
    )