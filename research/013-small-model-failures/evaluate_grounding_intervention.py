from __future__ import annotations

import argparse
import json
import shutil
import tempfile
from collections.abc import Callable
from dataclasses import asdict, dataclass
from pathlib import Path
from time import perf_counter
from typing import Any

from evaluate_feedback_representation import (
    CODING_MODEL,
    DEFAULT_EMBEDDING_MODEL,
    EDIT_TOOL,
    EXECUTION_TOOL,
    FIXTURES_ROOT,
    INTERVENTION_ELIGIBLE_TASKS,
    MAX_TURNS,
    MUTATION_FEEDBACK,
    REPETITIONS,
    CompletionPolicyProbe,
    MutationAwareCompletionPolicy,
    OracleResult,
    RecordingModel,
    build_normalized_diff,
    changed_files,
    coherent_completion_rejection_formatter,
    diff_hash,
    evaluate_regression_oracle,
    evaluate_structural_oracle,
    evaluate_task_oracle,
    load_manifest,
    snapshot_files,
    validate_fixture,
)

from hewn.agent import (
    Agent,
    AgentLimitError,
    AgentStagnationError,
)
from hewn.authority import AuthorityGrant, AuthorityPolicy
from hewn.builtin_tools import make_builtin_tool_registry
from hewn.completion import (
    CompletionPolicy,
    CompletionRequirement,
)
from hewn.context.builder import ContextBuilder
from hewn.execution import BubblewrapExecutionBackend
from hewn.llama_cpp import LlamaCppModel
from hewn.model_protocol import ModelProtocolError
from hewn.models import ModelError
from hewn.repository.index import RepositoryIndex
from hewn.retrieval.semantic_index import SemanticIndex
from hewn.retrieval.sentence_transformer import (
    SentenceTransformerEmbeddingModel,
)
from hewn.retrieval.symbol_documents import (
    build_symbol_documents,
)
from hewn.session import HewnSession
from hewn.tools import (
    ToolCall,
    ToolExecutor,
    ToolResult,
)
from hewn.workspace import (
    Workspace,
    WorkspaceViolationError,
)

MODULE_ROOT = Path(__file__).resolve().parent
RESULTS_ROOT = MODULE_ROOT / "results"

OUTPUT_PATH = (
    RESULTS_ROOT
    / "013c-grounding-intervention-run001.json"
)

MISSING_TARGET_FEEDBACK = (
    "Controller grounding feedback: The requested replacement target "
    "was not found in the selected file. Re-read the current source "
    "and ground any replacement in text that exists exactly in that "
    "file."
)

NOOP_FEEDBACK = (
    "Controller grounding feedback: The requested replacement would "
    "leave the selected file unchanged. Re-read the current source "
    "and make a replacement only if it produces an actual repository "
    "change."
)

GROUNDING_REASON_MISSING_TARGET = "missing_target"
GROUNDING_REASON_NOOP = "no_op_replacement"


@dataclass(frozen=True, slots=True)
class GroundingToolCall:
    name: str
    arguments: dict[str, Any]
    ok: bool
    effective_mutation: bool
    grounding_eligible: bool
    grounding_delivered: bool
    grounding_reason: str | None


@dataclass
class GroundingProbe:
    eligible: bool = False
    delivered: bool = False
    reason: str | None = None
    edit_attempts_at_delivery: int | None = None
    edit_attempts: int = 0

    def record_edit_attempt(self) -> None:
        self.edit_attempts += 1

    @property
    def edit_attempted_after_grounding(self) -> bool:
        if (
            not self.delivered
            or self.edit_attempts_at_delivery is None
        ):
            return False

        return self.edit_attempts > self.edit_attempts_at_delivery


