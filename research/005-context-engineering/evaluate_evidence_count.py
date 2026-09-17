from __future__ import annotations

import json
from pathlib import Path
from time import perf_counter
from typing import Any

from hewn.context.budget import select_by_evidence_count
from hewn.repository.index import RepositoryIndex
from hewn.retrieval.models import RetrievalResult
from hewn.retrieval.router import (
    retrieve_routed,
)
from hewn.retrieval.semantic_index import SemanticIndex
from hewn.retrieval.sentence_transformer import (
    SentenceTransformerEmbeddingModel,
)
from hewn.retrieval.symbol_documents import (
    build_symbol_documents,
)

REPO_ROOT = Path(__file__).resolve().parents[2]

TASKS_PATH = (
    REPO_ROOT
    / "research"
    / "002-tools"
    / "tasks.json"
)

RESULTS_DIR = Path(__file__).with_name("results")

MODEL_NAME = "BAAI/bge-small-en-v1.5"

FIXED_LIMITS = (1, 3, 5)


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


def unique_file_results(
    results: tuple[RetrievalResult, ...],
) -> tuple[RetrievalResult, ...]:
    seen: set[str] = set()
    unique: list[RetrievalResult] = []

    for result in results:
        path = str(result.document.path)

        if path in seen:
            continue

        seen.add(path)
        unique.append(result)

    return tuple(unique)


def expected_file_present(
    bundle_results: tuple[RetrievalResult, ...],
    expected_file: str,
) -> bool:
    return any(
        str(result.document.path) == expected_file
        for result in bundle_results
    )


def main() -> int:
    tasks = load_tasks()

    repository_index = RepositoryIndex.build(
        REPO_ROOT
    )

    documents = build_symbol_documents(
        repository_index,
        path_prefix="src/hewn",
    )

    print(f"Model: {MODEL_NAME}")
    print(f"Symbol documents: {len(documents)}")
    print()

    load_start = perf_counter()

    model = SentenceTransformerEmbeddingModel(
        MODEL_NAME
    )

    model_load_seconds = (
        perf_counter() - load_start
    )

    semantic_index = SemanticIndex.build(
        documents,
        model=model,
    )

    print(
        "Model load: "
        f"{model_load_seconds:.3f}s"
    )
    print(
        "Corpus indexing: "
        f"{semantic_index.stats.indexing_seconds:.3f}s"
    )
    print(
        "Embedding dimension: "
        f"{semantic_index.stats.embedding_dimension}"
    )
    print()

    task_records: list[dict[str, Any]] = []

    budget_names = [
        *(str(limit) for limit in FIXED_LIMITS),
        "all",
    ]

    aggregate: dict[str, dict[str, float | int]] = {
        name: {
            "coverage_hits": 0,
            "characters": 0,
            "evidence_items": 0,
            "unique_files": 0,
        }
        for name in budget_names
    }

    for task in tasks:
        routed = retrieve_routed(
            task["task"],
            repository_index=repository_index,
            semantic_index=semantic_index,
            model=model,
            semantic_limit=len(documents),
        )

        retrieved = unique_file_results(
            routed.results
        )

        expected_file = task["expected_file"]

        budgets: dict[str, dict[str, Any]] = {}

        limits: list[tuple[str, int]] = [
            *((
                str(limit),
                limit,
            ) for limit in FIXED_LIMITS),
            (
                "all",
                max(1, len(retrieved)),
            ),
        ]

        for budget_name, limit in limits:
            bundle = select_by_evidence_count(
                retrieved,
                limit=limit,
            )

            bundle_results = tuple(
                item.retrieval_result
                for item in bundle.evidence
            )

            covered = expected_file_present(
                bundle_results,
                expected_file,
            )

            if covered:
                aggregate[budget_name][
                    "coverage_hits"
                ] += 1

            aggregate[budget_name][
                "characters"
            ] += bundle.character_count

            aggregate[budget_name][
                "evidence_items"
            ] += bundle.evidence_count

            aggregate[budget_name][
                "unique_files"
            ] += bundle.unique_file_count

            budgets[budget_name] = {
                "covered": covered,
                "character_count": (
                    bundle.character_count
                ),
                "evidence_count": (
                    bundle.evidence_count
                ),
                "unique_file_count": (
                    bundle.unique_file_count
                ),
                "evidence": [
                    {
                        "path": str(
                            item.retrieval_result
                            .document.path
                        ),
                        "symbol": (
                            item.retrieval_result
                            .document.symbol
                        ),
                        "score": (
                            item.retrieval_result.score
                        ),
                    }
                    for item in bundle.evidence
                ],
            }

        task_records.append(
            {
                "id": task["id"],
                "category": task["category"],
                "task": task["task"],
                "expected_file": expected_file,
                "route": routed.route.value,
                "matched_symbol": (
                    routed.matched_symbol
                ),
                "available_unique_files": (
                    len(retrieved)
                ),
                "budgets": budgets,
            }
        )

        print(
            f"{task['id']}: "
            f"route={routed.route.value}"
        )

        for budget_name in budget_names:
            budget = budgets[budget_name]

            print(
                f"  budget={budget_name:>3} "
                f"coverage="
                f"{'PASS' if budget['covered'] else 'FAIL'} "
                f"items={budget['evidence_count']} "
                f"chars={budget['character_count']}"
            )

    task_count = len(tasks)

    summaries: dict[str, dict[str, Any]] = {}

    for budget_name in budget_names:
        values = aggregate[budget_name]

        coverage_hits = int(
            values["coverage_hits"]
        )

        summaries[budget_name] = {
            "coverage_hits": coverage_hits,
            "coverage": (
                coverage_hits / task_count
                if task_count
                else 0.0
            ),
            "average_characters": (
                int(values["characters"])
                / task_count
                if task_count
                else 0.0
            ),
            "average_evidence_items": (
                int(values["evidence_items"])
                / task_count
                if task_count
                else 0.0
            ),
            "average_unique_files": (
                int(values["unique_files"])
                / task_count
                if task_count
                else 0.0
            ),
        }

    output = {
        "configuration": {
            "model": MODEL_NAME,
            "representation": "symbol",
            "routing": (
                "exact-symbol-or-semantic"
            ),
            "document_count": len(documents),
            "embedding_dimension": (
                semantic_index.stats
                .embedding_dimension
            ),
            "model_load_seconds": (
                model_load_seconds
            ),
            "indexing_seconds": (
                semantic_index.stats
                .indexing_seconds
            ),
            "fixed_limits": list(
                FIXED_LIMITS
            ),
        },
        "summary": summaries,
        "tasks": task_records,
    }

    RESULTS_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    output_path = (
        RESULTS_DIR
        / "evidence-count-run-001.json"
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

    for budget_name in budget_names:
        summary = summaries[
            budget_name
        ]

        print(
            f"Budget {budget_name:>3}: "
            f"coverage="
            f"{summary['coverage_hits']}"
            f"/{task_count} "
            f"({summary['coverage']:.1%}) "
            f"avg_chars="
            f"{summary['average_characters']:.1f} "
            f"avg_items="
            f"{summary['average_evidence_items']:.2f} "
            f"avg_files="
            f"{summary['average_unique_files']:.2f}"
        )

    print()
    print(f"Results: {output_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())