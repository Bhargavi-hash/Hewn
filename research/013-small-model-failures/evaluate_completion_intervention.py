from __future__ import annotations

import argparse
import difflib
import hashlib
import json
import shutil
import sys
import tempfile
from dataclasses import asdict, dataclass, field
from pathlib import Path
from time import perf_counter
from typing import Any

from hewn.agent import (
    Agent,
    AgentLimitError,
    AgentStagnationError,
)
from hewn.authority import AuthorityGrant, AuthorityPolicy
from hewn.builtin_tools import make_builtin_tool_registry
from hewn.completion import CompletionPolicy, CompletionRequirement
from hewn.context.builder import ContextBuilder
from hewn.execution import (
    BubblewrapExecutionBackend,
    ExecutionError,
)
from hewn.llama_cpp import LlamaCppModel
from hewn.model_protocol import ModelProtocolError
from hewn.models import Message, ModelError, ModelResponse
from hewn.repository.index import RepositoryIndex
from hewn.retrieval.semantic_index import SemanticIndex
from hewn.retrieval.sentence_transformer import (
    SentenceTransformerEmbeddingModel,
)
from hewn.retrieval.symbol_documents import build_symbol_documents
from hewn.session import HewnSession
from hewn.tools import (
    ToolCall,
    ToolDefinition,
    ToolExecutor,
    ToolResult,
)
from hewn.workspace import Workspace

MODULE_ROOT = Path(__file__).resolve().parent
FIXTURES_ROOT = MODULE_ROOT / "fixtures-013b"
MANIFEST_PATH = FIXTURES_ROOT / "manifest.json"
RESULTS_ROOT = MODULE_ROOT / "results"

OUTPUT_PATH = (
    RESULTS_ROOT
    / "013b-completion-intervention-run001.json"
)

DEFAULT_EMBEDDING_MODEL = "BAAI/bge-small-en-v1.5"
CODING_MODEL = "Qwen2.5-Coder-1.5B-Instruct Q4_K_M"

REPETITIONS = 5
MAX_TURNS = 20

EDIT_TOOL = "replace_text"
EXECUTION_TOOL = "run_check"

MUTATION_FEEDBACK = (
    "The task requires a repository modification, but no edit has been "
    "attempted. Use an available repository-editing action before "
    "completing the task."
)

INTERVENTION_ELIGIBLE_TASKS = frozenset(
    {
        "stability-002",
        "stability-003",
    }
)


@dataclass
class CompletionPolicyProbe:
    policy: MutationAwareCompletionPolicy | None = None


@dataclass
class MutationAwareCompletionPolicy(CompletionPolicy):
    """Completion policy for the frozen 013B-1 intervention.

    For mutation-required tasks, the first final response before any
    replace_text attempt receives the frozen mutation-specific feedback.

    The intervention is delivered at most once. After it has been delivered,
    or after any replace_text attempt, ordinary CompletionPolicy behavior
    resumes.

    A replace_text call counts as an edit attempt regardless of whether the
    tool application succeeds. Successful edit application is measured
    separately by the experiment runner.
    """

    mutation_required: bool = False
    edit_attempted: bool = False
    intervention_delivered: bool = False

    def record_tool_attempt(
        self,
        *,
        call: ToolCall,
        result: ToolResult,
    ) -> None:
        del result

        if call.name == EDIT_TOOL:
            self.edit_attempted = True

    def can_finish(self) -> bool:
        if (
            self.mutation_required
            and not self.edit_attempted
            and not self.intervention_delivered
        ):
            return False

        return super().can_finish()

    def rejection_reason(self) -> str:
        if (
            self.mutation_required
            and not self.edit_attempted
            and not self.intervention_delivered
        ):
            self.intervention_delivered = True
            return MUTATION_FEEDBACK

        return super().rejection_reason()


@dataclass(frozen=True, slots=True)
class RecordedToolCall:
    name: str
    arguments: dict[str, Any]
    ok: bool


