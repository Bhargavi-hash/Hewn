from __future__ import annotations

import json
from pathlib import Path
from time import perf_counter
from typing import Any

from hewn.context.source import (
    build_bounded_source_document,
    build_signature_document,
    build_source_document,
    resolve_document_symbol,
)
from hewn.llama_cpp import LlamaCppModel
from hewn.model_protocol import ModelProtocolError
from hewn.models import (
    FinalResponse,
    Message,
    ModelError,
)
from hewn.repository.index import RepositoryIndex
from hewn.retrieval.models import (
    RepositoryDocument,
    RetrievalResult,
)
from hewn.retrieval.router import retrieve_routed
from hewn.retrieval.semantic_index import SemanticIndex
from hewn.retrieval.sentence_transformer import (
    SentenceTransformerEmbeddingModel,
)
from hewn.retrieval.symbol_documents import (
    build_symbol_documents,
)
from hewn.tools import ToolCall

REPO_ROOT = Path(__file__).resolve().parents[2]

TASKS_PATH = (
    REPO_ROOT
    / "research"
    / "002-tools"
    / "tasks.json"
)

RESULTS_DIR = Path(__file__).with_name("results")

EMBEDDING_MODEL = "BAAI/bge-small-en-v1.5"

CODING_MODEL = (
    "Qwen2.5-Coder-1.5B-Instruct Q4_K_M"
)

EVIDENCE_LIMIT = 3
BOUNDED_SOURCE_LIMIT = 800

SEMANTIC_TASK_IDS = frozenset(
    {
        "nav-006",
        "nav-007",
        "nav-008",
        "nav-009",
    }
)

REPRESENTATIONS = (
    "signature",
    "bounded_source",
    "whole_source",
)


def load_tasks() -> list[dict[str, Any]]:
    data = json.loads(
        TASKS_PATH.read_text(
            encoding="utf-8",
        )
    )

    if not isinstance(data, list):
        raise TypeError(
            "Navigation tasks must be a list"
        )

    tasks: list[dict[str, Any]] = []

    for item in data:
        if not isinstance(item, dict):
            raise TypeError(
                "Navigation task entries must be objects"
            )

        task_id = item.get("id")

        if not isinstance(task_id, str):
            raise TypeError(
                "Navigation task id must be a string"
            )

        if task_id not in SEMANTIC_TASK_IDS:
            continue

        task = item.get("task")
        expected_file = item.get(
            "expected_file"
        )
        expected_symbol = item.get(
            "expected_symbol"
        )

        if not isinstance(task, str):
            raise TypeError(
                "Navigation task text must be a string"
            )

        if not isinstance(
            expected_file,
            str,
        ):
            raise TypeError(
                "Expected file must be a string"
            )

        if not isinstance(
            expected_symbol,
            str,
        ):
            raise TypeError(
                "Expected symbol must be a string"
            )

        tasks.append(item)

    loaded_ids = {
        task["id"]
        for task in tasks
    }

    if loaded_ids != SEMANTIC_TASK_IDS:
        raise ValueError(
            "Semantic task set is incomplete"
        )

    return tasks


def unique_file_results(
    results: tuple[RetrievalResult, ...],
) -> tuple[RetrievalResult, ...]:
    seen: set[str] = set()
    unique: list[RetrievalResult] = []

    for result in results:
        path = str(
            result.document.path
        )

        if path in seen:
            continue

        seen.add(path)
        unique.append(result)

    return tuple(unique)


def represent_document(
    *,
    representation: str,
    structural_document: RepositoryDocument,
    repository_index: RepositoryIndex,
) -> RepositoryDocument:
    symbol = resolve_document_symbol(
        structural_document,
        repository_index,
    )

    if representation == "signature":
        return build_signature_document(
            repository_root=REPO_ROOT,
            symbol=symbol,
        )

    if representation == "bounded_source":
        return build_bounded_source_document(
            repository_root=REPO_ROOT,
            symbol=symbol,
            character_limit=(
                BOUNDED_SOURCE_LIMIT
            ),
        )

    if representation == "whole_source":
        return build_source_document(
            repository_root=REPO_ROOT,
            symbol=symbol,
        )

    raise ValueError(
        f"Unknown representation: {representation}"
    )


