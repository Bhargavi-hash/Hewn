from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from hewn.agent import Agent
from hewn.authority import AuthorityGrant, AuthorityPolicy
from hewn.builtin_tools import make_builtin_tool_registry
from hewn.completion import CompletionRequirement
from hewn.context.builder import ContextBuilder
from hewn.llama_cpp import LlamaCppModel
from hewn.repository.index import RepositoryIndex
from hewn.retrieval.semantic_index import SemanticIndex
from hewn.retrieval.sentence_transformer import (
    SentenceTransformerEmbeddingModel,
)
from hewn.retrieval.symbol_documents import build_symbol_documents
from hewn.session import HewnSession
from hewn.tools import ToolCall, ToolExecutor, ToolResult
from hewn.workspace import Workspace

MODULE_ROOT = Path(__file__).resolve().parent
FIXTURES_ROOT = MODULE_ROOT / "fixtures"
MANIFEST_PATH = FIXTURES_ROOT / "manifest.json"
RESULTS_ROOT = MODULE_ROOT / "results"

DEFAULT_EMBEDDING_MODEL = "BAAI/bge-small-en-v1.5"

DISCOVERY_TOOLS = {
    "list_directory",
    "read_file",
    "search_text",
    "find_symbol",
    "repository_map",
}


@dataclass(frozen=True)
class RecordedToolCall:
    name: str
    arguments: dict[str, Any]
    ok: bool
    evidence_paths: tuple[str, ...]


@dataclass(frozen=True)
class VerificationResult:
    passed: bool
    detail: str


@dataclass(frozen=True)
class TaskResult:
    task_id: str
    request: str
    agent_text: str
    model_calls: int
    tool_calls: int
    successful_tool_calls: int
    failed_tool_calls: int
    context_paths: tuple[str, ...]
    active_evidence_paths: tuple[str, ...]
    all_evidence_paths: tuple[str, ...]
    discovery_calls: tuple[RecordedToolCall, ...]
    changed_files: tuple[str, ...]
    required_file_recall: float
    allowed_file_precision: float
    behavior_passed: bool
    behavior_detail: str


@dataclass(frozen=True)
class PairResult:
    pair_id: str
    task_1: TaskResult
    task_2: TaskResult
    reusable_files: tuple[str, ...]
    task_1_reusable_evidence: tuple[str, ...]
    task_2_reusable_evidence: tuple[str, ...]
    rediscovered_reusable_files: tuple[str, ...]
    task_2_reusable_overlap_ratio: float
    repeated_discovery_operations: int


class RecordingToolExecutor(ToolExecutor):
    def __init__(
        self,
        registry: Any,
        *,
        authority_policy: AuthorityPolicy,
        workspace_root: Path,
    ) -> None:
        super().__init__(
            registry,
            authority_policy=authority_policy,
        )
        self.workspace_root = workspace_root.resolve()
        self.calls: list[RecordedToolCall] = []

    def execute(self, call: ToolCall) -> ToolResult:
        result = super().execute(call)

        paths: tuple[str, ...] = ()

        if call.name in DISCOVERY_TOOLS:
            paths = tuple(
                sorted(
                    infer_evidence_paths(
                        call=call,
                        result=result,
                        workspace_root=self.workspace_root,
                    )
                )
            )

        self.calls.append(
            RecordedToolCall(
                name=call.name,
                arguments=dict(call.arguments),
                ok=result.ok,
                evidence_paths=paths,
            )
        )

        return result


def normalize_repository_path(
    path: Path,
    root: Path,
) -> str | None:
    try:
        relative = path.resolve().relative_to(
            root.resolve()
        )
    except ValueError:
        return None

    return relative.as_posix()

def infer_evidence_paths(
    *,
    call: ToolCall,
    result: ToolResult,
    workspace_root: Path,
) -> set[str]:
    paths: set[str] = set()

    if not result.ok:
        return paths

    if call.name == "read_file":
        raw = call.arguments.get("path")

        if isinstance(raw, str):
            resolved = workspace_root / raw
            normalized = normalize_repository_path(
                resolved,
                workspace_root,
            )

            if normalized is not None:
                paths.add(normalized)

        return paths

    if call.name == "search_text":
        if result.output is None:
            return paths

        requested = call.arguments.get(
            "path",
            ".",
        )

        if not isinstance(requested, str):
            requested = "."

        search_root = (
            workspace_root / requested
        ).resolve()

        for line in result.output.splitlines():
            if line.startswith("... "):
                continue

            match_path, separator, _ = (
                line.partition(":")
            )

            if not separator or not match_path:
                continue

            candidate = search_root / match_path

            normalized = normalize_repository_path(
                candidate,
                workspace_root,
            )

            if normalized is not None:
                paths.add(normalized)

        return paths

    # find_symbol and repository_map return textual repository
    # information, but their current output formats are intentionally
    # not parsed here. Context-path and direct filesystem/search
    # evidence remain mechanically attributable.
    #
    # list_directory reveals names rather than file contents, so it is
    # retained as a discovery operation but does not count as file
    # evidence until a later operation identifies a concrete file.

    return paths


