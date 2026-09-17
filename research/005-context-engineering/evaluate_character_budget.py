from __future__ import annotations

import json
from pathlib import Path
from time import perf_counter
from typing import Any

from hewn.context.character_budget import (
    select_by_character_budget,
)
from hewn.repository.index import RepositoryIndex
from hewn.retrieval.models import RetrievalResult
from hewn.retrieval.router import retrieve_routed
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

CHARACTER_BUDGETS = (100, 200, 400, 800)


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


def bundle_contains_expected_file(
    results: tuple[RetrievalResult, ...],
    expected_file: str,
) -> bool:
    return any(
        str(result.document.path) == expected_file
        for result in results
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
    print(
        "Character budgets: "
        + ", ".join(
            str(budget)
            for budget in CHARACTER_BUDGETS
        )
        + ", unlimited"
    )
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

    budget_names = [
        *(str(budget) for budget in CHARACTER_BUDGETS),
        "unlimited",
    ]

    aggregate: dict[str, dict[str, int]] = {
        name: {
            "coverage_hits": 0,
            "characters": 0,
            "evidence_items": 0,
            "unique_files": 0,
            "over_budget_tasks": 0,
        }
        for name in budget_names
    }

    task_records: list[dict[str, Any]] = []

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

        for budget in CHARACTER_BUDGETS:
            bundle = select_by_character_budget(
                retrieved,
                budget=budget,
            )

            bundle_results = tuple(
                item.retrieval_result
                for item in bundle.evidence
            )

            covered = bundle_contains_expected_file(
                bundle_results,
                expected_file,
            )

            over_budget = (
                bundle.character_count > budget
            )

            name = str(budget)

            if covered:
                aggregate[name][
                    "coverage_hits"
                ] += 1

            if over_budget:
                aggregate[name][
                    "over_budget_tasks"
                ] += 1

            aggregate[name][
                "characters"
            ] += bundle.character_count

            aggregate[name][
                "evidence_items"
            ] += bundle.evidence_count

            aggregate[name][
                "unique_files"
            ] += bundle.unique_file_count

            budgets[name] = {
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
                "over_budget": over_budget,
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

        unlimited_results = retrieved

        unlimited_characters = sum(
            len(result.document.text)
            for result in unlimited_results
        )

        unlimited_covered = (
            bundle_contains_expected_file(
                unlimited_results,
                expected_file,
            )
        )

        if unlimited_covered:
            aggregate["unlimited"][
                "coverage_hits"
            ] += 1

        aggregate["unlimited"][
            "characters"
        ] += unlimited_characters

        aggregate["unlimited"][
            "evidence_items"
        ] += len(unlimited_results)

        aggregate["unlimited"][
            "unique_files"
        ] += len(unlimited_results)

        budgets["unlimited"] = {
            "covered": unlimited_covered,
            "character_count": (
                unlimited_characters
            ),
            "evidence_count": (
                len(unlimited_results)
            ),
            "unique_file_count": (
                len(unlimited_results)
            ),
            "over_budget": False,
            "evidence": [
                {
                    "path": str(
                        result.document.path
                    ),
                    "symbol": (
                        result.document.symbol
                    ),
                    "score": result.score,
                }
                for result in unlimited_results
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

        for name in budget_names:
            record = budgets[name]

            over_text = (
                " OVER"
                if record["over_budget"]
                else ""
            )

            print(
                f"  budget={name:>9} "
                f"coverage="
                f"{'PASS' if record['covered'] else 'FAIL'} "
                f"items={record['evidence_count']} "
                f"chars={record['character_count']}"
                f"{over_text}"
            )

    task_count = len(tasks)

    summaries: dict[str, dict[str, Any]] = {}

    for name in budget_names:
        values = aggregate[name]

        coverage_hits = values[
            "coverage_hits"
        ]

        summaries[name] = {
            "coverage_hits": coverage_hits,
            "coverage": (
                coverage_hits / task_count
                if task_count
                else 0.0
            ),
            "average_characters": (
                values["characters"]
                / task_count
                if task_count
                else 0.0
            ),
            "average_evidence_items": (
                values["evidence_items"]
                / task_count
                if task_count
                else 0.0
            ),
            "average_unique_files": (
                values["unique_files"]
                / task_count
                if task_count
                else 0.0
            ),
            "over_budget_tasks": (
                values["over_budget_tasks"]
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
            "character_budgets": list(
                CHARACTER_BUDGETS
            ),
            "atomic_evidence_policy": (
                "always-keep-first-then-skip-non-fitting"
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
        / "character-budget-run-001.json"
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

    for name in budget_names:
        summary = summaries[name]

        print(
            f"Budget {name:>9}: "
            f"coverage="
            f"{summary['coverage_hits']}"
            f"/{task_count} "
            f"({summary['coverage']:.1%}) "
            f"avg_chars="
            f"{summary['average_characters']:.1f} "
            f"avg_items="
            f"{summary['average_evidence_items']:.2f} "
            f"over_budget="
            f"{summary['over_budget_tasks']}"
        )

    print()
    print(f"Results: {output_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())