def build_context(
    documents: tuple[
        RepositoryDocument,
        ...,
    ],
) -> str:
    sections: list[str] = []

    for number, document in enumerate(
        documents,
        start=1,
    ):
        sections.append(
            "\n".join(
                (
                    f"[Evidence {number}]",
                    f"path: {document.path}",
                    (
                        f"symbol: {document.symbol}"
                        if document.symbol is not None
                        else "symbol: unknown"
                    ),
                    document.text,
                )
            )
        )

    return "\n\n".join(
        sections
    )


def build_user_message(
    *,
    task: str,
    context: str,
) -> Message:
    content = (
        "Answer the repository question using only "
        "the supplied repository evidence.\n"
        "\n"
        "Your final answer must identify the relevant "
        "repository file and symbol.\n"
        "\n"
        "Do not invent repository paths or symbols that "
        "are not supported by the evidence.\n"
        "\n"
        f"Question:\n{task}\n"
        "\n"
        f"Repository evidence:\n{context}"
    )

    return Message(
        role="user",
        content=content,
    )


def evaluate_response(
    *,
    response: FinalResponse | ToolCall,
    expected_file: str,
    expected_symbol: str,
) -> dict[str, Any]:
    if isinstance(
        response,
        ToolCall,
    ):
        return {
            "response_type": "tool_call",
            "final_response": False,
            "expected_file_present": False,
            "expected_symbol_present": False,
            "correct": False,
            "response_text": None,
            "tool_name": response.name,
        }

    text = response.text

    file_present = (
        expected_file in text
    )
    symbol_present = (
        expected_symbol in text
    )

    return {
        "response_type": "final",
        "final_response": True,
        "expected_file_present": (
            file_present
        ),
        "expected_symbol_present": (
            symbol_present
        ),
        "correct": (
            file_present
            and symbol_present
        ),
        "response_text": text,
        "tool_name": None,
    }