class GroundingToolExecutor(ToolExecutor):
    """013C treatment layered over the production executor.

    The executor never chooses an action for the model and never constructs
    replacement text.

    It observes model-selected replace_text calls and measures whether the
    selected file actually changed. For the first frozen mechanically
    ineffective edit after mutation feedback, it appends the frozen grounding
    observation to the ordinary tool observation.

    The underlying ToolResult.ok value is preserved.
    """

    def __init__(
        self,
        registry: Any,
        *,
        workspace: Workspace,
        authority_policy: AuthorityPolicy,
        mutation_feedback_delivered: Callable[[], bool],
        grounding_enabled: bool,
    ) -> None:
        super().__init__(
            registry,
            authority_policy=authority_policy,
        )

        self.workspace = workspace
        self.mutation_feedback_delivered = (
            mutation_feedback_delivered
        )
        self.grounding_enabled = grounding_enabled

        self.calls: list[GroundingToolCall] = []
        self.probe = GroundingProbe()

    def _selected_file_bytes(
        self,
        call: ToolCall,
    ) -> bytes | None:
        if call.name != EDIT_TOOL:
            return None

        raw_path = call.arguments.get("path")

        if not isinstance(raw_path, str):
            return None

        try:
            path = self.workspace.resolve(raw_path)
        except WorkspaceViolationError:
            return None

        if not path.exists() or not path.is_file():
            return None

        return path.read_bytes()

    @staticmethod
    def _is_missing_target(
        call: ToolCall,
        result: ToolResult,
    ) -> bool:
        if call.name != EDIT_TOOL or result.ok:
            return False

        return result.error == "Text to replace was not found"

    @staticmethod
    def _append_feedback(
        result: ToolResult,
        feedback: str,
    ) -> ToolResult:
        if result.ok:
            existing = result.output or ""

            output = (
                f"{existing}\n\n{feedback}"
                if existing
                else feedback
            )

            return ToolResult(
                ok=True,
                output=output,
                error=result.error,
            )

        existing_error = result.error or ""

        error = (
            f"{existing_error}\n\n{feedback}"
            if existing_error
            else feedback
        )

        return ToolResult(
            ok=False,
            output=result.output,
            error=error,
        )

    def execute(
        self,
        call: ToolCall,
    ) -> ToolResult:
        before = self._selected_file_bytes(call)

        if call.name == EDIT_TOOL:
            self.probe.record_edit_attempt()

        result = super().execute(call)

        after = self._selected_file_bytes(call)

        effective_mutation = (
            call.name == EDIT_TOOL
            and before is not None
            and after is not None
            and before != after
        )

        mutation_feedback_seen = (
            self.mutation_feedback_delivered()
        )

        missing_target = self._is_missing_target(
            call,
            result,
        )

        no_op = (
            call.name == EDIT_TOOL
            and result.ok
            and before is not None
            and after is not None
            and before == after
        )

        grounding_reason: str | None = None

        if missing_target:
            grounding_reason = (
                GROUNDING_REASON_MISSING_TARGET
            )
        elif no_op:
            grounding_reason = GROUNDING_REASON_NOOP

        grounding_eligible = (
            self.grounding_enabled
            and mutation_feedback_seen
            and grounding_reason is not None
        )

        grounding_delivered = (
            grounding_eligible
            and not self.probe.delivered
        )

        returned_result = result

        if grounding_delivered:
            if grounding_reason == GROUNDING_REASON_MISSING_TARGET:
                feedback = MISSING_TARGET_FEEDBACK
            elif grounding_reason == GROUNDING_REASON_NOOP:
                feedback = NOOP_FEEDBACK
            else:
                raise AssertionError(
                    "Unexpected grounding reason"
                )

            returned_result = self._append_feedback(
                result,
                feedback,
            )

            self.probe.eligible = True
            self.probe.delivered = True
            self.probe.reason = grounding_reason
            self.probe.edit_attempts_at_delivery = (
                self.probe.edit_attempts
            )

        elif grounding_eligible:
            self.probe.eligible = True

        self.calls.append(
            GroundingToolCall(
                name=call.name,
                arguments=dict(call.arguments),
                ok=result.ok,
                effective_mutation=effective_mutation,
                grounding_eligible=grounding_eligible,
                grounding_delivered=grounding_delivered,
                grounding_reason=grounding_reason,
            )
        )

        return returned_result


