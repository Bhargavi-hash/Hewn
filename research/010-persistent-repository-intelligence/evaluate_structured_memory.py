from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from memory_oracle import (
    MemoryRecord,
    format_memory_records,
    records_established_by,
    relevant_record_ids,
)

from hewn.agent import Agent
from hewn.authority import AuthorityGrant, AuthorityPolicy
from hewn.builtin_tools import make_builtin_tool_registry
from hewn.completion import CompletionRequirement
from hewn.context.builder import ContextBuilder
from hewn.context.models import ContextBundle
from hewn.llama_cpp import LlamaCppModel
from hewn.model_protocol import ModelProtocolError
from hewn.models import Message, ModelResponse
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
    ToolDefinition,
    ToolExecutor,
    ToolResult,
)
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

CONDITIONS = (
    "stateless",
    "structured_memory",
)


@dataclass(frozen=True, slots=True)
class RecordedToolCall:
    name: str
    arguments: dict[str, Any]
    ok: bool
    evidence_paths: tuple[str, ...]


@dataclass
class RecordingModel:
    delegate: LlamaCppModel
    model_calls: int = 0
    protocol_failures: int = 0
    last_protocol_error: str | None = None
    last_raw_response: str | None = None

    def respond(
        self,
        messages: list[Message],
        tools: list[ToolDefinition],
    ) -> ModelResponse:
        self.model_calls += 1

        try:
            return self.delegate.respond(
                messages=messages,
                tools=tools,
            )
        except ModelProtocolError as exc:
            self.protocol_failures += 1
            self.last_protocol_error = str(exc)
            self.last_raw_response = exc.raw_response
            raise


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

        self.workspace_root = (
            workspace_root.resolve()
        )

        self.calls: list[
            RecordedToolCall
        ] = []

    def execute(
        self,
        call: ToolCall,
    ) -> ToolResult:
        result = super().execute(call)

        paths: tuple[str, ...] = ()

        if call.name in DISCOVERY_TOOLS:
            paths = tuple(
                sorted(
                    infer_evidence_paths(
                        call=call,
                        result=result,
                        workspace_root=(
                            self.workspace_root
                        ),
                    )
                )
            )

        self.calls.append(
            RecordedToolCall(
                name=call.name,
                arguments=dict(
                    call.arguments
                ),
                ok=result.ok,
                evidence_paths=paths,
            )
        )

        return result


@dataclass(frozen=True, slots=True)
class VerificationResult:
    passed: bool
    detail: str


@dataclass(frozen=True, slots=True)
class TaskResult:
    task_id: str
    condition: str
    request: str

    agent_text: str
    protocol_valid: bool
    protocol_error: str | None
    raw_protocol_response: str | None

    model_calls: int
    tool_calls: int
    successful_tool_calls: int
    failed_tool_calls: int

    current_context_paths: tuple[str, ...]
    current_context_character_count: int
    current_context_evidence_count: int

    memory_records_available: int
    memory_records_retrieved: int
    memory_records_used_in_prompt: int
    memory_record_ids: tuple[str, ...]
    memory_evidence_paths: tuple[str, ...]
    relevant_memory_records: int
    irrelevant_memory_records: int
    memory_character_count: int

    prompt_evidence_character_count: int

    active_evidence_paths: tuple[str, ...]
    all_evidence_paths: tuple[str, ...]
    discovery_calls: tuple[
        RecordedToolCall,
        ...,
    ]

    changed_files: tuple[str, ...]
    required_file_recall: float
    allowed_file_precision: float

    behavior_passed: bool
    behavior_detail: str


@dataclass(frozen=True, slots=True)
class SequenceResult:
    pair_id: str
    condition: str
    task_1: TaskResult
    task_2: TaskResult
    persisted_memory: tuple[
        MemoryRecord,
        ...,
    ]
    repeated_discovery_operations: int


@dataclass(frozen=True, slots=True)
class PairComparison:
    pair_id: str
    stateless: SequenceResult
    structured_memory: SequenceResult