@dataclass
class RecordingModel:
    delegate: LlamaCppModel
    model_calls: int = 0
    protocol_failures: int = 0
    last_protocol_error: str | None = None
    last_raw_response: str | None = None
    parsed_responses: list[str] = field(
        default_factory=list
    )

    def respond(
        self,
        messages: list[Message],
        tools: list[ToolDefinition],
    ) -> ModelResponse:
        self.model_calls += 1

        try:
            response = self.delegate.respond(
                messages=messages,
                tools=tools,
            )
        except ModelProtocolError as exc:
            self.protocol_failures += 1
            self.last_protocol_error = str(exc)
            self.last_raw_response = exc.raw_response
            raise

        self.parsed_responses.append(
            repr(response)
        )

        return response


class RecordingToolExecutor(ToolExecutor):
    def __init__(
        self,
        registry: Any,
        *,
        authority_policy: AuthorityPolicy,
    ) -> None:
        super().__init__(
            registry,
            authority_policy=authority_policy,
        )
        self.calls: list[RecordedToolCall] = []

    def execute(
        self,
        call: ToolCall,
    ) -> ToolResult:
        result = super().execute(call)

        self.calls.append(
            RecordedToolCall(
                name=call.name,
                arguments=dict(call.arguments),
                ok=result.ok,
            )
        )

        return result


@dataclass(frozen=True, slots=True)
class OracleResult:
    passed: bool
    detail: str


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

    intervention_eligible: bool
    intervention_delivered: bool
    edit_attempted_after_intervention: bool

    model_calls: int
    tool_calls: int
    tool_names: tuple[str, ...]
    successful_tool_calls: int
    failed_tool_calls: int

    edit_attempts: int
    successful_edit_applications: int
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
    runs_producing_edits: int

    intervention_eligible_runs: int
    intervention_delivered_runs: int
    edit_after_intervention_runs: int

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


def load_manifest() -> list[dict[str, Any]]:
    payload = json.loads(
        MANIFEST_PATH.read_text(encoding="utf-8")
    )

    tasks = payload.get("tasks")

    if not isinstance(tasks, list):
        raise TypeError(
            "013B manifest tasks must be a list"
        )

    if len(tasks) != 3:
        raise ValueError(
            f"013B requires exactly 3 tasks, found {len(tasks)}"
        )

    return tasks


def snapshot_files(
    root: Path,
) -> dict[str, bytes]:
    snapshot: dict[str, bytes] = {}

    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue

        relative = path.relative_to(root).as_posix()

        if (
            relative.startswith(
                (
                    ".pytest_cache/",
                    "__pycache__/",
                )
            )
            or "/__pycache__/" in relative
            or relative.endswith(".pyc")
        ):
            continue

        snapshot[relative] = path.read_bytes()

    return snapshot


def changed_files(
    before: dict[str, bytes],
    after: dict[str, bytes],
) -> tuple[str, ...]:
    paths = set(before) | set(after)

    return tuple(
        sorted(
            path
            for path in paths
            if before.get(path) != after.get(path)
        )
    )


def decode_for_diff(
    content: bytes | None,
) -> list[str]:
    if content is None:
        return []

    return (
        content.decode(
            "utf-8",
            errors="replace",
        )
        .replace("\r\n", "\n")
        .replace("\r", "\n")
        .splitlines(keepends=True)
    )


def build_normalized_diff(
    before: dict[str, bytes],
    after: dict[str, bytes],
) -> str:
    sections: list[str] = []

    for path in sorted(set(before) | set(after)):
        old = before.get(path)
        new = after.get(path)

        if old == new:
            continue

        diff = difflib.unified_diff(
            decode_for_diff(old),
            decode_for_diff(new),
            fromfile=f"a/{path}",
            tofile=f"b/{path}",
            lineterm="\n",
        )

        sections.extend(diff)

    return "".join(sections)


def diff_hash(
    diff: str,
) -> str:
    return hashlib.sha256(
        diff.encode("utf-8")
    ).hexdigest()


