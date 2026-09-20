from __future__ import annotations

from dataclasses import dataclass

from hewn.bench.models import ResourceUsage, RunOutcome


@dataclass(frozen=True, slots=True)
class DominanceResult:
    comparable: bool
    dominates: bool | None
    reason: str


def behavioral_success(outcome: RunOutcome) -> bool:
    return outcome.behavioral_success


def resource_dominance(
    left_outcome: RunOutcome,
    left_resources: ResourceUsage,
    right_outcome: RunOutcome,
    right_resources: ResourceUsage,
) -> DominanceResult:
    if (
        left_outcome.behavioral_success
        != right_outcome.behavioral_success
    ):
        return DominanceResult(
            comparable=False,
            dominates=None,
            reason=(
                "resource dominance is undefined across "
                "different behavioral classifications"
            ),
        )

    left_values = _complete_resource_vector(left_resources)
    right_values = _complete_resource_vector(right_resources)

    if left_values is None or right_values is None:
        return DominanceResult(
            comparable=False,
            dominates=None,
            reason=(
                "resource dominance requires all resource "
                "measurements"
            ),
        )

    no_more_of_every_resource = all(
        left <= right
        for left, right in zip(
            left_values,
            right_values,
            strict=True,
        )
    )

    strictly_less_of_at_least_one = any(
        left < right
        for left, right in zip(
            left_values,
            right_values,
            strict=True,
        )
    )

    return DominanceResult(
        comparable=True,
        dominates=(
            no_more_of_every_resource
            and strictly_less_of_at_least_one
        ),
        reason="runs have comparable behavioral classifications",
    )


def _complete_resource_vector(
    resources: ResourceUsage,
) -> tuple[int | float, ...] | None:
    values = (
        resources.model_calls,
        resources.tool_calls,
        resources.execution_calls,
        resources.context_chars,
        resources.wall_time_seconds,
    )

    if any(value is None for value in values):
        return None

    return tuple(
        value
        for value in values
        if value is not None
    )