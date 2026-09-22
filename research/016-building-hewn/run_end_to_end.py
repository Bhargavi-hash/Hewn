from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from collections.abc import Mapping
from dataclasses import asdict, dataclass
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
from hewn.completion import CompletionRequirement
from hewn.context.builder import ContextBuilder
from hewn.execution import BubblewrapExecutionBackend
from hewn.llama_cpp import LlamaCppModel
from hewn.repository.index import RepositoryIndex
from hewn.retrieval.semantic_index import SemanticIndex

# from hewn.retrieval.sentence_transformer import (
#     SentenceTransformerEmbeddingModel,
# )
from hewn.retrieval.symbol_documents import (
    build_symbol_documents,
)
from hewn.session import HewnSession
from hewn.telemetry import AgentMetrics
from hewn.tools import ToolExecutor
from hewn.workspace import Workspace

MODULE_ROOT = Path("research/016-building-hewn")
CASES_PATH = MODULE_ROOT / "data/end_to_end/cases.jsonl"
FIXTURES_ROOT = MODULE_ROOT / "fixtures"

DEFAULT_OUTPUT = (
    MODULE_ROOT
    / "results"
    / "end_to_end_run.json"
)

EMBEDDING_MODEL = "BAAI/bge-small-en-v1.5"
FROZEN_BENCHMARK_COMMIT = "851de9e"

MODEL_ID = "Qwen2.5-Coder-0.5B-Instruct"
MAX_TURNS = 12


@dataclass(frozen=True)
class OracleResult:
    passed: bool
    returncode: int
    stdout: str
    stderr: str


@dataclass(frozen=True)
class ProtocolCounts:
    canonical: int
    normalized: int
    normalization_rules: Mapping[str, int]


@dataclass(frozen=True)
class TaskResult:
    task_id: str
    family: str
    fixture: str
    terminal_status: str
    terminal_error: str | None
    final_text: str | None

    task_passes: bool
    regression_passes: bool
    behavioral_success: bool

    expected_changed_files: tuple[str, ...]
    changed_files: tuple[str, ...]
    expected_changes_satisfied: bool
    unnecessary_changed_files: tuple[str, ...]

    model_calls: int
    tool_calls: int
    successful_tool_calls: int
    failed_tool_calls: int
    execution_calls: int

    context_chars: int
    context_evidence_count: int
    wall_time_seconds: float

    canonical_model_responses: int
    normalized_model_responses: int
    normalization_rules: Mapping[str, int]

    behavioral_oracle: OracleResult
    regression_oracle: OracleResult

    events: tuple[dict[str, str], ...]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run the frozen Module 16 Hewn end-to-end benchmark."
        )
    )

    parser.add_argument(
        "--task",
        help=(
            "Run one frozen task ID. "
            "Omit to run the full frozen benchmark."
        ),
    )

    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
    )

    parser.add_argument(
        "--base-url",
        default="http://127.0.0.1:8080",
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help=(
            "Validate benchmark and construction without "
            "calling the coding model."
        ),
    )

    return parser.parse_args()


def load_cases() -> list[dict[str, Any]]:
    cases: list[dict[str, Any]] = []

    for line in CASES_PATH.read_text(
        encoding="utf-8"
    ).splitlines():
        if line.strip():
            value: Any = json.loads(line)

            if not isinstance(value, dict):
                raise ValueError(
                    "Benchmark case must be a JSON object"
                )

            cases.append(value)

    return cases


def git_output(*args: str) -> str:
    completed = subprocess.run(
        ["git", *args],
        capture_output=True,
        text=True,
        check=True,
    )
    return completed.stdout.strip()


def current_commit() -> str:
    return git_output("rev-parse", "HEAD")


def snapshot_files(
    root: Path,
) -> dict[str, str]:
    snapshot: dict[str, str] = {}

    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue

        relative = path.relative_to(root)

        if "__pycache__" in relative.parts:
            continue

        if relative.suffix in {
            ".pyc",
            ".pyo",
        }:
            continue

        digest = hashlib.sha256(
            path.read_bytes()
        ).hexdigest()

        snapshot[str(relative)] = digest

    return snapshot