def run_hidden_python_oracle(
    root: Path,
    source: str,
) -> OracleResult:
    workspace = Workspace(root)
    backend = BubblewrapExecutionBackend()

    command = [
        sys.executable,
        "-c",
        (
            "import sys\n"
            "sys.path.insert(0, '/workspace/src')\n"
            + source
        ),
    ]

    try:
        result = backend.run(
            command,
            workspace=workspace,
            timeout_seconds=10.0,
        )
    except ExecutionError as exc:
        return OracleResult(
            passed=False,
            detail=(
                "oracle_execution_error="
                f"{type(exc).__name__}: {exc}"
            ),
        )

    stdout = result.stdout.strip()
    stderr = result.stderr.strip()

    if result.returncode != 0:
        return OracleResult(
            passed=False,
            detail=(
                f"oracle_returncode={result.returncode}; "
                f"stdout={stdout!r}; "
                f"stderr={stderr!r}"
            ),
        )

    try:
        payload = json.loads(stdout)
    except json.JSONDecodeError as exc:
        return OracleResult(
            passed=False,
            detail=(
                "oracle_output_error="
                f"{type(exc).__name__}: {exc}; "
                f"stdout={stdout!r}"
            ),
        )

    passed = payload.get("passed")
    detail = payload.get("detail")

    if not isinstance(passed, bool):
        return OracleResult(
            passed=False,
            detail=(
                "oracle_output_error="
                "missing boolean 'passed'"
            ),
        )

    if not isinstance(detail, str):
        return OracleResult(
            passed=False,
            detail=(
                "oracle_output_error="
                "missing string 'detail'"
            ),
        )

    return OracleResult(
        passed=passed,
        detail=detail,
    )


def evaluate_task_oracle(
    task_id: str,
    root: Path,
) -> OracleResult:
    if task_id == "stability-001":
        return run_hidden_python_oracle(
            root,
            """
import json
from sample.greeting import greeting

observed = greeting()
expected = "hi"

print(json.dumps({
    "passed": observed == expected,
    "detail": (
        f"greeting()={observed!r}; "
        f"expected={expected!r}"
    ),
}))
""",
        )

    if task_id == "stability-002":
        return run_hidden_python_oracle(
            root,
            """
import json
from sample.client import request_policy
from sample.settings import DEFAULT_RETRIES

observed_setting = DEFAULT_RETRIES
observed_policy = request_policy()

passed = (
    observed_setting == 4
    and observed_policy == 4
)

print(json.dumps({
    "passed": passed,
    "detail": (
        f"DEFAULT_RETRIES={observed_setting!r}; "
        f"request_policy()={observed_policy!r}"
    ),
}))
""",
        )

    if task_id == "stability-003":
        return run_hidden_python_oracle(
            root,
            """
import json
from sample.normalization import normalize_name

observed = [
    normalize_name(" Alice "),
    normalize_name(" BOB "),
    normalize_name("   "),
]
expected = [
    "alice",
    "bob",
    None,
]

print(json.dumps({
    "passed": observed == expected,
    "detail": (
        f"observed={observed!r}; "
        f"expected={expected!r}"
    ),
}))
""",
        )

    raise ValueError(
        f"Unknown 013B task: {task_id}"
    )


def evaluate_regression_oracle(
    task_id: str,
    root: Path,
) -> OracleResult:
    if task_id == "stability-001":
        module = "sample.greeting"
    elif task_id == "stability-002":
        module = "sample.client"
    elif task_id == "stability-003":
        module = "sample.normalization"
    else:
        raise ValueError(
            f"Unknown 013B task: {task_id}"
        )

    return run_hidden_python_oracle(
        root,
        f"""
import json
from {module} import stable_identifier

observed = stable_identifier("Alice")
expected = "user:Alice"

print(json.dumps({{
    "passed": observed == expected,
    "detail": (
        f"stable_identifier('Alice')={{observed!r}}; "
        f"expected={{expected!r}}"
    ),
}}))
""",
    )