def snapshot_files(
    root: Path,
) -> dict[str, bytes]:
    snapshot: dict[str, bytes] = {}

    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue

        relative = (
            path.relative_to(root).as_posix()
        )

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
    all_paths = set(before) | set(after)

    return tuple(
        sorted(
            path
            for path in all_paths
            if before.get(path) != after.get(path)
        )
    )


def file_scope_metrics(
    *,
    changed: tuple[str, ...],
    required: list[str],
    allowed: list[str],
) -> tuple[float, float]:
    changed_set = set(changed)
    required_set = set(required)
    allowed_set = set(allowed)

    if required_set:
        recall = len(
            changed_set & required_set
        ) / len(required_set)
    else:
        recall = 1.0

    if changed_set:
        precision = len(
            changed_set & allowed_set
        ) / len(changed_set)
    else:
        precision = 1.0

    return recall, precision


def run_python_oracle(
    root: Path,
    code: str,
) -> VerificationResult:
    completed = subprocess.run(
        ["python", "-c", code],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )

    if completed.returncode == 0:
        return VerificationResult(
            passed=True,
            detail="behavior oracle passed",
        )

    detail = (
        completed.stderr.strip()
        or completed.stdout.strip()
        or f"oracle exited {completed.returncode}"
    )

    return VerificationResult(
        passed=False,
        detail=detail,
    )


def verify_behavior(
    root: Path,
    task_id: str,
) -> VerificationResult:
    env_prefix = (
        "import sys; "
        "sys.path.insert(0, 'src'); "
    )

    oracles = {
        "config-001": (
            env_prefix
            + "from sample.client import request_policy; "
            + "assert request_policy() == (4, 5)"
        ),
        "config-002": (
            env_prefix
            + "from sample.client import request_policy; "
            + "assert request_policy() == (4, 10)"
        ),
        "serialization-001": (
            env_prefix
            + "from sample.serializer import serialize_user; "
            + "assert serialize_user(7) == {'account_id': 7}"
        ),
        "serialization-002": (
            env_prefix
            + "from sample.serializer import serialize_user; "
            + "assert serialize_user(7, True) == "
            + "{'account_id': 7, 'active': True}; "
            + "assert serialize_user(9, False) == "
            + "{'account_id': 9, 'active': False}"
        ),
        "parser-001": (
            env_prefix
            + "from sample.parser import normalize_value; "
            + "assert normalize_value('  Alpha  ') == 'alpha'; "
            + "assert normalize_value('BETA') == 'beta'"
        ),
        "parser-002": (
            env_prefix
            + "from sample.parser import normalize_value; "
            + "assert normalize_value('   ') is None; "
            + "assert normalize_value('  Alpha  ') == 'alpha'"
        ),
    }

    code = oracles.get(task_id)

    if code is None:
        raise ValueError(
            f"No behavior oracle for task: {task_id}"
        )

    return run_python_oracle(
        root,
        code,
    )


def build_session(
    *,
    root: Path,
    embedding_model: SentenceTransformerEmbeddingModel,
    model: LlamaCppModel,
) -> tuple[HewnSession, RecordingToolExecutor]:
    repository_index = RepositoryIndex.build(root)

    documents = build_symbol_documents(
        repository_index
    )

    semantic_index = SemanticIndex.build(
        documents,
        model=embedding_model,
    )

    workspace = Workspace(root)

    registry = make_builtin_tool_registry(
        workspace,
        repository_index,
    )

    authority_policy = AuthorityPolicy(
        AuthorityGrant(
            repository_read=True,
            repository_write=True,
            approved_checks=True,
        )
    )

    executor = RecordingToolExecutor(
        registry,
        authority_policy=authority_policy,
        workspace_root=root,
    )

    agent = Agent(
        model=model,
        registry=registry,
        executor=executor,
    )

    context_builder = ContextBuilder(
        repository_root=root,
        repository_index=repository_index,
    )

    session = HewnSession(
        agent=agent,
        repository_index=repository_index,
        semantic_index=semantic_index,
        embedding_model=embedding_model,
        context_builder=context_builder,
    )

    return session, executor


def context_paths(
    session: HewnSession,
    request: str,
) -> tuple[str, ...]:
    prepared = session.prepare_context(request)

    return tuple(
        sorted(
            {
                str(
                    evidence
                    .retrieval_result
                    .document
                    .path
                )
                for evidence in prepared.context.evidence
            }
        )
    )


