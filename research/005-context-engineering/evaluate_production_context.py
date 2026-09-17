from __future__ import annotations

import json
from pathlib import Path
from time import perf_counter
from typing import Any

from hewn.agent import (
    Agent,
    AgentLimitError,
    AgentRunResult,
    AgentStagnationError,
)
from hewn.builtin_tools import make_builtin_tool_registry
from hewn.context.builder import ContextBuilder
from hewn.llama_cpp import LlamaCppModel
from hewn.model_protocol import ModelProtocolError
from hewn.models import ModelError
from hewn.repository.index import RepositoryIndex
from hewn.retrieval.router import RetrievalRoute
from hewn.retrieval.semantic_index import SemanticIndex
from hewn.retrieval.sentence_transformer import (
    SentenceTransformerEmbeddingModel,
)
from hewn.retrieval.symbol_documents import (
    build_symbol_documents,
)
from hewn.session import HewnSession, PreparedContext
from hewn.tools import ToolExecutor
from hewn.workspace import Workspace

REPO_ROOT = Path(__file__).resolve().parents[2]

TASKS_PATH = (
    REPO_ROOT
    / "research"
    / "002-tools"
    / "tasks.json"
)

RESULTS_DIR = Path(__file__).with_name("results")

RESULTS_PATH = (
    RESULTS_DIR
    / "production-context-run-001.json"
)

EMBEDDING_MODEL = "BAAI/bge-small-en-v1.5"

CODING_MODEL = (
    "Qwen2.5-Coder-1.5B-Instruct Q4_K_M"
)

SEMANTIC_CANDIDATE_LIMIT = 12

