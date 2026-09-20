from __future__ import annotations

from hewn.bench import (
    AgentVisibleCase,
    BenchmarkCase,
    BenchmarkIdentity,
    BenchmarkRun,
    EvaluatorOnlyCase,
    ResourceUsage,
    RunOutcome,
    RunProvenance,
    aggregate_runs,
    behavioral_success,
    build_agent_payload,
    resource_dominance,
    validate_agent_payload,
)


def make_identity() -> BenchmarkIdentity:
    return BenchmarkIdentity(
        benchmark_name="hewn-test",
        benchmark_version="1",
        task_id="task-001",
    )


def make_provenance(
    repetition: int = 1,
) -> RunProvenance:
    return RunProvenance(
        hewn_commit="abc123",
        model_id="test-model",
        model_configuration={
            "temperature": 0,
            "context_size": 4096,
        },
        hardware_description="test hardware",
        repetition=repetition,
    )


def make_run(
    *,
    outcome: RunOutcome,
    terminal_status: str = "completed",
    repetition: int = 1,
    resources: ResourceUsage | None = None,
    error: str | None = None,
) -> BenchmarkRun:
    return BenchmarkRun(
        benchmark=make_identity(),
        provenance=make_provenance(repetition),
        outcome=outcome,
        terminal_status=terminal_status,
        resources=resources or ResourceUsage(),
        error=error,
    )


def test_task_and_regression_success_is_behavioral_success() -> None:
    outcome = RunOutcome(
        protocol_valid=True,
        edit_applied=True,
        task_passes=True,
        regression_passes=True,
    )

    assert behavioral_success(outcome)


def test_regression_failure_prevents_behavioral_success() -> None:
    outcome = RunOutcome(
        protocol_valid=True,
        edit_applied=True,
        task_passes=True,
        regression_passes=False,
    )

    assert not behavioral_success(outcome)


def test_structural_failure_prevents_behavioral_success() -> None:
    outcome = RunOutcome(
        protocol_valid=True,
        edit_applied=True,
        task_passes=True,
        regression_passes=True,
        structural_passes=False,
    )

    assert not behavioral_success(outcome)


def test_absent_structural_requirement_does_not_prevent_success() -> None:
    outcome = RunOutcome(
        protocol_valid=True,
        edit_applied=True,
        task_passes=True,
        regression_passes=True,
        structural_passes=None,
    )

    assert behavioral_success(outcome)


def test_protocol_failure_does_not_change_behavioral_formula() -> None:
    outcome = RunOutcome(
        protocol_valid=False,
        edit_applied=False,
        task_passes=True,
        regression_passes=True,
    )

    assert behavioral_success(outcome)


def test_aggregation_keeps_failed_runs_in_denominator() -> None:
    successful = make_run(
        outcome=RunOutcome(
            protocol_valid=True,
            edit_applied=True,
            task_passes=True,
            regression_passes=True,
        ),
    )

    failed = make_run(
        outcome=RunOutcome(
            protocol_valid=False,
            edit_applied=False,
            task_passes=False,
            regression_passes=True,
        ),
        terminal_status="protocol_failure",
        repetition=2,
        error="invalid response",
    )

    aggregate = aggregate_runs(
        (successful, failed)
    )

    assert aggregate.total_runs == 2
    assert aggregate.behavioral_successes == 1
    assert aggregate.terminal_status_counts == {
        "completed": 1,
        "protocol_failure": 1,
    }


def test_aggregation_counts_protocol_valid_runs_separately() -> None:
    runs = (
        make_run(
            outcome=RunOutcome(
                protocol_valid=True,
                edit_applied=False,
                task_passes=False,
                regression_passes=True,
            ),
        ),
        make_run(
            outcome=RunOutcome(
                protocol_valid=False,
                edit_applied=False,
                task_passes=False,
                regression_passes=True,
            ),
            repetition=2,
        ),
    )

    aggregate = aggregate_runs(runs)

    assert aggregate.protocol_valid_runs == 1


def test_aggregation_counts_runs_with_edits_separately() -> None:
    runs = (
        make_run(
            outcome=RunOutcome(
                protocol_valid=True,
                edit_applied=True,
                task_passes=False,
                regression_passes=True,
            ),
        ),
        make_run(
            outcome=RunOutcome(
                protocol_valid=True,
                edit_applied=False,
                task_passes=False,
                regression_passes=True,
            ),
            repetition=2,
        ),
    )

    aggregate = aggregate_runs(runs)

    assert aggregate.runs_with_edits == 1


def test_resource_dominance_within_successful_runs() -> None:
    outcome = RunOutcome(
        protocol_valid=True,
        edit_applied=True,
        task_passes=True,
        regression_passes=True,
    )

    lower = ResourceUsage(
        model_calls=2,
        tool_calls=2,
        execution_calls=1,
        context_chars=1000,
        wall_time_seconds=4.0,
    )

    higher = ResourceUsage(
        model_calls=5,
        tool_calls=6,
        execution_calls=3,
        context_chars=3000,
        wall_time_seconds=12.0,
    )

    result = resource_dominance(
        outcome,
        lower,
        outcome,
        higher,
    )

    assert result.comparable
    assert result.dominates is True