@dataclass(frozen=True, slots=True)
class RunResult:
    task_id: str
    repetition: int
    request: str

    behavioral_success: bool
    task_passed: bool
    task_detail: str
    regression_passed: bool
    regression_detail: str
    structural_passed: bool | None
    structural_detail: str | None

    protocol_valid: bool
    protocol_error: str | None
    raw_protocol_response: str | None
    parsed_model_responses: tuple[str, ...]

    final_response_observed: bool
    agent_text: str
    terminal_status: str
    terminal_error: str | None

    mutation_intervention_eligible: bool
    mutation_intervention_delivered: bool
    edit_attempted_after_mutation_intervention: bool

    grounding_intervention_eligible: bool
    grounding_intervention_delivered: bool
    grounding_reason: str | None
    edit_attempted_after_grounding_intervention: bool

    model_calls: int
    tool_calls: int
    tool_names: tuple[str, ...]
    successful_tool_calls: int
    failed_tool_calls: int

    edit_attempts: int
    tool_accepted_edit_calls: int
    effective_repository_mutations: int
    execution_calls: int

    context_character_count: int
    context_evidence_count: int

    wall_time_seconds: float

    changed_files: tuple[str, ...]
    expected_changed_files: tuple[str, ...]
    changed_expected_files: tuple[str, ...]
    unexpected_changed_files: tuple[str, ...]

    normalized_diff: str
    diff_sha256: str


@dataclass(frozen=True, slots=True)
class TaskAggregate:
    task_id: str
    repetitions: int

    behavioral_successes: int
    protocol_valid_runs: int
    runs_with_repository_delta: int

    mutation_intervention_eligible_runs: int
    mutation_intervention_delivered_runs: int
    edit_after_mutation_intervention_runs: int

    grounding_intervention_eligible_runs: int
    grounding_intervention_delivered_runs: int
    edit_after_grounding_intervention_runs: int

    runs_with_tool_accepted_edits: int
    runs_with_effective_mutations: int

    distinct_patch_hashes: int
    patch_hashes: tuple[str, ...]

    model_calls_min: int
    model_calls_max: int
    tool_calls_min: int
    tool_calls_max: int
    wall_time_min_seconds: float
    wall_time_max_seconds: float

    behaviorally_variable: bool
    patch_variable: bool


def build_session(
    root: Path,
    *,
    mutation_required: bool,
    grounding_enabled: bool,
) -> tuple[
    HewnSession,
    RecordingModel,
    GroundingToolExecutor,
    CompletionPolicyProbe,
]:
    workspace = Workspace(root)

    repository_index = RepositoryIndex.build(root)

    embedding_model = SentenceTransformerEmbeddingModel(
        DEFAULT_EMBEDDING_MODEL
    )

    semantic_index = SemanticIndex.build(
        build_symbol_documents(repository_index),
        model=embedding_model,
    )

    context_builder = ContextBuilder(
        repository_root=root,
        repository_index=repository_index,
    )

    recording_model = RecordingModel(
        delegate=LlamaCppModel()
    )

    registry = make_builtin_tool_registry(
        workspace,
        repository_index,
        execution_backend=BubblewrapExecutionBackend(),
    )

    authority_policy = AuthorityPolicy(
        AuthorityGrant(
            repository_read=True,
            repository_write=True,
            approved_checks=True,
        )
    )

    policy_probe = CompletionPolicyProbe()

    def mutation_feedback_delivered() -> bool:
        policy = policy_probe.policy

        return (
            policy is not None
            and isinstance(
                policy,
                MutationAwareCompletionPolicy,
            )
            and policy.intervention_delivered
        )

    recording_executor = GroundingToolExecutor(
        registry,
        workspace=workspace,
        authority_policy=authority_policy,
        mutation_feedback_delivered=(
            mutation_feedback_delivered
        ),
        grounding_enabled=grounding_enabled,
    )

    def make_completion_policy(
        requirement: CompletionRequirement,
    ) -> CompletionPolicy:
        policy = MutationAwareCompletionPolicy(
            requirement=requirement,
            mutation_required=mutation_required,
        )

        policy_probe.policy = policy
        return policy

    agent = Agent(
        model=recording_model,
        registry=registry,
        executor=recording_executor,
        max_turns=MAX_TURNS,
        completion_policy_factory=make_completion_policy,
        completion_rejection_formatter=(
            coherent_completion_rejection_formatter
        ),
    )

    session = HewnSession(
        agent=agent,
        repository_index=repository_index,
        semantic_index=semantic_index,
        embedding_model=embedding_model,
        context_builder=context_builder,
    )

    return (
        session,
        recording_model,
        recording_executor,
        policy_probe,
    )