def changed_files(
    before: Mapping[str, str],
    after: Mapping[str, str],
) -> tuple[str, ...]:
    paths = set(before) | set(after)

    return tuple(
        sorted(
            path
            for path in paths
            if before.get(path) != after.get(path)
        )
    )


def run_pytest(
    repository: Path,
    target: Path | None = None,
) -> OracleResult:
    env = dict(os.environ)

    source = repository / "src"

    existing = env.get("PYTHONPATH")

    if existing:
        env["PYTHONPATH"] = (
            f"{source}{os.pathsep}{existing}"
        )
    else:
        env["PYTHONPATH"] = str(source)

    command = [
        sys.executable,
        "-m",
        "pytest",
        "-q",
    ]

    if target is not None:
        command.append(str(target))

    completed = subprocess.run(
        command,
        cwd=repository,
        env=env,
        capture_output=True,
        text=True,
        check=False,
        timeout=60.0,
    )

    return OracleResult(
        passed=completed.returncode == 0,
        returncode=completed.returncode,
        stdout=completed.stdout,
        stderr=completed.stderr,
    )


def run_behavioral_oracle(
    fixture_root: Path,
    repository: Path,
) -> OracleResult:
    evaluator = (
        fixture_root
        / "evaluator"
        / "test_task.py"
    )

    if not evaluator.is_file():
        raise FileNotFoundError(
            f"Missing hidden evaluator: {evaluator}"
        )

    return run_pytest(
        repository,
        evaluator.resolve(),
    )


def run_regression_oracle(
    repository: Path,
) -> OracleResult:
    return run_pytest(repository)


def count_protocol_events(
    metrics: AgentMetrics,
) -> ProtocolCounts:
    canonical = 0
    normalized = 0
    rules: dict[str, int] = {}

    for event in metrics.events:
        if event.kind != "model_protocol":
            continue

        if event.detail == "canonical":
            canonical += 1
            continue

        prefix = "normalized:"

        if event.detail.startswith(prefix):
            normalized += 1
            rule = event.detail[len(prefix):]

            rules[rule] = rules.get(rule, 0) + 1

    return ProtocolCounts(
        canonical=canonical,
        normalized=normalized,
        normalization_rules=dict(
            sorted(rules.items())
        ),
    )


def count_execution_calls(
    metrics: AgentMetrics,
) -> int:
    return sum(
        1
        for event in metrics.events
        if (
            event.kind == "tool_call"
            and "run_check" in event.detail
        )
    )


def build_session(
    root: Path,
    *,
    base_url: str,
) -> HewnSession:

    from hewn.retrieval.sentence_transformer import (
        SentenceTransformerEmbeddingModel,
    )
    workspace = Workspace(root)

    repository_index = RepositoryIndex.build(
        root
    )

    embedding_model = (
        SentenceTransformerEmbeddingModel(
            EMBEDDING_MODEL
        )
    )

    semantic_index = SemanticIndex.build(
        build_symbol_documents(
            repository_index
        ),
        model=embedding_model,
    )

    context_builder = ContextBuilder(
        repository_root=root,
        repository_index=repository_index,
    )

    model = LlamaCppModel(
        base_url=base_url,
        temperature=0.0,
    )

    registry = make_builtin_tool_registry(
        workspace,
        repository_index,
        execution_backend=(
            BubblewrapExecutionBackend()
        ),
    )

    executor = ToolExecutor(
        registry,
        authority_policy=AuthorityPolicy(
            AuthorityGrant(
                repository_read=True,
                repository_write=True,
                approved_checks=True,
            )
        ),
    )

    agent = Agent(
        model=model,
        registry=registry,
        executor=executor,
        max_turns=MAX_TURNS,
    )

    return HewnSession(
        agent=agent,
        repository_index=repository_index,
        semantic_index=semantic_index,
        embedding_model=embedding_model,
        context_builder=context_builder,
    )


