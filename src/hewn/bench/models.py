from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class BenchmarkIdentity:
    benchmark_name: str
    benchmark_version: str
    task_id: str


@dataclass(frozen=True, slots=True)
class AgentVisibleCase:
    task_request: str
    repository_context: str
    tool_names: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class EvaluatorOnlyCase:
    behavioral_oracle_id: str
    regression_oracle_ids: tuple[str, ...] = ()
    structural_oracle_ids: tuple[str, ...] = ()
    expected_changed_files: tuple[str, ...] = ()
    expected_patch_markers: tuple[str, ...] = ()
    hidden_markers: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class BenchmarkCase:
    identity: BenchmarkIdentity
    agent_visible: AgentVisibleCase
    evaluator_only: EvaluatorOnlyCase


@dataclass(frozen=True, slots=True)
class RunProvenance:
    hewn_commit: str
    model_id: str
    model_configuration: Mapping[str, object]
    hardware_description: str
    repetition: int

    def __post_init__(self) -> None:
        if self.repetition < 1:
            raise ValueError("repetition must be at least 1")


@dataclass(frozen=True, slots=True)
class ResourceUsage:
    model_calls: int | None = None
    tool_calls: int | None = None
    execution_calls: int | None = None
    context_chars: int | None = None
    wall_time_seconds: float | None = None

    def __post_init__(self) -> None:
        integer_fields = {
            "model_calls": self.model_calls,
            "tool_calls": self.tool_calls,
            "execution_calls": self.execution_calls,
            "context_chars": self.context_chars,
        }

        for name, value in integer_fields.items():
            if value is not None and value < 0:
                raise ValueError(f"{name} must be non-negative")

        if (
            self.wall_time_seconds is not None
            and self.wall_time_seconds < 0
        ):
            raise ValueError(
                "wall_time_seconds must be non-negative"
            )


@dataclass(frozen=True, slots=True)
class RunOutcome:
    protocol_valid: bool
    edit_applied: bool
    task_passes: bool
    regression_passes: bool
    structural_passes: bool | None = None

    @property
    def behavioral_success(self) -> bool:
        structural_success = (
            True
            if self.structural_passes is None
            else self.structural_passes
        )

        return (
            self.task_passes
            and self.regression_passes
            and structural_success
        )


@dataclass(frozen=True, slots=True)
class BenchmarkRun:
    benchmark: BenchmarkIdentity
    provenance: RunProvenance
    outcome: RunOutcome
    terminal_status: str
    resources: ResourceUsage = ResourceUsage()
    error: str | None = None