def run_one(
    task: dict[str, Any],
    repetition: int,
) -> RunResult:
    task_id = str(task["task_id"])
    request = str(task["request"])

    expected_changed = tuple(
        str(path)
        for path in task["expected_changed_files"]
    )

    source_fixture = (
        FIXTURES_ROOT / str(task["fixture"])
    )

    with tempfile.TemporaryDirectory(
        prefix=f"hewn-013c-{task_id}-"
    ) as temporary:
        root = Path(temporary) / "repo"

        shutil.copytree(
            source_fixture,
            root,
        )

        before = snapshot_files(root)

        mutation_intervention_eligible = (
            task_id in INTERVENTION_ELIGIBLE_TASKS
        )

        (
            session,
            recording_model,
            recording_executor,
            policy_probe,
        ) = build_session(
            root,
            mutation_required=mutation_intervention_eligible,
            grounding_enabled=mutation_intervention_eligible,
        )

        prepared = session.prepare_context(
            request
        )

        context_character_count = (
            prepared.context.character_count
        )

        context_evidence_count = (
            prepared.context.evidence_count
        )

        agent_text = ""
        final_response_observed = False
        terminal_status = "unknown"
        terminal_error: str | None = None

        started = perf_counter()

        try:
            result = session.agent.run(
                request,
                completion_requirement=(
                    CompletionRequirement.VERIFIED
                ),
                context=prepared.context,
            )

            agent_text = result.text
            final_response_observed = True
            terminal_status = "completed"

        except ModelProtocolError as exc:
            terminal_status = "protocol_failure"
            terminal_error = str(exc)

        except AgentStagnationError as exc:
            terminal_status = "stagnation"
            terminal_error = str(exc)

        except AgentLimitError as exc:
            terminal_status = "turn_limit"
            terminal_error = str(exc)

        except ModelError as exc:
            terminal_status = "model_error"
            terminal_error = str(exc)

        elapsed = perf_counter() - started

        completion_policy = policy_probe.policy

        if completion_policy is None:
            raise RuntimeError(
                "Agent did not construct its completion policy"
            )

        if not isinstance(
            completion_policy,
            MutationAwareCompletionPolicy,
        ):
            raise TypeError(
                "013C expected MutationAwareCompletionPolicy"
            )

        mutation_intervention_delivered = (
            completion_policy.intervention_delivered
        )

        edit_attempted_after_mutation_intervention = (
            mutation_intervention_delivered
            and completion_policy.edit_attempted
        )

        grounding_probe = recording_executor.probe

        after = snapshot_files(root)

        changed = changed_files(
            before,
            after,
        )

        normalized_diff = build_normalized_diff(
            before,
            after,
        )

        task_oracle: OracleResult = evaluate_task_oracle(
            task_id,
            root,
        )

        regression_oracle = evaluate_regression_oracle(
            task_id,
            root,
        )

        structural_oracle = evaluate_structural_oracle(
            task_id,
            root,
        )

        structural_passed = (
            None
            if structural_oracle is None
            else structural_oracle.passed
        )

        structural_detail = (
            None
            if structural_oracle is None
            else structural_oracle.detail
        )

        behavioral_success = (
            task_oracle.passed
            and regression_oracle.passed
            and (
                structural_oracle is None
                or structural_oracle.passed
            )
        )

        tool_names = tuple(
            call.name
            for call in recording_executor.calls
        )

        edit_calls = [
            call
            for call in recording_executor.calls
            if call.name == EDIT_TOOL
        ]

        execution_calls = sum(
            call.name == EXECUTION_TOOL
            for call in recording_executor.calls
        )

        changed_expected = tuple(
            path
            for path in changed
            if path in expected_changed
        )

        unexpected_changed = tuple(
            path
            for path in changed
            if path not in expected_changed
        )

        protocol_valid = (
            recording_model.protocol_failures == 0
        )

        return RunResult(
            task_id=task_id,
            repetition=repetition,
            request=request,
            behavioral_success=behavioral_success,
            task_passed=task_oracle.passed,
            task_detail=task_oracle.detail,
            regression_passed=regression_oracle.passed,
            regression_detail=regression_oracle.detail,
            structural_passed=structural_passed,
            structural_detail=structural_detail,
            protocol_valid=protocol_valid,
            protocol_error=(
                recording_model.last_protocol_error
            ),
            raw_protocol_response=(
                recording_model.last_raw_response
            ),
            parsed_model_responses=tuple(
                recording_model.parsed_responses
            ),
            final_response_observed=(
                final_response_observed
            ),
            agent_text=agent_text,
            terminal_status=terminal_status,
            terminal_error=terminal_error,
            mutation_intervention_eligible=(
                mutation_intervention_eligible
            ),
            mutation_intervention_delivered=(
                mutation_intervention_delivered
            ),
            edit_attempted_after_mutation_intervention=(
                edit_attempted_after_mutation_intervention
            ),
            grounding_intervention_eligible=(
                grounding_probe.eligible
            ),
            grounding_intervention_delivered=(
                grounding_probe.delivered
            ),
            grounding_reason=grounding_probe.reason,
            edit_attempted_after_grounding_intervention=(
                grounding_probe.edit_attempted_after_grounding
            ),
            model_calls=recording_model.model_calls,
            tool_calls=len(
                recording_executor.calls
            ),
            tool_names=tool_names,
            successful_tool_calls=sum(
                call.ok
                for call in recording_executor.calls
            ),
            failed_tool_calls=sum(
                not call.ok
                for call in recording_executor.calls
            ),
            edit_attempts=len(edit_calls),
            tool_accepted_edit_calls=sum(
                call.ok
                for call in edit_calls
            ),
            effective_repository_mutations=sum(
                call.effective_mutation
                for call in edit_calls
            ),
            execution_calls=execution_calls,
            context_character_count=(
                context_character_count
            ),
            context_evidence_count=(
                context_evidence_count
            ),
            wall_time_seconds=elapsed,
            changed_files=changed,
            expected_changed_files=expected_changed,
            changed_expected_files=changed_expected,
            unexpected_changed_files=(
                unexpected_changed
            ),
            normalized_diff=normalized_diff,
            diff_sha256=diff_hash(
                normalized_diff
            ),
        )