def run_one(
    case: dict[str, Any],
    *,
    base_url: str,
) -> TaskResult:
    task_id = str(case["task_id"])
    family = str(case["family"])
    fixture_name = str(case["fixture"])
    request = str(case["task_request"])

    expected_changed = tuple(
        str(path)
        for path in case[
            "expected_changed_files"
        ]
    )

    fixture_root = (
        FIXTURES_ROOT / fixture_name
    )

    source_repository = (
        fixture_root / "repository"
    )

    if not source_repository.is_dir():
        raise FileNotFoundError(
            f"Missing repository fixture: "
            f"{source_repository}"
        )

    with tempfile.TemporaryDirectory(
        prefix=f"hewn-016c-{task_id}-"
    ) as temporary:
        root = (
            Path(temporary)
            / "repository"
        )

        shutil.copytree(
            source_repository,
            root,
        )

        # The model-visible workspace contains only repository/.
        if (
            (root / "evaluator").exists()
            or (root / "reference").exists()
        ):
            raise RuntimeError(
                f"{task_id}: evaluator-only "
                "material entered the workspace"
            )

        before = snapshot_files(root)

        session = build_session(
            root,
            base_url=base_url,
        )

        # Prepare once so context resource usage can be
        # measured without repeating retrieval.
        prepared = session.prepare_context(
            request
        )

        context_chars = (
            prepared.context.character_count
        )
        context_evidence_count = (
            prepared.context.evidence_count
        )

        terminal_status = "unknown"
        terminal_error: str | None = None
        final_text: str | None = None

        metrics = AgentMetrics()

        started = perf_counter()

        try:
            result = session.agent.run(
                request,
                completion_requirement=(
                    CompletionRequirement.VERIFIED
                ),
                context=prepared.context,
            )

            final_text = result.text
            metrics = result.metrics
            terminal_status = "completed"

        except AgentLimitError as exc:
            metrics = exc.metrics
            terminal_status = "agent_limit"
            terminal_error = str(exc)

        except AgentStagnationError as exc:
            metrics = exc.metrics
            terminal_status = "stagnation"
            terminal_error = str(exc)

        except Exception as exc:  # noqa: BLE001
            terminal_status = "error"
            terminal_error = (
                f"{type(exc).__name__}: {exc}"
            )

        agent_wall_time = (
            perf_counter() - started
        )

        after = snapshot_files(root)

        changed = changed_files(
            before,
            after,
        )

        expected_changes_satisfied = (
            set(expected_changed)
            .issubset(changed)
        )

        unnecessary = tuple(
            sorted(
                set(changed)
                - set(expected_changed)
            )
        )

        # Evaluator-only checks happen only after the
        # agent has finished interacting with its workspace.
        behavioral = run_behavioral_oracle(
            fixture_root,
            root,
        )

        regression = run_regression_oracle(
            root
        )

        behavioral_success = (
            behavioral.passed
            and regression.passed
        )

        protocol = count_protocol_events(
            metrics
        )

        events = tuple(
            {
                "kind": event.kind,
                "detail": event.detail,
            }
            for event in metrics.events
        )

        return TaskResult(
            task_id=task_id,
            family=family,
            fixture=fixture_name,
            terminal_status=terminal_status,
            terminal_error=terminal_error,
            final_text=final_text,
            task_passes=behavioral.passed,
            regression_passes=regression.passed,
            behavioral_success=(
                behavioral_success
            ),
            expected_changed_files=(
                expected_changed
            ),
            changed_files=changed,
            expected_changes_satisfied=(
                expected_changes_satisfied
            ),
            unnecessary_changed_files=(
                unnecessary
            ),
            model_calls=metrics.model_calls,
            tool_calls=metrics.tool_calls,
            successful_tool_calls=(
                metrics.successful_tool_calls
            ),
            failed_tool_calls=(
                metrics.failed_tool_calls
            ),
            execution_calls=(
                count_execution_calls(metrics)
            ),
            context_chars=context_chars,
            context_evidence_count=(
                context_evidence_count
            ),
            wall_time_seconds=(
                agent_wall_time
            ),
            canonical_model_responses=(
                protocol.canonical
            ),
            normalized_model_responses=(
                protocol.normalized
            ),
            normalization_rules=(
                protocol.normalization_rules
            ),
            behavioral_oracle=behavioral,
            regression_oracle=regression,
            events=events,
        )