CONDITIONS = (
    "no_context",
    "production_context",
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

    return data


def build_agent(
    *,
    model: LlamaCppModel,
) -> Agent:
    workspace = Workspace(
        REPO_ROOT
    )

    registry = make_builtin_tool_registry(
        workspace
    )

    executor = ToolExecutor(
        registry
    )

    return Agent(
        model=model,
        registry=registry,
        executor=executor,
    )


def evaluate_text(
    *,
    text: str,
    expected_file: str,
    expected_symbol: str,
) -> dict[str, Any]:
    file_present = expected_file in text
    symbol_present = expected_symbol in text

    return {
        "expected_file_present": file_present,
        "expected_symbol_present": symbol_present,
        "correct": (
            file_present
            and symbol_present
        ),
        "response_text": text,
    }


def selected_evidence(
    prepared: PreparedContext,
) -> list[dict[str, Any]]:
    return [
        {
            "path": str(
                item.retrieval_result.document.path
            ),
            "symbol": (
                item.retrieval_result.document.symbol
            ),
            "score": item.retrieval_result.score,
            "characters": len(item.text),
        }
        for item in prepared.context.evidence
    ]


def run_agent_condition(
    *,
    agent: Agent,
    task_text: str,
    expected_file: str,
    expected_symbol: str,
    prepared: PreparedContext | None,
) -> dict[str, Any]:
    context = (
        None
        if prepared is None
        else prepared.context
    )

    context_characters = (
        0
        if context is None
        else context.character_count
    )

    context_evidence_count = (
        0
        if context is None
        else context.evidence_count
    )

    context_unique_file_count = (
        0
        if context is None
        else context.unique_file_count
    )

    start = perf_counter()

    try:
        result: AgentRunResult = agent.run(
            task_text,
            context=context,
        )
    except AgentLimitError as exc:
        elapsed = perf_counter() - start

        return {
            "context_characters": context_characters,
            "context_evidence_count": (
                context_evidence_count
            ),
            "context_unique_file_count": (
                context_unique_file_count
            ),
            "response_seconds": elapsed,
            "error_type": "agent_limit",
            "error": (
                f"{type(exc).__name__}: {exc}"
            ),
            "final_response": False,
            "expected_file_present": False,
            "expected_symbol_present": False,
            "correct": False,
            "response_text": None,
            "model_calls": exc.metrics.model_calls,
            "tool_calls": exc.metrics.tool_calls,
            "successful_tool_calls": (
                exc.metrics.successful_tool_calls
            ),
            "failed_tool_calls": (
                exc.metrics.failed_tool_calls
            ),
        }
    except AgentStagnationError as exc:
        elapsed = perf_counter() - start

        return {
            "context_characters": context_characters,
            "context_evidence_count": (
                context_evidence_count
            ),
            "context_unique_file_count": (
                context_unique_file_count
            ),
            "response_seconds": elapsed,
            "error_type": "agent_stagnation",
            "error": (
                f"{type(exc).__name__}: {exc}"
            ),
            "final_response": False,
            "expected_file_present": False,
            "expected_symbol_present": False,
            "correct": False,
            "response_text": None,
            "model_calls": exc.metrics.model_calls,
            "tool_calls": exc.metrics.tool_calls,
            "successful_tool_calls": (
                exc.metrics.successful_tool_calls
            ),
            "failed_tool_calls": (
                exc.metrics.failed_tool_calls
            ),
        }
    except ModelProtocolError as exc:
        elapsed = perf_counter() - start

        return {
            "context_characters": context_characters,
            "context_evidence_count": (
                context_evidence_count
            ),
            "context_unique_file_count": (
                context_unique_file_count
            ),
            "response_seconds": elapsed,
            "error_type": "protocol",
            "error": (
                f"{type(exc).__name__}: {exc}"
            ),
            "final_response": False,
            "expected_file_present": False,
            "expected_symbol_present": False,
            "correct": False,
            "response_text": None,
            "model_calls": None,
            "tool_calls": None,
            "successful_tool_calls": None,
            "failed_tool_calls": None,
        }
    except ModelError as exc:
        elapsed = perf_counter() - start

        return {
            "context_characters": context_characters,
            "context_evidence_count": (
                context_evidence_count
            ),
            "context_unique_file_count": (
                context_unique_file_count
            ),
            "response_seconds": elapsed,
            "error_type": "model",
            "error": (
                f"{type(exc).__name__}: {exc}"
            ),
            "final_response": False,
            "expected_file_present": False,
            "expected_symbol_present": False,
            "correct": False,
            "response_text": None,
            "model_calls": None,
            "tool_calls": None,
            "successful_tool_calls": None,
            "failed_tool_calls": None,
        }

    elapsed = perf_counter() - start

    evaluation = evaluate_text(
        text=result.text,
        expected_file=expected_file,
        expected_symbol=expected_symbol,
    )

    return {
        "context_characters": context_characters,
        "context_evidence_count": (
            context_evidence_count
        ),
        "context_unique_file_count": (
            context_unique_file_count
        ),
        "response_seconds": elapsed,
        "error_type": None,
        "error": None,
        "final_response": True,
        **evaluation,
        "model_calls": result.metrics.model_calls,
        "tool_calls": result.metrics.tool_calls,
        "successful_tool_calls": (
            result.metrics.successful_tool_calls
        ),
        "failed_tool_calls": (
            result.metrics.failed_tool_calls
        ),
    }


def empty_totals() -> dict[str, int | float]:
    return {
        "correct": 0,
        "final_responses": 0,
        "model_errors": 0,
        "protocol_errors": 0,
        "agent_limit_errors": 0,
        "agent_stagnation_errors": 0,
        "context_characters": 0,
        "context_evidence_count": 0,
        "context_unique_file_count": 0,
        "response_seconds": 0.0,
        "model_calls": 0,
        "tool_calls": 0,
        "successful_tool_calls": 0,
        "failed_tool_calls": 0,
        "runs_with_metrics": 0,
    }


def update_totals(
    totals: dict[str, int | float],
    record: dict[str, Any],
) -> None:
    if record["correct"]:
        totals["correct"] += 1

    if record["final_response"]:
        totals["final_responses"] += 1

    error_type = record["error_type"]

    if error_type == "model":
        totals["model_errors"] += 1
    elif error_type == "protocol":
        totals["protocol_errors"] += 1
    elif error_type == "agent_limit":
        totals["agent_limit_errors"] += 1
    elif error_type == "agent_stagnation":
        totals["agent_stagnation_errors"] += 1

    totals["context_characters"] += (
        record["context_characters"]
    )

    totals["context_evidence_count"] += (
        record["context_evidence_count"]
    )

    totals["context_unique_file_count"] += (
        record["context_unique_file_count"]
    )

    totals["response_seconds"] += (
        record["response_seconds"]
    )

    if record["model_calls"] is not None:
        totals["model_calls"] += (
            record["model_calls"]
        )

        totals["tool_calls"] += (
            record["tool_calls"]
        )

        totals["successful_tool_calls"] += (
            record["successful_tool_calls"]
        )

        totals["failed_tool_calls"] += (
            record["failed_tool_calls"]
        )

        totals["runs_with_metrics"] += 1


def main() -> int:
    tasks = load_tasks()

    repository_index = RepositoryIndex.build(
        REPO_ROOT
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
    print(
        "Temperature: 0.0"
    )
    print(
        "Agent tools: builtin Hewn tools"
    )
    print(
        f"Symbol documents: "
        f"{len(retrieval_documents)}"
    )
    print(
        "Production semantic evidence limit: 3 unique files"
    )
    print(
        "Production bounded source limit: 800 chars/symbol"
    )
    print(
        f"Semantic candidate limit: "
        f"{SEMANTIC_CANDIDATE_LIMIT}"
    )
    print(
        "Conditions: "
        + ", ".join(CONDITIONS)
    )
    print(
        f"Tasks: {len(tasks)}"
    )
    print(
        "Minimum planned agent runs: "
        f"{len(tasks) * len(CONDITIONS)}"
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

    agent = build_agent(
        model=coding_model,
    )

    context_builder = ContextBuilder(
        repository_root=REPO_ROOT,
        repository_index=repository_index,
    )

    session = HewnSession(
        agent=agent,
        repository_index=repository_index,
        semantic_index=semantic_index,
        embedding_model=embedding_model,
        context_builder=context_builder,
        semantic_candidate_limit=(
            SEMANTIC_CANDIDATE_LIMIT
        ),
    )

    totals = {
        condition: empty_totals()
        for condition in CONDITIONS
    }

    records: list[dict[str, Any]] = []

    for task_index, task in enumerate(tasks):
        task_id = task["id"]
        task_text = task["task"]
        expected_file = task["expected_file"]
        expected_symbol = task["expected_symbol"]

        prepared = session.prepare_context(
            task_text
        )

        selected_paths = [
            str(
                item.retrieval_result.document.path
            )
            for item in prepared.context.evidence
        ]

        retrieval_covered = (
            expected_file in selected_paths
        )

        print(
            f"{task_id}: "
            f"category={task['category']} "
            f"route={prepared.retrieval.route.value} "
            f"retrieval="
            f"{'PASS' if retrieval_covered else 'FAIL'} "
            f"context={prepared.context.character_count} chars "
            f"files={prepared.context.unique_file_count}"
        )

        conditions: dict[str, Any] = {}

        # Alternate condition order by task so that one condition is
        # not systematically always evaluated first.
        condition_order: tuple[str, ...]

        if task_index % 2 == 0:
            condition_order = CONDITIONS
        else:
            condition_order = tuple(
                reversed(CONDITIONS)
            )

        for condition in condition_order:
            prepared_for_condition = (
                prepared
                if condition == "production_context"
                else None
            )

            result = run_agent_condition(
                agent=agent,
                task_text=task_text,
                expected_file=expected_file,
                expected_symbol=expected_symbol,
                prepared=prepared_for_condition,
            )

            conditions[condition] = result

            update_totals(
                totals[condition],
                result,
            )

            if result["error_type"] is not None:
                print(
                    f"  {condition:>18}: "
                    f"ERROR "
                    f"type={result['error_type']} "
                    f"time={result['response_seconds']:.2f}s"
                )
            else:
                print(
                    f"  {condition:>18}: "
                    f"{'PASS' if result['correct'] else 'FAIL'} "
                    f"models={result['model_calls']} "
                    f"tools={result['tool_calls']} "
                    f"time={result['response_seconds']:.2f}s"
                )

        records.append(
            {
                "task_id": task_id,
                "category": task["category"],
                "task": task_text,
                "expected_file": expected_file,
                "expected_symbol": expected_symbol,
                "retrieval": {
                    "route": (
                        prepared.retrieval.route.value
                    ),
                    "matched_symbol": (
                        prepared.retrieval.matched_symbol
                    ),
                    "covered_expected_file": (
                        retrieval_covered
                    ),
                    "selected_evidence": (
                        selected_evidence(
                            prepared
                        )
                    ),
                    "context_characters": (
                        prepared.context.character_count
                    ),
                    "context_evidence_count": (
                        prepared.context.evidence_count
                    ),
                    "context_unique_file_count": (
                        prepared.context.unique_file_count
                    ),
                },
                "condition_order": list(
                    condition_order
                ),
                "conditions": conditions,
            }
        )

    RESULTS_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    output = {
        "experiment": (
            "module_5_production_context_integration"
        ),
        "configuration": {
            "repository": "Hewn",
            "tasks_path": str(
                TASKS_PATH.relative_to(
                    REPO_ROOT
                )
            ),
            "task_count": len(tasks),
            "embedding_model": EMBEDDING_MODEL,
            "coding_model": CODING_MODEL,
            "temperature": 0.0,
            "agent_tools": "builtin Hewn tools",
            "semantic_candidate_limit": (
                SEMANTIC_CANDIDATE_LIMIT
            ),
            "semantic_evidence_limit": 3,
            "bounded_source_limit": 800,
            "conditions": list(CONDITIONS),
            "condition_order": (
                "alternated by task"
            ),
            "repeated_trials": False,
        },
        "semantic_index": {
            "document_count": (
                semantic_index.stats.document_count
            ),
            "embedding_dimension": (
                semantic_index.stats.embedding_dimension
            ),
            "indexing_seconds": (
                semantic_index.stats.indexing_seconds
            ),
        },
        "totals": totals,
        "records": records,
    }

    RESULTS_PATH.write_text(
        json.dumps(
            output,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    print()
    print("Summary")

    task_count = len(tasks)

    for condition in CONDITIONS:
        condition_totals = totals[
            condition
        ]

        runs_with_metrics = int(
            condition_totals[
                "runs_with_metrics"
            ]
        )

        avg_model_calls = (
            float(
                condition_totals[
                    "model_calls"
                ]
            )
            / runs_with_metrics
            if runs_with_metrics
            else 0.0
        )

        avg_tool_calls = (
            float(
                condition_totals[
                    "tool_calls"
                ]
            )
            / runs_with_metrics
            if runs_with_metrics
            else 0.0
        )

        avg_context = (
            float(
                condition_totals[
                    "context_characters"
                ]
            )
            / task_count
        )

        avg_time = (
            float(
                condition_totals[
                    "response_seconds"
                ]
            )
            / task_count
        )

        correct = int(
            condition_totals["correct"]
        )

        final_responses = int(
            condition_totals[
                "final_responses"
            ]
        )

        print(
            f"{condition:>18}: "
            f"success={correct}/{task_count} "
            f"({correct / task_count:.1%}) "
            f"final={final_responses}/{task_count} "
            f"avg_models={avg_model_calls:.2f} "
            f"avg_tools={avg_tool_calls:.2f} "
            f"avg_context={avg_context:.1f} "
            f"avg_time={avg_time:.2f}s"
        )

        print(
            " " * 20
            + "errors: "
            f"model={condition_totals['model_errors']} "
            f"protocol={condition_totals['protocol_errors']} "
            f"limit={condition_totals['agent_limit_errors']} "
            f"stagnation="
            f"{condition_totals['agent_stagnation_errors']}"
        )

    exact_tasks = [
        record
        for record in records
        if record["category"] == "symbol"
    ]

    conceptual_tasks = [
        record
        for record in records
        if record["category"] == "concept"
    ]

    print()
    print("Category success")

    for condition in CONDITIONS:
        exact_correct = sum(
            bool(
                record["conditions"][
                    condition
                ]["correct"]
            )
            for record in exact_tasks
        )

        conceptual_correct = sum(
            bool(
                record["conditions"][
                    condition
                ]["correct"]
            )
            for record in conceptual_tasks
        )

        print(
            f"{condition:>18}: "
            f"exact={exact_correct}/{len(exact_tasks)} "
            f"conceptual="
            f"{conceptual_correct}/{len(conceptual_tasks)}"
        )

    retrieval_coverage = sum(
        bool(
            record["retrieval"][
                "covered_expected_file"
            ]
        )
        for record in records
    )

    exact_routes = sum(
        record["retrieval"]["route"]
        == RetrievalRoute.EXACT_SYMBOL.value
        for record in records
    )

    semantic_routes = sum(
        record["retrieval"]["route"]
        == RetrievalRoute.SEMANTIC.value
        for record in records
    )

    print()
    print(
        "Production retrieval coverage: "
        f"{retrieval_coverage}/{len(records)}"
    )
    print(
        "Routes: "
        f"exact={exact_routes}, "
        f"semantic={semantic_routes}"
    )

    print()
    print(
        f"Results: {RESULTS_PATH}"
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(
        main()
    )