def aggregate_task(
    task_id: str,
    runs: list[RunResult],
) -> TaskAggregate:
    if len(runs) != REPETITIONS:
        raise ValueError(
            f"{task_id} expected {REPETITIONS} runs, "
            f"found {len(runs)}"
        )

    successes = sum(
        run.behavioral_success
        for run in runs
    )

    hashes = tuple(
        sorted(
            {
                run.diff_sha256
                for run in runs
            }
        )
    )

    return TaskAggregate(
        task_id=task_id,
        repetitions=len(runs),
        behavioral_successes=successes,
        protocol_valid_runs=sum(
            run.protocol_valid
            for run in runs
        ),
        runs_with_repository_delta=sum(
            bool(run.changed_files)
            for run in runs
        ),
        mutation_intervention_eligible_runs=sum(
            run.mutation_intervention_eligible
            for run in runs
        ),
        mutation_intervention_delivered_runs=sum(
            run.mutation_intervention_delivered
            for run in runs
        ),
        edit_after_mutation_intervention_runs=sum(
            run.edit_attempted_after_mutation_intervention
            for run in runs
        ),
        grounding_intervention_eligible_runs=sum(
            run.grounding_intervention_eligible
            for run in runs
        ),
        grounding_intervention_delivered_runs=sum(
            run.grounding_intervention_delivered
            for run in runs
        ),
        edit_after_grounding_intervention_runs=sum(
            run.edit_attempted_after_grounding_intervention
            for run in runs
        ),
        runs_with_tool_accepted_edits=sum(
            run.tool_accepted_edit_calls > 0
            for run in runs
        ),
        runs_with_effective_mutations=sum(
            run.effective_repository_mutations > 0
            for run in runs
        ),
        distinct_patch_hashes=len(hashes),
        patch_hashes=hashes,
        model_calls_min=min(
            run.model_calls
            for run in runs
        ),
        model_calls_max=max(
            run.model_calls
            for run in runs
        ),
        tool_calls_min=min(
            run.tool_calls
            for run in runs
        ),
        tool_calls_max=max(
            run.tool_calls
            for run in runs
        ),
        wall_time_min_seconds=min(
            run.wall_time_seconds
            for run in runs
        ),
        wall_time_max_seconds=max(
            run.wall_time_seconds
            for run in runs
        ),
        behaviorally_variable=(
            0 < successes < len(runs)
        ),
        patch_variable=len(hashes) > 1,
    )