def normalize_repository_path(
    path: Path,
    root: Path,
) -> str | None:
    try:
        relative = (
            path.resolve().relative_to(
                root.resolve()
            )
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
            resolved = (
                workspace_root / raw
            )

            normalized = (
                normalize_repository_path(
                    resolved,
                    workspace_root,
                )
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

        if not isinstance(
            requested,
            str,
        ):
            requested = "."

        search_root = (
            workspace_root / requested
        ).resolve()

        for line in (
            result.output.splitlines()
        ):
            if line.startswith("... "):
                continue

            match_path, separator, _ = (
                line.partition(":")
            )

            if (
                not separator
                or not match_path
            ):
                continue

            candidate = (
                search_root / match_path
            )

            normalized = (
                normalize_repository_path(
                    candidate,
                    workspace_root,
                )
            )

            if normalized is not None:
                paths.add(normalized)

        return paths

    return paths


def snapshot_files(
    root: Path,
) -> dict[str, bytes]:
    snapshot: dict[str, bytes] = {}

    for path in sorted(
        root.rglob("*")
    ):
        if not path.is_file():
            continue

        relative = (
            path.relative_to(root)
            .as_posix()
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

        snapshot[relative] = (
            path.read_bytes()
        )

    return snapshot


def changed_files(
    before: dict[str, bytes],
    after: dict[str, bytes],
) -> tuple[str, ...]:
    all_paths = (
        set(before) | set(after)
    )

    return tuple(
        sorted(
            path
            for path in all_paths
            if (
                before.get(path)
                != after.get(path)
            )
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
        recall = (
            len(
                changed_set
                & required_set
            )
            / len(required_set)
        )
    else:
        recall = 1.0

    if changed_set:
        precision = (
            len(
                changed_set
                & allowed_set
            )
            / len(changed_set)
        )
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
            detail=(
                "behavior oracle passed"
            ),
        )

    detail = (
        completed.stderr.strip()
        or completed.stdout.strip()
        or (
            "oracle exited "
            f"{completed.returncode}"
        )
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
            + (
                "from sample.client import "
                "request_policy; "
            )
            + (
                "assert request_policy() "
                "== (4, 5)"
            )
        ),
        "config-002": (
            env_prefix
            + (
                "from sample.client import "
                "request_policy; "
            )
            + (
                "assert request_policy() "
                "== (4, 10)"
            )
        ),
        "serialization-001": (
            env_prefix
            + (
                "from sample.serializer "
                "import serialize_user; "
            )
            + (
                "assert serialize_user(7) "
                "== {'account_id': 7}"
            )
        ),
        "serialization-002": (
            env_prefix
            + (
                "from sample.serializer "
                "import serialize_user; "
            )
            + (
                "assert serialize_user(7, True) "
                "== {'account_id': 7, "
                "'active': True}; "
            )
            + (
                "assert serialize_user(9, False) "
                "== {'account_id': 9, "
                "'active': False}"
            )
        ),
        "parser-001": (
            env_prefix
            + (
                "from sample.parser import "
                "normalize_value; "
            )
            + (
                "assert normalize_value"
                "('  Alpha  ') == 'alpha'; "
            )
            + (
                "assert normalize_value"
                "('BETA') == 'beta'"
            )
        ),
        "parser-002": (
            env_prefix
            + (
                "from sample.parser import "
                "normalize_value; "
            )
            + (
                "assert normalize_value"
                "('   ') is None; "
            )
            + (
                "assert normalize_value"
                "('  Alpha  ') == 'alpha'"
            )
        ),
    }

    code = oracles.get(task_id)

    if code is None:
        raise ValueError(
            "No behavior oracle for task: "
            f"{task_id}"
        )

    return run_python_oracle(
        root,
        code,
    )


def build_session(
    *,
    root: Path,
    embedding_model: (
        SentenceTransformerEmbeddingModel
    ),
    model: LlamaCppModel,
) -> tuple[
    HewnSession,
    RecordingToolExecutor,
    RecordingModel,
]:
    repository_index = (
        RepositoryIndex.build(root)
    )

    documents = (
        build_symbol_documents(
            repository_index
        )
    )

    semantic_index = (
        SemanticIndex.build(
            documents,
            model=embedding_model,
        )
    )

    workspace = Workspace(root)

    registry = (
        make_builtin_tool_registry(
            workspace,
            repository_index,
        )
    )

    authority_policy = (
        AuthorityPolicy(
            AuthorityGrant(
                repository_read=True,
                repository_write=True,
                approved_checks=True,
            )
        )
    )

    executor = RecordingToolExecutor(
        registry,
        authority_policy=(
            authority_policy
        ),
        workspace_root=root,
    )

    recording_model = RecordingModel(
        delegate=model,
    )

    agent = Agent(
        model=recording_model,
        registry=registry,
        executor=executor,
    )

    context_builder = ContextBuilder(
        repository_root=root,
        repository_index=(
            repository_index
        ),
    )

    session = HewnSession(
        agent=agent,
        repository_index=(
            repository_index
        ),
        semantic_index=semantic_index,
        embedding_model=(
            embedding_model
        ),
        context_builder=context_builder,
    )

    return (
        session,
        executor,
        recording_model,
    )


def context_paths(
    context: ContextBundle,
) -> tuple[str, ...]:
    return tuple(
        sorted(
            {
                str(
                    evidence
                    .retrieval_result
                    .document
                    .path
                )
                for evidence
                in context.evidence
            }
        )
    )


def memory_evidence_paths(
    records: tuple[
        MemoryRecord,
        ...,
    ],
) -> tuple[str, ...]:
    return tuple(
        sorted(
            {
                path
                for record in records
                for path
                in record.evidence_paths
            }
        )
    )


def repeated_discovery_operation_count(
    task_1: TaskResult,
    task_2: TaskResult,
) -> int:
    task_1_paths = set(
        task_1.all_evidence_paths
    )

    count = 0

    for call in task_2.discovery_calls:
        if (
            set(call.evidence_paths)
            & task_1_paths
        ):
            count += 1

    return count


def execute_task(
    *,
    root: Path,
    task: dict[str, Any],
    condition: str,
    available_memory: tuple[
        MemoryRecord,
        ...,
    ],
    embedding_model: (
        SentenceTransformerEmbeddingModel
    ),
    model: LlamaCppModel,
) -> TaskResult:
    (
        session,
        executor,
        recording_model,
    ) = build_session(
        root=root,
        embedding_model=embedding_model,
        model=model,
    )

    prepared = session.prepare_context(
        task["request"]
    )

    current_context = (
        prepared.context
    )

    current_paths = context_paths(
        current_context
    )

    if condition == "structured_memory":
        used_memory = available_memory
    else:
        used_memory = ()

    memory_text = (
        format_memory_records(
            used_memory
        )
    )

    memory_ids = tuple(
        record.record_id
        for record in used_memory
    )

    relevant_ids = (
        relevant_record_ids(
            task["id"]
        )
    )

    relevant_count = sum(
        1
        for record in used_memory
        if record.record_id
        in relevant_ids
    )

    irrelevant_count = (
        len(used_memory)
        - relevant_count
    )

    before = snapshot_files(root)

    agent_text = ""
    protocol_valid = True
    protocol_error: str | None = None
    raw_protocol_response: (
        str | None
    ) = None

    returned_model_calls = 0
    returned_tool_calls = 0
    returned_successful = 0
    returned_failed = 0

    original_request = task["request"]

    if memory_text:
        experimental_request = (
            f"{original_request}\n\n"
            f"{memory_text}"
        )
    else:
        experimental_request = (
            original_request
        )

    try:
        result = session.agent.run(
            experimental_request,
            completion_requirement=(
                CompletionRequirement.NONE
            ),
            context=current_context,
        )

        agent_text = result.text

        returned_model_calls = (
            result.metrics.model_calls
        )
        returned_tool_calls = (
            result.metrics.tool_calls
        )
        returned_successful = (
            result.metrics
            .successful_tool_calls
        )
        returned_failed = (
            result.metrics
            .failed_tool_calls
        )

    except ModelProtocolError as exc:
        protocol_valid = False
        protocol_error = str(exc)
        raw_protocol_response = (
            exc.raw_response
        )

    after = snapshot_files(root)

    changed = changed_files(
        before,
        after,
    )

    recall, precision = (
        file_scope_metrics(
            changed=changed,
            required=task[
                "required_changed_files"
            ],
            allowed=task[
                "allowed_changed_files"
            ],
        )
    )

    verification = verify_behavior(
        root,
        task["id"],
    )

    discovery_calls = tuple(
        call
        for call in executor.calls
        if call.name
        in DISCOVERY_TOOLS
    )

    active_paths = tuple(
        sorted(
            {
                path
                for call
                in discovery_calls
                for path
                in call.evidence_paths
            }
        )
    )

    all_paths = tuple(
        sorted(
            set(current_paths)
            | set(active_paths)
        )
    )

    if protocol_valid:
        model_calls = (
            returned_model_calls
        )
        tool_calls = (
            returned_tool_calls
        )
        successful_tool_calls = (
            returned_successful
        )
        failed_tool_calls = (
            returned_failed
        )
    else:
        model_calls = (
            recording_model.model_calls
        )

        tool_calls = len(
            executor.calls
        )

        successful_tool_calls = sum(
            1
            for call in executor.calls
            if call.ok
        )

        failed_tool_calls = (
            tool_calls
            - successful_tool_calls
        )

    return TaskResult(
        task_id=task["id"],
        condition=condition,
        request=original_request,
        agent_text=agent_text,
        protocol_valid=protocol_valid,
        protocol_error=protocol_error,
        raw_protocol_response=(
            raw_protocol_response
        ),
        model_calls=model_calls,
        tool_calls=tool_calls,
        successful_tool_calls=(
            successful_tool_calls
        ),
        failed_tool_calls=(
            failed_tool_calls
        ),
        current_context_paths=(
            current_paths
        ),
        current_context_character_count=(
            current_context.character_count
        ),
        current_context_evidence_count=(
            current_context.evidence_count
        ),
        memory_records_available=len(
            available_memory
        ),
        memory_records_retrieved=len(
            used_memory
        ),
        memory_records_used_in_prompt=len(
            used_memory
        ),
        memory_record_ids=memory_ids,
        memory_evidence_paths=(
            memory_evidence_paths(
                used_memory
            )
        ),
        relevant_memory_records=(
            relevant_count
        ),
        irrelevant_memory_records=(
            irrelevant_count
        ),
        memory_character_count=len(
            memory_text
        ),
        prompt_evidence_character_count=(
            current_context.character_count
            + len(memory_text)
        ),
        active_evidence_paths=(
            active_paths
        ),
        all_evidence_paths=all_paths,
        discovery_calls=(
            discovery_calls
        ),
        changed_files=changed,
        required_file_recall=recall,
        allowed_file_precision=(
            precision
        ),
        behavior_passed=(
            verification.passed
        ),
        behavior_detail=(
            verification.detail
        ),
    )


def evaluate_sequence(
    *,
    pair: dict[str, Any],
    fixture_source: Path,
    condition: str,
    embedding_model: (
        SentenceTransformerEmbeddingModel
    ),
    model: LlamaCppModel,
) -> SequenceResult:
    with tempfile.TemporaryDirectory(
        prefix=(
            f"hewn-010b-"
            f"{pair['id']}-"
            f"{condition}-"
        )
    ) as temporary:
        root = (
            Path(temporary) / "repo"
        )

        shutil.copytree(
            fixture_source,
            root,
        )

        task_1_definition = (
            pair["tasks"][0]
        )

        task_2_definition = (
            pair["tasks"][1]
        )

        task_1 = execute_task(
            root=root,
            task=task_1_definition,
            condition=condition,
            available_memory=(),
            embedding_model=(
                embedding_model
            ),
            model=model,
        )

        persisted_memory = (
            records_established_by(
                task_1_definition["id"]
            )
            if condition
            == "structured_memory"
            else ()
        )

        task_2 = execute_task(
            root=root,
            task=task_2_definition,
            condition=condition,
            available_memory=(
                persisted_memory
            ),
            embedding_model=(
                embedding_model
            ),
            model=model,
        )

        return SequenceResult(
            pair_id=pair["id"],
            condition=condition,
            task_1=task_1,
            task_2=task_2,
            persisted_memory=(
                persisted_memory
            ),
            repeated_discovery_operations=(
                repeated_discovery_operation_count(
                    task_1,
                    task_2,
                )
            ),
        )


def evaluate_pair(
    *,
    pair: dict[str, Any],
    fixture_source: Path,
    embedding_model: (
        SentenceTransformerEmbeddingModel
    ),
    model: LlamaCppModel,
) -> PairComparison:
    stateless = evaluate_sequence(
        pair=pair,
        fixture_source=fixture_source,
        condition="stateless",
        embedding_model=embedding_model,
        model=model,
    )

    structured_memory = (
        evaluate_sequence(
            pair=pair,
            fixture_source=fixture_source,
            condition=(
                "structured_memory"
            ),
            embedding_model=(
                embedding_model
            ),
            model=model,
        )
    )

    return PairComparison(
        pair_id=pair["id"],
        stateless=stateless,
        structured_memory=(
            structured_memory
        ),
    )


def load_manifest() -> dict[str, Any]:
    payload: Any = json.loads(
        MANIFEST_PATH.read_text(
            encoding="utf-8"
        )
    )

    if not isinstance(
        payload,
        dict,
    ):
        raise TypeError(
            "010B manifest root "
            "must be an object"
        )

    return payload


def validate_manifest(
    manifest: dict[str, Any],
) -> None:
    if (
        manifest.get("experiment")
        != "010A"
    ):
        raise ValueError(
            "010B intentionally reuses "
            "the frozen 010A corpus"
        )

    pairs = manifest.get("pairs")

    if not isinstance(pairs, list):
        raise TypeError(
            "Manifest pairs must be a list"
        )

    if len(pairs) != 3:
        raise ValueError(
            "010B expects exactly "
            "three task pairs"
        )


def print_task(
    task: TaskResult,
) -> None:
    print(
        f"{task.task_id}: "
        f"behavior={task.behavior_passed} "
        f"protocol={task.protocol_valid} "
        f"model_calls={task.model_calls} "
        f"tool_calls={task.tool_calls} "
        f"memory={task.memory_records_used_in_prompt} "
        f"context_chars="
        f"{task.current_context_character_count} "
        f"memory_chars="
        f"{task.memory_character_count}"
    )


def print_summary(
    results: list[PairComparison],
) -> None:
    print(
        "\n===== 010B SUMMARY ====="
    )

    stateless_behavior = 0
    memory_behavior = 0

    stateless_protocol = 0
    memory_protocol = 0

    stateless_t2_tools = 0
    memory_t2_tools = 0

    stateless_repeated = 0
    memory_repeated = 0

    total_pairs = len(results)

    for comparison in results:
        print(
            f"\n[{comparison.pair_id}]"
        )

        print("stateless:")
        print_task(
            comparison.stateless.task_1
        )
        print_task(
            comparison.stateless.task_2
        )

        print("structured_memory:")
        print_task(
            comparison
            .structured_memory
            .task_1
        )
        print_task(
            comparison
            .structured_memory
            .task_2
        )

        stateless_t2 = (
            comparison.stateless.task_2
        )

        memory_t2 = (
            comparison
            .structured_memory
            .task_2
        )

        stateless_behavior += int(
            stateless_t2.behavior_passed
        )

        memory_behavior += int(
            memory_t2.behavior_passed
        )

        stateless_protocol += int(
            stateless_t2.protocol_valid
        )

        memory_protocol += int(
            memory_t2.protocol_valid
        )

        stateless_t2_tools += (
            stateless_t2.tool_calls
        )

        memory_t2_tools += (
            memory_t2.tool_calls
        )

        stateless_repeated += (
            comparison
            .stateless
            .repeated_discovery_operations
        )

        memory_repeated += (
            comparison
            .structured_memory
            .repeated_discovery_operations
        )

        print(
            "T2 delta: "
            f"behavior "
            f"{stateless_t2.behavior_passed}"
            " -> "
            f"{memory_t2.behavior_passed}, "
            f"tools "
            f"{stateless_t2.tool_calls}"
            " -> "
            f"{memory_t2.tool_calls}, "
            f"context chars "
            f"{stateless_t2.current_context_character_count}"
            " + "
            f"{memory_t2.memory_character_count}"
            " memory chars"
        )

    print(
        "\n===== 010B T2 AGGREGATE ====="
    )

    print(
        "behavioral success: "
        f"stateless={stateless_behavior}/"
        f"{total_pairs} "
        f"memory={memory_behavior}/"
        f"{total_pairs}"
    )

    print(
        "protocol-valid: "
        f"stateless={stateless_protocol}/"
        f"{total_pairs} "
        f"memory={memory_protocol}/"
        f"{total_pairs}"
    )

    print(
        "tool calls: "
        f"stateless={stateless_t2_tools} "
        f"memory={memory_t2_tools}"
    )

    print(
        "repeated discovery operations: "
        f"stateless={stateless_repeated} "
        f"memory={memory_repeated}"
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--embedding-model",
        default=DEFAULT_EMBEDDING_MODEL,
    )

    parser.add_argument(
        "--base-url",
        default=(
            "http://127.0.0.1:8080"
        ),
    )

    parser.add_argument(
        "--output",
        type=Path,
        default=(
            RESULTS_ROOT
            / (
                "010b-structured-memory-"
                "run001.json"
            )
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

    results: list[
        PairComparison
    ] = []

    for pair in manifest["pairs"]:
        fixture_source = (
            FIXTURES_ROOT
            / pair["fixture"]
        )

        results.append(
            evaluate_pair(
                pair=pair,
                fixture_source=(
                    fixture_source
                ),
                embedding_model=(
                    embedding_model
                ),
                model=model,
            )
        )

    args.output.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    payload = {
        "experiment": "010B",
        "run": "run001",
        "design": (
            "paired stateless versus "
            "structured repository memory"
        ),
        "embedding_model": (
            args.embedding_model
        ),
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
        "\nWrote results to "
        f"{args.output}"
    )


if __name__ == "__main__":
    main()