def execute_task(
    *,
    root: Path,
    task: dict[str, Any],
    embedding_model: SentenceTransformerEmbeddingModel,
    model: LlamaCppModel,
) -> TaskResult:
    session, executor = build_session(
        root=root,
        embedding_model=embedding_model,
        model=model,
    )

    initial_context_paths = context_paths(
        session,
        task["request"],
    )

    before = snapshot_files(root)

    result = session.run(
        task["request"],
        completion_requirement=(
            CompletionRequirement.NONE
        ),
    )

    after = snapshot_files(root)

    changed = changed_files(
        before,
        after,
    )

    recall, precision = file_scope_metrics(
        changed=changed,
        required=task[
            "required_changed_files"
        ],
        allowed=task[
            "allowed_changed_files"
        ],
    )

    verification = verify_behavior(
        root,
        task["id"],
    )

    discovery_calls = tuple(
        call
        for call in executor.calls
        if call.name in DISCOVERY_TOOLS
    )

    active_paths = tuple(
        sorted(
            {
                path
                for call in discovery_calls
                for path in call.evidence_paths
            }
        )
    )

    all_paths = tuple(
        sorted(
            set(initial_context_paths)
            | set(active_paths)
        )
    )

    return TaskResult(
        task_id=task["id"],
        request=task["request"],
        agent_text=result.text,
        model_calls=result.metrics.model_calls,
        tool_calls=result.metrics.tool_calls,
        successful_tool_calls=(
            result.metrics.successful_tool_calls
        ),
        failed_tool_calls=(
            result.metrics.failed_tool_calls
        ),
        context_paths=initial_context_paths,
        active_evidence_paths=active_paths,
        all_evidence_paths=all_paths,
        discovery_calls=discovery_calls,
        changed_files=changed,
        required_file_recall=recall,
        allowed_file_precision=precision,
        behavior_passed=verification.passed,
        behavior_detail=verification.detail,
    )


def repeated_discovery_operation_count(
    task_1: TaskResult,
    task_2: TaskResult,
    reusable_files: set[str],
) -> int:
    task_1_paths = (
        set(task_1.all_evidence_paths)
        & reusable_files
    )

    count = 0

    for call in task_2.discovery_calls:
        if (
            set(call.evidence_paths)
            & task_1_paths
        ):
            count += 1

    return count


def evaluate_pair(
    *,
    pair: dict[str, Any],
    fixture_source: Path,
    embedding_model: SentenceTransformerEmbeddingModel,
    model: LlamaCppModel,
) -> PairResult:
    with tempfile.TemporaryDirectory(
        prefix=f"hewn-010a-{pair['id']}-"
    ) as temporary:
        root = Path(temporary) / "repo"

        shutil.copytree(
            fixture_source,
            root,
        )

        task_1_definition = pair["tasks"][0]
        task_2_definition = pair["tasks"][1]

        task_1 = execute_task(
            root=root,
            task=task_1_definition,
            embedding_model=embedding_model,
            model=model,
        )

        # Task 2 intentionally starts from the repository state
        # produced by task 1. execute_task() rebuilds all repository
        # and semantic indexes, preventing stale retrieval state.
        task_2 = execute_task(
            root=root,
            task=task_2_definition,
            embedding_model=embedding_model,
            model=model,
        )

        reusable_files = set(
            task_1_definition["reusable_files"]
        ) & set(
            task_2_definition["reusable_files"]
        )

        task_1_reusable = (
            set(task_1.all_evidence_paths)
            & reusable_files
        )

        task_2_reusable = (
            set(task_2.all_evidence_paths)
            & reusable_files
        )

        rediscovered = (
            task_1_reusable
            & task_2_reusable
        )

        if task_2_reusable:
            overlap_ratio = (
                len(rediscovered)
                / len(task_2_reusable)
            )
        else:
            overlap_ratio = 0.0

        return PairResult(
            pair_id=pair["id"],
            task_1=task_1,
            task_2=task_2,
            reusable_files=tuple(
                sorted(reusable_files)
            ),
            task_1_reusable_evidence=tuple(
                sorted(task_1_reusable)
            ),
            task_2_reusable_evidence=tuple(
                sorted(task_2_reusable)
            ),
            rediscovered_reusable_files=tuple(
                sorted(rediscovered)
            ),
            task_2_reusable_overlap_ratio=(
                overlap_ratio
            ),
            repeated_discovery_operations=(
                repeated_discovery_operation_count(
                    task_1,
                    task_2,
                    reusable_files,
                )
            ),
        )