def print_run(
    result: RunResult,
) -> None:
    print(
        f"{result.task_id} "
        f"rep={result.repetition}: "
        f"behavior={result.behavioral_success} "
        f"task={result.task_passed} "
        f"regression={result.regression_passed} "
        f"protocol={result.protocol_valid} "
        f"terminal={result.terminal_status} "
        f"models={result.model_calls} "
        f"tools={result.tool_calls} "
        f"edits={result.edit_attempts} "
        f"accepted={result.tool_accepted_edit_calls} "
        f"effective={result.effective_repository_mutations} "
        f"checks={result.execution_calls} "
        f"time={result.wall_time_seconds:.2f}s"
    )

    print(
        "  mutation_intervention="
        f"eligible:{result.mutation_intervention_eligible} "
        f"delivered:{result.mutation_intervention_delivered} "
        "edit_after:"
        f"{result.edit_attempted_after_mutation_intervention}"
    )

    print(
        "  grounding_intervention="
        f"eligible:{result.grounding_intervention_eligible} "
        f"delivered:{result.grounding_intervention_delivered} "
        f"reason:{result.grounding_reason} "
        "edit_after:"
        f"{result.edit_attempted_after_grounding_intervention}"
    )

    print(
        f"  changed={list(result.changed_files)}"
    )

    print(
        f"  patch={result.diff_sha256[:16]}"
    )

    if result.terminal_error is not None:
        print(
            f"  error={result.terminal_error}"
        )