def main() -> int:
    tasks = load_tasks()

    repository_index = (
        RepositoryIndex.build(
            REPO_ROOT
        )
    )

    retrieval_documents = (
        build_symbol_documents(
            repository_index,
            path_prefix="src/hewn",
        )
    )

    print(
        f"Embedding model: {EMBEDDING_MODEL}"
    )
    print(
        f"Coding model: {CODING_MODEL}"
    )
    print("Temperature: 0.0")
    print(
        "Tools exposed to coding model: 0"
    )
    print(
        f"Symbol documents: "
        f"{len(retrieval_documents)}"
    )
    print(
        f"Evidence limit: "
        f"{EVIDENCE_LIMIT} unique files"
    )
    print(
        f"Bounded source limit: "
        f"{BOUNDED_SOURCE_LIMIT} "
        "chars per symbol"
    )
    print(
        "Tasks: nav-006 through nav-009"
    )
    print(
        "Representations: "
        + ", ".join(
            REPRESENTATIONS
        )
    )
    print(
        f"Planned model calls: "
        f"{len(tasks) * len(REPRESENTATIONS)}"
    )
    print()

    embedding_model = (
        SentenceTransformerEmbeddingModel(
            EMBEDDING_MODEL
        )
    )

    semantic_index = SemanticIndex.build(
        retrieval_documents,
        model=embedding_model,
    )

    coding_model = LlamaCppModel(
        temperature=0.0,
    )

    totals: dict[
        str,
        dict[str, int | float],
    ] = {
        representation: {
            "correct": 0,
            "final_responses": 0,
            "model_errors": 0,
            "protocol_errors": 0,
            "context_characters": 0,
            "response_seconds": 0.0,
        }
        for representation in REPRESENTATIONS
    }

    records: list[
        dict[str, Any]
    ] = []

    for task in tasks:
        task_text = task["task"]
        expected_file = task[
            "expected_file"
        ]
        expected_symbol = task[
            "expected_symbol"
        ]

        if not isinstance(
            task_text,
            str,
        ):
            raise TypeError(
                "Navigation task text must be a string"
            )

        if not isinstance(
            expected_file,
            str,
        ):
            raise TypeError(
                "Expected file must be a string"
            )

        if not isinstance(
            expected_symbol,
            str,
        ):
            raise TypeError(
                "Expected symbol must be a string"
            )

        routed = retrieve_routed(
            task_text,
            repository_index=repository_index,
            semantic_index=semantic_index,
            model=embedding_model,
            semantic_limit=len(
                retrieval_documents
            ),
        )

        selected = (
            unique_file_results(
                routed.results
            )[:EVIDENCE_LIMIT]
        )

        selected_paths = [
            str(
                result.document.path
            )
            for result in selected
        ]

        retrieval_covered = (
            expected_file
            in selected_paths
        )

        print(
            f"{task['id']}: "
            f"route={routed.route.value} "
            f"retrieval="
            f"{'PASS' if retrieval_covered else 'FAIL'}"
        )

        conditions: dict[
            str,
            Any,
        ] = {}

        for representation in REPRESENTATIONS:
            represented = tuple(
                represent_document(
                    representation=(
                        representation
                    ),
                    structural_document=(
                        result.document
                    ),
                    repository_index=(
                        repository_index
                    ),
                )
                for result in selected
            )

            context = build_context(
                represented
            )

            message = build_user_message(
                task=task_text,
                context=context,
            )

            start = perf_counter()

            try:
                response = (
                    coding_model.respond(
                        messages=[message],
                        tools=[],
                    )
                )
            except (
                ModelError,
                ModelProtocolError,
            ) as exc:
                elapsed = (
                    perf_counter()
                    - start
                )

                if isinstance(
                    exc,
                    ModelProtocolError,
                ):
                    error_type = (
                        "protocol"
                    )

                    totals[
                        representation
                    ][
                        "protocol_errors"
                    ] += 1
                else:
                    error_type = "model"

                    totals[
                        representation
                    ][
                        "model_errors"
                    ] += 1

                totals[
                    representation
                ][
                    "context_characters"
                ] += len(context)

                totals[
                    representation
                ][
                    "response_seconds"
                ] += elapsed

                conditions[
                    representation
                ] = {
                    "context_characters": (
                        len(context)
                    ),
                    "response_seconds": (
                        elapsed
                    ),
                    "error_type": (
                        error_type
                    ),
                    "model_error": (
                        f"{type(exc).__name__}: "
                        f"{exc}"
                    ),
                    "response_type": None,
                    "final_response": False,
                    "expected_file_present": (
                        False
                    ),
                    "expected_symbol_present": (
                        False
                    ),
                    "correct": False,
                    "response_text": None,
                    "tool_name": None,
                }

                print(
                    f"  "
                    f"{representation:>14}: "
                    "ERROR "
                    f"error_type={error_type} "
                    f"chars={len(context)} "
                    f"time={elapsed:.2f}s "
                    f"{type(exc).__name__}: "
                    f"{exc}"
                )

                continue

            elapsed = (
                perf_counter()
                - start
            )

            evaluation = (
                evaluate_response(
                    response=response,
                    expected_file=(
                        expected_file
                    ),
                    expected_symbol=(
                        expected_symbol
                    ),
                )
            )

            totals[
                representation
            ][
                "context_characters"
            ] += len(context)

            totals[
                representation
            ][
                "response_seconds"
            ] += elapsed

            if evaluation["correct"]:
                totals[
                    representation
                ]["correct"] += 1

            if evaluation[
                "final_response"
            ]:
                totals[
                    representation
                ][
                    "final_responses"
                ] += 1

            conditions[
                representation
            ] = {
                "context_characters": (
                    len(context)
                ),
                "response_seconds": (
                    elapsed
                ),
                "error_type": None,
                "model_error": None,
                **evaluation,
            }

            print(
                f"  "
                f"{representation:>14}: "
                f"{'PASS' if evaluation['correct'] else 'FAIL'} "
                f"type="
                f"{evaluation['response_type']} "
                f"file="
                f"{evaluation['expected_file_present']} "
                f"symbol="
                f"{evaluation['expected_symbol_present']} "
                f"chars={len(context)} "
                f"time={elapsed:.2f}s"
            )

        records.append(
            {
                "id": task["id"],
                "category": task[
                    "category"
                ],
                "task": task_text,
                "expected_file": (
                    expected_file
                ),
                "expected_symbol": (
                    expected_symbol
                ),
                "route": (
                    routed.route.value
                ),
                "retrieval_covered": (
                    retrieval_covered
                ),
                "selected_evidence": [
                    {
                        "path": str(
                            result.document.path
                        ),
                        "symbol": (
                            result.document.symbol
                        ),
                        "score": (
                            result.score
                        ),
                    }
                    for result in selected
                ],
                "conditions": conditions,
            }
        )

    task_count = len(tasks)

    summary: dict[
        str,
        dict[str, Any],
    ] = {}

    for representation in REPRESENTATIONS:
        values = totals[
            representation
        ]

        correct = int(
            values["correct"]
        )

        summary[
            representation
        ] = {
            "correct": correct,
            "success_rate": (
                correct / task_count
                if task_count
                else 0.0
            ),
            "final_responses": int(
                values[
                    "final_responses"
                ]
            ),
            "model_errors": int(
                values["model_errors"]
            ),
            "protocol_errors": int(
                values[
                    "protocol_errors"
                ]
            ),
            "average_context_characters": (
                float(
                    values[
                        "context_characters"
                    ]
                )
                / task_count
                if task_count
                else 0.0
            ),
            "average_response_seconds": (
                float(
                    values[
                        "response_seconds"
                    ]
                )
                / task_count
                if task_count
                else 0.0
            ),
        }

    output = {
        "configuration": {
            "embedding_model": (
                EMBEDDING_MODEL
            ),
            "coding_model": (
                CODING_MODEL
            ),
            "temperature": 0.0,
            "max_tokens": (
                coding_model.max_tokens
            ),
            "tools_exposed": 0,
            "retrieval": (
                "module-4-hybrid"
            ),
            "evidence_limit": (
                EVIDENCE_LIMIT
            ),
            "unique_file_evidence": True,
            "bounded_source_limit": (
                BOUNDED_SOURCE_LIMIT
            ),
            "representations": list(
                REPRESENTATIONS
            ),
            "task_ids": [
                task["id"]
                for task in tasks
            ],
            "task_count": (
                task_count
            ),
            "planned_model_calls": (
                task_count
                * len(
                    REPRESENTATIONS
                )
            ),
            "scoring": (
                "final response contains "
                "expected file and canonical symbol"
            ),
        },
        "summary": summary,
        "tasks": records,
    }

    RESULTS_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    output_path = (
        RESULTS_DIR
        / "source-granularity-run-001.json"
    )

    output_path.write_text(
        json.dumps(
            output,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    print()
    print("Summary")

    for representation in REPRESENTATIONS:
        values = summary[
            representation
        ]

        print(
            f"{representation:>14}: "
            f"success="
            f"{values['correct']}/{task_count} "
            f"({values['success_rate']:.1%}) "
            f"final="
            f"{values['final_responses']}/{task_count} "
            f"model_errors="
            f"{values['model_errors']} "
            f"protocol_errors="
            f"{values['protocol_errors']} "
            f"avg_context="
            f"{values['average_context_characters']:.1f} "
            f"avg_time="
            f"{values['average_response_seconds']:.2f}s"
        )

    print()
    print(
        f"Results: {output_path}"
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(
        main()
    )