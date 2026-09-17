from __future__ import annotations

import json
from pathlib import Path
from time import perf_counter
from typing import Any

from hewn.repository.index import RepositoryIndex
from hewn.retrieval.models import RetrievalResult
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


def result_payload(
    result: RetrievalResult,
) -> dict[str, Any]:
    return {
        "path": str(result.document.path),
        "symbol": result.document.symbol,
        "score": result.score,
    }


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

    results: list[dict[str, Any]] = []

    top_1_hits = 0
    top_3_hits = 0

    top_1_characters_total = 0
    top_3_characters_total = 0

    query_seconds_total = 0.0

    for task in tasks:
        start = perf_counter()

        raw_results = semantic_index.retrieve(
            task["task"],
            model=model,
            limit=len(documents),
        )

        query_seconds = (
            perf_counter() - start
        )

        query_seconds_total += query_seconds

        retrieved = unique_file_results(
            raw_results
        )

        expected_file = task["expected_file"]

        expected_rank: int | None = None
        expected_score: float | None = None
        expected_symbol: str | None = None

        for rank, result in enumerate(
            retrieved,
            start=1,
        ):
            if (
                str(result.document.path)
                == expected_file
            ):
                expected_rank = rank
                expected_score = result.score
                expected_symbol = (
                    result.document.symbol
                )
                break

        top_1 = retrieved[:1]
        top_3 = retrieved[:3]

        top_1_success = any(
            str(result.document.path)
            == expected_file
            for result in top_1
        )

        top_3_success = any(
            str(result.document.path)
            == expected_file
            for result in top_3
        )

        if top_1_success:
            top_1_hits += 1

        if top_3_success:
            top_3_hits += 1

        top_1_characters = sum(
            len(result.document.text)
            for result in top_1
        )

        top_3_characters = sum(
            len(result.document.text)
            for result in top_3
        )

        top_1_characters_total += (
            top_1_characters
        )

        top_3_characters_total += (
            top_3_characters
        )

        results.append(
            {
                "id": task["id"],
                "category": task["category"],
                "task": task["task"],
                "expected_file": expected_file,
                "expected_rank": expected_rank,
                "expected_score": expected_score,
                "expected_symbol": expected_symbol,
                "query_seconds": query_seconds,
                "top_1_success": top_1_success,
                "top_3_success": top_3_success,
                "top_1": [
                    result_payload(result)
                    for result in top_1
                ],
                "top_3": [
                    result_payload(result)
                    for result in top_3
                ],
                "top_1_characters": (
                    top_1_characters
                ),
                "top_3_characters": (
                    top_3_characters
                ),
            }
        )

        rank_text = (
            str(expected_rank)
            if expected_rank is not None
            else "not-found"
        )

        print(
            f"{task['id']}: "
            f"expected={expected_file} "
            f"rank={rank_text} "
            f"top1="
            f"{'PASS' if top_1_success else 'FAIL'} "
            f"top3="
            f"{'PASS' if top_3_success else 'FAIL'} "
            f"query={query_seconds:.4f}s"
        )

        for rank, result in enumerate(
            top_3,
            start=1,
        ):
            print(
                f"  {rank}. "
                f"{result.document.path} "
                f"symbol={result.document.symbol} "
                f"score={result.score:.4f}"
            )

    task_count = len(tasks)

    summary = {
        "model": MODEL_NAME,
        "representation": "symbol",
        "document_count": len(documents),
        "embedding_dimension": (
            semantic_index.stats.embedding_dimension
        ),
        "model_load_seconds": (
            model_load_seconds
        ),
        "indexing_seconds": (
            semantic_index.stats.indexing_seconds
        ),
        "task_count": task_count,
        "top_1_hits": top_1_hits,
        "top_1_accuracy": (
            top_1_hits / task_count
            if task_count
            else 0.0
        ),
        "top_3_hits": top_3_hits,
        "top_3_accuracy": (
            top_3_hits / task_count
            if task_count
            else 0.0
        ),
        "average_query_seconds": (
            query_seconds_total / task_count
            if task_count
            else 0.0
        ),
        "average_top_1_characters": (
            top_1_characters_total / task_count
            if task_count
            else 0.0
        ),
        "average_top_3_characters": (
            top_3_characters_total / task_count
            if task_count
            else 0.0
        ),
    }

    output = {
        "summary": summary,
        "results": results,
    }

    RESULTS_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    output_path = (
        RESULTS_DIR
        / "semantic-bge-small-symbol-run-001.json"
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
    print(f"Model: {MODEL_NAME}")
    print(
        f"Top-1: {top_1_hits}/{task_count} "
        f"({summary['top_1_accuracy']:.1%})"
    )
    print(
        f"Top-3: {top_3_hits}/{task_count} "
        f"({summary['top_3_accuracy']:.1%})"
    )
    print(
        "Average query time: "
        f"{summary['average_query_seconds']:.4f}s"
    )
    print(
        "Average Top-1 context: "
        f"{summary['average_top_1_characters']:.1f} chars"
    )
    print(
        "Average Top-3 context: "
        f"{summary['average_top_3_characters']:.1f} chars"
    )
    print(
        f"Results: {output_path}"
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())