def print_aggregate(
    aggregate: TaskAggregate,
) -> None:
    print(f"\n[{aggregate.task_id}]")

    print(
        "behavioral successes: "
        f"{aggregate.behavioral_successes}/"
        f"{aggregate.repetitions}"
    )

    print(
        "protocol-valid runs: "
        f"{aggregate.protocol_valid_runs}/"
        f"{aggregate.repetitions}"
    )

    print(
        "runs with repository delta: "
        f"{aggregate.runs_with_repository_delta}/"
        f"{aggregate.repetitions}"
    )

    print(
        "mutation intervention delivered: "
        f"{aggregate.mutation_intervention_delivered_runs}/"
        f"{aggregate.repetitions}"
    )

    print(
        "grounding intervention eligible: "
        f"{aggregate.grounding_intervention_eligible_runs}/"
        f"{aggregate.repetitions}"
    )

    print(
        "grounding intervention delivered: "
        f"{aggregate.grounding_intervention_delivered_runs}/"
        f"{aggregate.repetitions}"
    )

    print(
        "edit after grounding: "
        f"{aggregate.edit_after_grounding_intervention_runs}/"
        f"{aggregate.repetitions}"
    )

    print(
        "runs with tool-accepted edits: "
        f"{aggregate.runs_with_tool_accepted_edits}/"
        f"{aggregate.repetitions}"
    )

    print(
        "runs with effective mutations: "
        f"{aggregate.runs_with_effective_mutations}/"
        f"{aggregate.repetitions}"
    )

    print(
        "distinct patch hashes: "
        f"{aggregate.distinct_patch_hashes}"
    )

    print(
        "model calls range: "
        f"{aggregate.model_calls_min}-"
        f"{aggregate.model_calls_max}"
    )

    print(
        "tool calls range: "
        f"{aggregate.tool_calls_min}-"
        f"{aggregate.tool_calls_max}"
    )

    print(
        "wall time range: "
        f"{aggregate.wall_time_min_seconds:.2f}-"
        f"{aggregate.wall_time_max_seconds:.2f}s"
    )

    print(
        "behaviorally variable: "
        f"{aggregate.behaviorally_variable}"
    )

    print(
        "patch variable: "
        f"{aggregate.patch_variable}"
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run Module 13 deterministic edit-grounding "
            "experiment."
        )
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help=(
            "Validate frozen fixtures and experiment "
            "configuration without invoking the coding model."
        ),
    )

    return parser.parse_args()