def test_resource_dominance_within_unsuccessful_runs() -> None:
    outcome = RunOutcome(
        protocol_valid=True,
        edit_applied=True,
        task_passes=False,
        regression_passes=True,
    )

    lower = ResourceUsage(
        model_calls=1,
        tool_calls=0,
        execution_calls=0,
        context_chars=500,
        wall_time_seconds=2.0,
    )

    higher = ResourceUsage(
        model_calls=4,
        tool_calls=5,
        execution_calls=2,
        context_chars=2500,
        wall_time_seconds=10.0,
    )

    result = resource_dominance(
        outcome,
        lower,
        outcome,
        higher,
    )

    assert result.comparable
    assert result.dominates is True


def test_resource_dominance_is_undefined_across_correctness() -> None:
    successful = RunOutcome(
        protocol_valid=True,
        edit_applied=True,
        task_passes=True,
        regression_passes=True,
    )

    unsuccessful = RunOutcome(
        protocol_valid=True,
        edit_applied=True,
        task_passes=False,
        regression_passes=True,
    )

    successful_resources = ResourceUsage(
        model_calls=2,
        tool_calls=2,
        execution_calls=1,
        context_chars=1000,
        wall_time_seconds=4.0,
    )

    unsuccessful_resources = ResourceUsage(
        model_calls=1,
        tool_calls=0,
        execution_calls=0,
        context_chars=500,
        wall_time_seconds=2.0,
    )

    result = resource_dominance(
        unsuccessful,
        unsuccessful_resources,
        successful,
        successful_resources,
    )

    assert not result.comparable
    assert result.dominates is None


def test_clean_agent_payload_passes_integrity_validation() -> None:
    visible = AgentVisibleCase(
        task_request="Normalize names.",
        repository_context=(
            "src/sample/normalization.py\n"
            "def normalize_name(value): ..."
        ),
        tool_names=("read_file", "replace_text"),
    )

    evaluator = EvaluatorOnlyCase(
        behavioral_oracle_id="normalize-behavior",
        hidden_markers=(
            'normalize_name(" Alice ") == "alice"',
        ),
    )

    payload = build_agent_payload(visible)
    result = validate_agent_payload(
        payload,
        evaluator,
    )

    assert result.passes
    assert result.exposed_markers == ()


def test_hidden_marker_exposure_fails_integrity_validation() -> None:
    marker = 'normalize_name(" Alice ") == "alice"'

    visible = AgentVisibleCase(
        task_request="Normalize names.",
        repository_context=marker,
        tool_names=("read_file",),
    )

    evaluator = EvaluatorOnlyCase(
        behavioral_oracle_id="normalize-behavior",
        hidden_markers=(marker,),
    )

    payload = build_agent_payload(visible)
    result = validate_agent_payload(
        payload,
        evaluator,
    )

    assert not result.passes
    assert result.exposed_markers == (marker,)


def test_expected_file_path_is_not_automatically_contamination() -> None:
    expected_path = "src/sample/normalization.py"

    visible = AgentVisibleCase(
        task_request="Normalize names.",
        repository_context=expected_path,
        tool_names=("read_file",),
    )

    evaluator = EvaluatorOnlyCase(
        behavioral_oracle_id="normalize-behavior",
        expected_changed_files=(expected_path,),
        hidden_markers=(
            f"{expected_path}::expected_changed_file",
        ),
    )

    payload = build_agent_payload(visible)
    result = validate_agent_payload(
        payload,
        evaluator,
    )

    assert expected_path in payload
    assert result.passes


def test_benchmark_provenance_remains_attached() -> None:
    identity = make_identity()

    case = BenchmarkCase(
        identity=identity,
        agent_visible=AgentVisibleCase(
            task_request="Change behavior.",
            repository_context="repository",
            tool_names=("read_file",),
        ),
        evaluator_only=EvaluatorOnlyCase(
            behavioral_oracle_id="behavior",
        ),
    )

    run = BenchmarkRun(
        benchmark=identity,
        provenance=make_provenance(),
        outcome=RunOutcome(
            protocol_valid=True,
            edit_applied=True,
            task_passes=True,
            regression_passes=True,
        ),
        terminal_status="completed",
    )

    assert case.identity.benchmark_name == "hewn-test"
    assert case.identity.benchmark_version == "1"
    assert case.identity.task_id == "task-001"

    assert run.benchmark == case.identity
    assert run.provenance.hewn_commit == "abc123"
    assert run.provenance.model_id == "test-model"
    assert run.provenance.repetition == 1


def test_resource_aggregation_preserves_totals_and_ranges() -> None:
    outcome = RunOutcome(
        protocol_valid=True,
        edit_applied=True,
        task_passes=True,
        regression_passes=True,
    )

    runs = (
        make_run(
            outcome=outcome,
            resources=ResourceUsage(
                model_calls=2,
                tool_calls=3,
                execution_calls=1,
                context_chars=1000,
                wall_time_seconds=4.0,
            ),
        ),
        make_run(
            outcome=outcome,
            repetition=2,
            resources=ResourceUsage(
                model_calls=5,
                tool_calls=6,
                execution_calls=3,
                context_chars=3000,
                wall_time_seconds=12.0,
            ),
        ),
    )

    aggregate = aggregate_runs(runs)

    assert aggregate.model_calls is not None
    assert aggregate.model_calls.count == 2
    assert aggregate.model_calls.total == 7
    assert aggregate.model_calls.minimum == 2
    assert aggregate.model_calls.maximum == 5

    assert aggregate.wall_time_seconds is not None
    assert aggregate.wall_time_seconds.total == 16.0
    assert aggregate.wall_time_seconds.minimum == 4.0
    assert aggregate.wall_time_seconds.maximum == 12.0