def validate_case(
    case: dict[str, Any],
) -> None:
    required = {
        "task_id",
        "family",
        "task_request",
        "fixture",
        "behavioral_oracle",
        "regression_oracle",
        "expected_changed_files",
    }

    missing = required - case.keys()

    if missing:
        raise ValueError(
            "Benchmark case is missing fields: "
            f"{sorted(missing)}"
        )

    fixture = (
        FIXTURES_ROOT
        / str(case["fixture"])
    )

    repository = fixture / "repository"
    evaluator = (
        fixture
        / "evaluator"
        / "test_task.py"
    )
    reference = fixture / "reference"

    if not repository.is_dir():
        raise FileNotFoundError(repository)

    if not evaluator.is_file():
        raise FileNotFoundError(evaluator)

    if not reference.is_dir():
        raise FileNotFoundError(reference)


def print_task_result(
    result: TaskResult,
) -> None:
    print(
        f"{result.task_id}: "
        f"behavioral={result.behavioral_success} "
        f"task={result.task_passes} "
        f"regression={result.regression_passes} "
        f"terminal={result.terminal_status}"
    )

    print(
        "  changed="
        f"{list(result.changed_files)}"
    )

    print(
        "  protocol="
        f"canonical:{result.canonical_model_responses} "
        f"normalized:{result.normalized_model_responses}"
    )

    print(
        "  resources="
        f"model:{result.model_calls} "
        f"tools:{result.tool_calls} "
        f"checks:{result.execution_calls} "
        f"context:{result.context_chars} "
        f"wall:{result.wall_time_seconds:.2f}s"
    )

    if result.terminal_error is not None:
        print(
            f"  error={result.terminal_error}"
        )


def main() -> None:
    args = parse_args()

    cases = load_cases()

    for case in cases:
        validate_case(case)

    if args.task is not None:
        cases = [
            case
            for case in cases
            if case["task_id"] == args.task
        ]

        if not cases:
            raise SystemExit(
                f"Unknown frozen task: {args.task}"
            )

    if args.dry_run:
        print(
            "016C dry run passed: "
            f"{len(cases)} task(s)"
        )
        print(
            "frozen benchmark commit: "
            f"{FROZEN_BENCHMARK_COMMIT}"
        )
        return

    results: list[TaskResult] = []

    for case in cases:
        task_id = str(case["task_id"])

        print(
            f"\n===== {task_id} ====="
        )

        result = run_one(
            case,
            base_url=args.base_url,
        )

        results.append(result)
        print_task_result(result)

    payload = {
        "benchmark": {
            "name": "hewn-module-16-end-to-end",
            "version": "16C-frozen-1",
            "frozen_commit": (
                FROZEN_BENCHMARK_COMMIT
            ),
        },
        "run": {
            "commit": current_commit(),
            "model_id": MODEL_ID,
            "embedding_model": EMBEDDING_MODEL,
            "temperature": 0.0,
            "max_turns": MAX_TURNS,
            "completion_requirement": "VERIFIED",
            "execution_backend": "bubblewrap",
        },
        "summary": {
            "runs": len(results),
            "behavioral_successes": sum(
                result.behavioral_success
                for result in results
            ),
            "task_passes": sum(
                result.task_passes
                for result in results
            ),
            "regression_passes": sum(
                result.regression_passes
                for result in results
            ),
            "runs_with_edits": sum(
                bool(result.changed_files)
                for result in results
            ),
            "canonical_model_responses": sum(
                result.canonical_model_responses
                for result in results
            ),
            "normalized_model_responses": sum(
                result.normalized_model_responses
                for result in results
            ),
        },
        "results": [
            asdict(result)
            for result in results
        ],
    }

    args.output.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    args.output.write_text(
        json.dumps(
            payload,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    print(
        f"\nwrote {args.output}"
    )


if __name__ == "__main__":
    main()