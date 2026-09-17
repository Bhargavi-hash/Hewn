from __future__ import annotations

import argparse
import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

from hewn.repository.index import RepositoryIndex
from hewn.retrieval.bm25 import retrieve_bm25
from hewn.retrieval.documents import (
    build_repository_documents,
)
from hewn.retrieval.lexical import retrieve_lexical
from hewn.retrieval.models import (
    RepositoryDocument,
    RetrievalResult,
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

Retriever = Callable[
    [str, tuple[RepositoryDocument, ...]],
    tuple[RetrievalResult, ...],
]


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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--retriever",
        choices=(
            "lexical",
            "bm25",
        ),
        required=True,
    )

    parser.add_argument(
        "--representation",
        choices=(
            "file",
            "symbol",
        ),
        default="file",
    )

    parser.add_argument(
        "--output",
        required=True,
    )

    return parser.parse_args()


def make_retriever(
    name: str,
    *,
    limit: int,
) -> Retriever:
    if name == "lexical":

        def lexical(
            query: str,
            documents: tuple[
                RepositoryDocument,
                ...,
            ],
        ) -> tuple[
            RetrievalResult,
            ...,
        ]:
            return retrieve_lexical(
                query,
                documents,
                limit=limit,
            )

        return lexical

    if name == "bm25":

        def bm25(
            query: str,
            documents: tuple[
                RepositoryDocument,
                ...,
            ],
        ) -> tuple[
            RetrievalResult,
            ...,
        ]:
            return retrieve_bm25(
                query,
                documents,
                limit=limit,
            )

        return bm25

    raise ValueError(
        f"Unknown retriever: {name}"
    )


def build_documents(
    repository_index: RepositoryIndex,
    representation: str,
) -> tuple[RepositoryDocument, ...]:
    if representation == "file":
        return build_repository_documents(
            repository_index,
            path_prefix="src/hewn",
        )

    if representation == "symbol":
        return build_symbol_documents(
            repository_index,
            path_prefix="src/hewn",
        )

    raise ValueError(
        "Unknown representation: "
        f"{representation}"
    )


def unique_file_results(
    results: tuple[
        RetrievalResult,
        ...,
    ],
) -> tuple[RetrievalResult, ...]:
    seen_paths: set[str] = set()
    unique: list[RetrievalResult] = []

    for result in results:
        path = str(
            result.document.path
        )

        if path in seen_paths:
            continue

        seen_paths.add(path)
        unique.append(result)

    return tuple(unique)


def result_payload(
    result: RetrievalResult,
) -> dict[str, Any]:
    return {
        "path": str(
            result.document.path
        ),
        "symbol": (
            result.document.symbol
        ),
        "score": result.score,
    }


def main() -> int:
    args = parse_args()
    tasks = load_tasks()

    repository_index = (
        RepositoryIndex.build(
            REPO_ROOT
        )
    )

    documents = build_documents(
        repository_index,
        args.representation,
    )

    retriever = make_retriever(
        args.retriever,
        limit=len(documents),
    )

    results: list[
        dict[str, Any]
    ] = []

    top_1_hits = 0
    top_3_hits = 0

    top_1_characters_total = 0
    top_3_characters_total = 0

    for task in tasks:
        raw_retrieved = retriever(
            task["task"],
            documents,
        )

        retrieved = unique_file_results(
            raw_retrieved
        )

        expected_file = (
            task["expected_file"]
        )

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
                expected_score = (
                    result.score
                )
                expected_symbol = (
                    result.document.symbol
                )
                break

        top_1 = retrieved[:1]
        top_3 = retrieved[:3]

        top_1_paths = [
            str(result.document.path)
            for result in top_1
        ]

        top_3_paths = [
            str(result.document.path)
            for result in top_3
        ]

        top_1_success = (
            expected_file
            in top_1_paths
        )

        top_3_success = (
            expected_file
            in top_3_paths
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
                "category": (
                    task["category"]
                ),
                "task": task["task"],
                "expected_file": (
                    expected_file
                ),
                "expected_rank": (
                    expected_rank
                ),
                "expected_score": (
                    expected_score
                ),
                "expected_symbol": (
                    expected_symbol
                ),
                "top_1_success": (
                    top_1_success
                ),
                "top_3_success": (
                    top_3_success
                ),
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
            f"{'PASS' if top_3_success else 'FAIL'}"
        )

        for rank, result in enumerate(
            top_3,
            start=1,
        ):
            symbol_text = (
                f" "
                f"symbol={result.document.symbol}"
                if result.document.symbol
                is not None
                else ""
            )

            print(
                f"  {rank}. "
                f"{result.document.path}"
                f"{symbol_text} "
                f"score={result.score:.4f}"
            )

    task_count = len(tasks)

    summary = {
        "retriever": (
            args.retriever
        ),
        "representation": (
            args.representation
        ),
        "task_count": task_count,
        "document_count": (
            len(documents)
        ),
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
        "average_top_1_characters": (
            top_1_characters_total
            / task_count
            if task_count
            else 0.0
        ),
        "average_top_3_characters": (
            top_3_characters_total
            / task_count
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
        / args.output
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
    print(
        f"Retriever: "
        f"{args.retriever}"
    )
    print(
        f"Representation: "
        f"{args.representation}"
    )
    print(
        f"Top-1: "
        f"{top_1_hits}/{task_count} "
        f"({summary['top_1_accuracy']:.1%})"
    )
    print(
        f"Top-3: "
        f"{top_3_hits}/{task_count} "
        f"({summary['top_3_accuracy']:.1%})"
    )
    print(
        "Average Top-1 context: "
        f"{summary['average_top_1_characters']:.1f} "
        "chars"
    )
    print(
        "Average Top-3 context: "
        f"{summary['average_top_3_characters']:.1f} "
        "chars"
    )
    print(
        f"Documents: "
        f"{len(documents)}"
    )
    print(
        f"Results: {output_path}"
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())