def evaluate_structural_oracle(
    task_id: str,
    root: Path,
) -> OracleResult | None:
    if task_id != "stability-002":
        return None

    source = (
        root / "src/sample/client.py"
    ).read_text(encoding="utf-8")

    expected_import = (
        "from sample.settings import DEFAULT_RETRIES"
    )

    return OracleResult(
        passed=expected_import in source,
        detail=(
            "client.py imports DEFAULT_RETRIES "
            "from sample.settings"
            if expected_import in source
            else (
                "client.py no longer imports DEFAULT_RETRIES "
                "from sample.settings"
            )
        ),
    )


def build_session(
    root: Path,
    *,
    mutation_required: bool,
) -> tuple[
    HewnSession,
    RecordingModel,
    RecordingToolExecutor,
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

    recording_executor = RecordingToolExecutor(
        registry,
        authority_policy=authority_policy,
    )

    policy_probe = CompletionPolicyProbe()

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
        prefix=f"hewn-013b-{task_id}-"
    ) as temporary:
        root = Path(temporary) / "repo"

        shutil.copytree(
            source_fixture,
            root,
        )

        before = snapshot_files(root)

        intervention_eligible = (
            task_id in INTERVENTION_ELIGIBLE_TASKS
        )

        (
            session,
            recording_model,
            recording_executor,
            policy_probe,
        ) = build_session(
            root,
            mutation_required=intervention_eligible,
        )

        # Prepare retrieval exactly once. Do not call session.run(),
        # because session.run() would prepare context internally.
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

        intervention_delivered = (
            completion_policy.intervention_delivered
        )

        edit_attempted_after_intervention = (
            intervention_delivered
            and completion_policy.edit_attempted
        )

        after = snapshot_files(root)

        changed = changed_files(
            before,
            after,
        )

        normalized_diff = build_normalized_diff(
            before,
            after,
        )

        task_oracle = evaluate_task_oracle(
            task_id,
            root,
        )

        regression_oracle = (
            evaluate_regression_oracle(
                task_id,
                root,
            )
        )

        structural_oracle = (
            evaluate_structural_oracle(
                task_id,
                root,
            )
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
            intervention_eligible=(
                intervention_eligible
            ),
            intervention_delivered=(
                intervention_delivered
            ),
            edit_attempted_after_intervention=(
                edit_attempted_after_intervention
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
            successful_edit_applications=sum(
                call.ok
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
        runs_producing_edits=sum(
            bool(run.changed_files)
            for run in runs
        ),
        intervention_eligible_runs=sum(
            run.intervention_eligible
            for run in runs
        ),
        intervention_delivered_runs=sum(
            run.intervention_delivered
            for run in runs
        ),
        edit_after_intervention_runs=sum(
            run.edit_attempted_after_intervention
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
        f"edits={result.successful_edit_applications}/"
        f"{result.edit_attempts} "
        f"checks={result.execution_calls} "
        f"time={result.wall_time_seconds:.2f}s"
    )

    print(
        "  intervention="
        f"eligible:{result.intervention_eligible} "
        f"delivered:{result.intervention_delivered} "
        "edit_after_intervention:"
        f"{result.edit_attempted_after_intervention}"
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
        "runs producing edits: "
        f"{aggregate.runs_producing_edits}/"
        f"{aggregate.repetitions}"
    )

    print(
        "intervention eligible: "
        f"{aggregate.intervention_eligible_runs}/"
        f"{aggregate.repetitions}"
    )

    print(
        "intervention delivered: "
        f"{aggregate.intervention_delivered_runs}/"
        f"{aggregate.repetitions}"
    )

    print(
        "edit after intervention: "
        f"{aggregate.edit_after_intervention_runs}/"
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
            "Run Module 13 premature-completion intervention "
            "experiment."
        )
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help=(
            "Validate frozen fixtures and manifest without "
            "invoking the coding model."
        ),
    )

    return parser.parse_args()


def validate_fixture(
    task: dict[str, Any],
) -> None:
    task_id = str(task["task_id"])

    fixture = (
        FIXTURES_ROOT / str(task["fixture"])
    )

    if not fixture.is_dir():
        raise FileNotFoundError(
            f"Missing fixture for {task_id}: {fixture}"
        )

    request = task.get("request")

    expected = task.get(
        "expected_changed_files"
    )

    if (
        not isinstance(request, str)
        or not request.strip()
    ):
        raise ValueError(
            f"{task_id} has invalid request"
        )

    if (
        not isinstance(expected, list)
        or not expected
        or not all(
            isinstance(item, str)
            for item in expected
        )
    ):
        raise ValueError(
            f"{task_id} has invalid "
            "expected_changed_files"
        )

    before = snapshot_files(
        fixture
    )

    if not before:
        raise ValueError(
            f"{task_id} fixture is empty"
        )


def main() -> None:
    args = parse_args()

    tasks = load_manifest()

    for task in tasks:
        validate_fixture(task)

    if args.dry_run:
        eligible = sum(
            str(task["task_id"])
            in INTERVENTION_ELIGIBLE_TASKS
            for task in tasks
        )

        print(
            "013B-1 dry run passed: "
            f"{len(tasks)} frozen tasks, "
            f"{eligible} intervention-eligible tasks, "
            f"{REPETITIONS} repetitions each, "
            f"{len(tasks) * REPETITIONS} "
            "planned runs."
        )
        return

    RESULTS_ROOT.mkdir(
        parents=True,
        exist_ok=True,
    )

    results: list[RunResult] = []

    print(
        "===== 013B-1 COMPLETION INTERVENTION ====="
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

    aggregates: list[
        TaskAggregate
    ] = []

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

    overall_runs = len(
        results
    )

    overall_behavioral_successes = sum(
        result.behavioral_success
        for result in results
    )

    overall_protocol_valid_runs = sum(
        result.protocol_valid
        for result in results
    )

    overall_runs_producing_edits = sum(
        bool(result.changed_files)
        for result in results
    )

    overall_intervention_eligible = sum(
        result.intervention_eligible
        for result in results
    )

    overall_intervention_delivered = sum(
        result.intervention_delivered
        for result in results
    )

    overall_edit_after_intervention = sum(
        result.edit_attempted_after_intervention
        for result in results
    )

    payload: dict[str, Any] = {
        "experiment": "013B-1",
        "run": "run001",
        "model": CODING_MODEL,
        "embedding_model": (
            DEFAULT_EMBEDDING_MODEL
        ),
        "repetitions_per_task": (
            REPETITIONS
        ),
        "max_turns": MAX_TURNS,
        "completion_requirement": (
            "VERIFIED"
        ),
        "intervention": {
            "name": (
                "mutation-aware completion feedback"
            ),
            "feedback": MUTATION_FEEDBACK,
            "eligible_tasks": sorted(
                INTERVENTION_ELIGIBLE_TASKS
            ),
            "ineligible_negative_control": (
                "stability-001"
            ),
            "bounded_feedback_count": 1,
            "edit_attempt_definition": (
                "any replace_text tool call, "
                "regardless of application success"
            ),
            "baseline_completion_requirement": (
                "VERIFIED"
            ),
        },
        "model_configuration": {
            "temperature": 0.0,
            "context_window": 4096,
            "llama_cpp_threads": 4,
            "endpoint": (
                "http://127.0.0.1:8080"
            ),
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
            "runs_producing_edits": (
                overall_runs_producing_edits
            ),
            "intervention_eligible_runs": (
                overall_intervention_eligible
            ),
            "intervention_delivered_runs": (
                overall_intervention_delivered
            ),
            "edit_after_intervention_runs": (
                overall_edit_after_intervention
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
        "\n===== 013B-1 AGGREGATE ====="
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
        "runs producing edits: "
        f"{overall_runs_producing_edits}/"
        f"{overall_runs}"
    )

    print(
        "intervention eligible: "
        f"{overall_intervention_eligible}/"
        f"{overall_runs}"
    )

    print(
        "intervention delivered: "
        f"{overall_intervention_delivered}/"
        f"{overall_runs}"
    )

    print(
        "edit after intervention: "
        f"{overall_edit_after_intervention}/"
        f"{overall_runs}"
    )

    print(
        f"\nWrote results to {OUTPUT_PATH}"
    )


if __name__ == "__main__":
    main()