def load_manifest() -> dict[str, Any]:
    payload: Any = json.loads(
        MANIFEST_PATH.read_text(
            encoding="utf-8"
        )
    )

    if not isinstance(payload, dict):
        raise TypeError(
            "010A manifest root must be an object"
        )

    return payload

def validate_manifest(
    manifest: dict[str, Any],
) -> None:
    if manifest.get("experiment") != "010A":
        raise ValueError(
            "Manifest is not the frozen 010A corpus"
        )

    pairs = manifest.get("pairs")

    if not isinstance(pairs, list):
        raise TypeError(
            "Manifest pairs must be a list"
        )

    if len(pairs) != 3:
        raise ValueError(
            "010A expects exactly three task pairs"
        )

    task_ids: list[str] = []

    for pair in pairs:
        tasks = pair.get("tasks")

        if (
            not isinstance(tasks, list)
            or len(tasks) != 2
        ):
            raise ValueError(
                "Every 010A pair must contain "
                "exactly two tasks"
            )

        task_ids.extend(
            task["id"]
            for task in tasks
        )

    if len(set(task_ids)) != 6:
        raise ValueError(
            "010A expects six unique task IDs"
        )


def print_summary(
    results: list[PairResult],
) -> None:
    print("\n===== 010A SUMMARY =====")

    total_behavior = 0
    total_tasks = 0
    total_rediscovered = 0
    total_t2_reusable = 0
    repeated_operations = 0

    for pair in results:
        print(f"\n[{pair.pair_id}]")

        for task in (
            pair.task_1,
            pair.task_2,
        ):
            total_tasks += 1
            total_behavior += int(
                task.behavior_passed
            )

            print(
                f"{task.task_id}: "
                f"behavior={task.behavior_passed} "
                f"model_calls={task.model_calls} "
                f"tool_calls={task.tool_calls} "
                f"context={list(task.context_paths)} "
                f"active={list(task.active_evidence_paths)}"
            )

        rediscovered_count = len(
            pair.rediscovered_reusable_files
        )

        t2_count = len(
            pair.task_2_reusable_evidence
        )

        total_rediscovered += rediscovered_count
        total_t2_reusable += t2_count
        repeated_operations += (
            pair.repeated_discovery_operations
        )

        print(
            "rediscovered="
            f"{list(pair.rediscovered_reusable_files)}"
        )
        print(
            "T2 reusable overlap="
            f"{pair.task_2_reusable_overlap_ratio:.3f}"
        )
        print(
            "repeated discovery operations="
            f"{pair.repeated_discovery_operations}"
        )

    aggregate_overlap = (
        total_rediscovered / total_t2_reusable
        if total_t2_reusable
        else 0.0
    )

    print("\n===== AGGREGATE =====")
    print(
        f"behavioral success: "
        f"{total_behavior}/{total_tasks}"
    )
    print(
        "rediscovered reusable files: "
        f"{total_rediscovered}/"
        f"{total_t2_reusable}"
    )
    print(
        f"aggregate T2 overlap: "
        f"{aggregate_overlap:.3f}"
    )
    print(
        "repeated discovery operations: "
        f"{repeated_operations}"
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--embedding-model",
        default=DEFAULT_EMBEDDING_MODEL,
    )

    parser.add_argument(
        "--base-url",
        default="http://127.0.0.1:8080",
    )

    parser.add_argument(
        "--output",
        type=Path,
        default=(
            RESULTS_ROOT
            / "010a-repeated-discovery-run001.json"
        ),
    )

    return parser.parse_args()


def main() -> None:
    args = parse_args()

    manifest = load_manifest()
    validate_manifest(manifest)

    embedding_model = (
        SentenceTransformerEmbeddingModel(
            args.embedding_model
        )
    )

    model = LlamaCppModel(
        base_url=args.base_url,
        temperature=0.0,
        max_tokens=256,
        timeout_seconds=120.0,
    )

    results: list[PairResult] = []

    for pair in manifest["pairs"]:
        fixture_source = (
            FIXTURES_ROOT / pair["fixture"]
        )

        results.append(
            evaluate_pair(
                pair=pair,
                fixture_source=fixture_source,
                embedding_model=embedding_model,
                model=model,
            )
        )

    args.output.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    payload = {
        "experiment": "010A",
        "run": "run001",
        "embedding_model": args.embedding_model,
        "model": {
            "provider": "llama.cpp",
            "temperature": 0.0,
            "max_tokens": 256,
        },
        "pairs": [
            asdict(result)
            for result in results
        ],
    }

    args.output.write_text(
        json.dumps(
            payload,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    print_summary(results)

    print(
        f"\nWrote results to {args.output}"
    )


if __name__ == "__main__":
    main()