def main() -> None:
    args = parse_args()

    tasks = load_manifest()

    for task in tasks:
        validate_fixture(task)

    if args.dry_run:
        candidates = sum(
            str(task["task_id"])
            in INTERVENTION_ELIGIBLE_TASKS
            for task in tasks
        )

        print(
            "013C dry run passed: "
            f"{len(tasks)} frozen tasks, "
            f"{candidates} grounding candidates, "
            f"{REPETITIONS} repetitions each, "
            f"{len(tasks) * REPETITIONS} planned runs."
        )
        return

    RESULTS_ROOT.mkdir(
        parents=True,
        exist_ok=True,
    )

    results: list[RunResult] = []

    print(
        "===== 013C DETERMINISTIC EDIT GROUNDING ====="
    )

    for task in tasks:
        task_id = str(
            task["task_id"]
        )

        print(
            f"\n===== {task_id} ====="
        )

        for repetition in range(
            1,
            REPETITIONS + 1,
        ):
            result = run_one(
                task,
                repetition,
            )

            results.append(
                result
            )

            print_run(
                result
            )

    aggregates: list[TaskAggregate] = []

    for task in tasks:
        task_id = str(
            task["task_id"]
        )

        task_runs = [
            result
            for result in results
            if result.task_id == task_id
        ]

        aggregates.append(
            aggregate_task(
                task_id,
                task_runs,
            )
        )

    overall_runs = len(results)

    overall_behavioral_successes = sum(
        result.behavioral_success
        for result in results
    )

    overall_protocol_valid_runs = sum(
        result.protocol_valid
        for result in results
    )

    overall_repository_delta_runs = sum(
        bool(result.changed_files)
        for result in results
    )

    overall_mutation_delivered = sum(
        result.mutation_intervention_delivered
        for result in results
    )

    overall_grounding_eligible = sum(
        result.grounding_intervention_eligible
        for result in results
    )

    overall_grounding_delivered = sum(
        result.grounding_intervention_delivered
        for result in results
    )

    overall_edit_after_grounding = sum(
        result.edit_attempted_after_grounding_intervention
        for result in results
    )

    overall_effective_mutation_runs = sum(
        result.effective_repository_mutations > 0
        for result in results
    )

    payload: dict[str, Any] = {
        "experiment": "013C",
        "run": "run001",
        "model": CODING_MODEL,
        "embedding_model": DEFAULT_EMBEDDING_MODEL,
        "repetitions_per_task": REPETITIONS,
        "max_turns": MAX_TURNS,
        "completion_requirement": "VERIFIED",
        "mutation_intervention": {
            "feedback": MUTATION_FEEDBACK,
            "eligible_tasks": sorted(
                INTERVENTION_ELIGIBLE_TASKS
            ),
            "bounded_feedback_count": 1,
        },
        "feedback_representation": {
            "rejected_response_retained": True,
            "rejected_response_role": "assistant",
            "controller_feedback_role": "user",
            "controller_prefix": "Controller feedback: ",
        },
        "grounding_intervention": {
            "eligible_tasks": sorted(
                INTERVENTION_ELIGIBLE_TASKS
            ),
            "bounded_feedback_count": 1,
            "triggers": [
                GROUNDING_REASON_MISSING_TARGET,
                GROUNDING_REASON_NOOP,
            ],
            "missing_target_feedback": (
                MISSING_TARGET_FEEDBACK
            ),
            "no_op_feedback": NOOP_FEEDBACK,
            "semantic_repair_provided": False,
            "replacement_text_provided": False,
            "effective_mutation_definition": (
                "selected file bytes differ immediately "
                "before and after replace_text"
            ),
        },
        "model_configuration": {
            "temperature": 0.0,
            "context_window": 4096,
            "llama_cpp_threads": 4,
            "endpoint": "http://127.0.0.1:8080",
        },
        "runs": [
            asdict(result)
            for result in results
        ],
        "aggregates": [
            asdict(aggregate)
            for aggregate in aggregates
        ],
        "overall": {
            "runs": overall_runs,
            "behavioral_successes": (
                overall_behavioral_successes
            ),
            "protocol_valid_runs": (
                overall_protocol_valid_runs
            ),
            "runs_with_repository_delta": (
                overall_repository_delta_runs
            ),
            "mutation_intervention_delivered_runs": (
                overall_mutation_delivered
            ),
            "grounding_intervention_eligible_runs": (
                overall_grounding_eligible
            ),
            "grounding_intervention_delivered_runs": (
                overall_grounding_delivered
            ),
            "edit_after_grounding_intervention_runs": (
                overall_edit_after_grounding
            ),
            "runs_with_effective_mutations": (
                overall_effective_mutation_runs
            ),
        },
    }

    OUTPUT_PATH.write_text(
        json.dumps(
            payload,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    print(
        "\n===== 013C DETERMINISTIC EDIT GROUNDING ====="
    )

    for aggregate in aggregates:
        print_aggregate(
            aggregate
        )

    print(
        "\n===== OVERALL ====="
    )

    print(
        "behavioral successes: "
        f"{overall_behavioral_successes}/"
        f"{overall_runs}"
    )

    print(
        "protocol-valid runs: "
        f"{overall_protocol_valid_runs}/"
        f"{overall_runs}"
    )

    print(
        "runs with repository delta: "
        f"{overall_repository_delta_runs}/"
        f"{overall_runs}"
    )

    print(
        "grounding intervention eligible: "
        f"{overall_grounding_eligible}/"
        f"{overall_runs}"
    )

    print(
        "grounding intervention delivered: "
        f"{overall_grounding_delivered}/"
        f"{overall_runs}"
    )

    print(
        "edit after grounding: "
        f"{overall_edit_after_grounding}/"
        f"{overall_runs}"
    )

    print(
        "runs with effective mutations: "
        f"{overall_effective_mutation_runs}/"
        f"{overall_runs}"
    )

    print(
        f"\nWrote results to {OUTPUT_PATH}"
    )


if __name__ == "__main__":
    main()