from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from hewn.context.source import (
    build_mixed_document,
    build_source_document,
    resolve_document_symbol,
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

REPO_ROOT = Path(__file__).resolve().parents[2]

TASKS_PATH = (
    REPO_ROOT
    / "research"
    / "002-tools"
    / "tasks.json"
)

RESULTS_DIR = Path(__file__).with_name("results")

MODEL_NAME = "BAAI/bge-small-en-v1.5"

EVIDENCE_LIMIT = 3

REPRESENTATIONS = (
    "structure",
    "source",
    "mixed",
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


def represent_document(
    *,
    representation: str,
    structural_document: RepositoryDocument,
    repository_index: RepositoryIndex,
) -> RepositoryDocument:
    if representation == "structure":
        return structural_document

    symbol = resolve_document_symbol(
        structural_document,
        repository_index,
    )

    source_document = build_source_document(
        repository_root=REPO_ROOT,
        symbol=symbol,
    )

    if representation == "source":
        return source_document

    if representation == "mixed":
        return build_mixed_document(
            structural_document=(
                structural_document
            ),
            source_document=source_document,
        )

    raise ValueError(
        f"Unknown representation: "
        f"{representation}"
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
        f"Evidence limit: {EVIDENCE_LIMIT} "
        "unique files"
    )
    print()

    model = SentenceTransformerEmbeddingModel(
        MODEL_NAME
    )

    semantic_index = SemanticIndex.build(
        documents,
        model=model,
    )

    totals: dict[str, dict[str, int]] = {
        representation: {
            "characters": 0,
            "evidence_items": 0,
            "coverage_hits": 0,
        }
        for representation in REPRESENTATIONS
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

        unique_results = unique_file_results(
            routed.results
        )

        selected = unique_results[
            :EVIDENCE_LIMIT
        ]

        expected_file = task["expected_file"]

        expected_covered = any(
            str(result.document.path)
            == expected_file
            for result in selected
        )

        representations: dict[
            str,
            dict[str, Any],
        ] = {}

        print(
            f"{task['id']}: "
            f"route={routed.route.value} "
            f"coverage="
            f"{'PASS' if expected_covered else 'FAIL'}"
        )

        for representation in REPRESENTATIONS:
            represented = tuple(
                represent_document(
                    representation=representation,
                    structural_document=(
                        result.document
                    ),
                    repository_index=(
                        repository_index
                    ),
                )
                for result in selected
            )

            character_count = sum(
                len(document.text)
                for document in represented
            )

            totals[representation][
                "characters"
            ] += character_count

            totals[representation][
                "evidence_items"
            ] += len(represented)

            if expected_covered:
                totals[representation][
                    "coverage_hits"
                ] += 1

            representations[
                representation
            ] = {
                "character_count": (
                    character_count
                ),
                "evidence_count": (
                    len(represented)
                ),
                "evidence": [
                    {
                        "path": str(
                            document.path
                        ),
                        "symbol": (
                            document.symbol
                        ),
                        "characters": (
                            len(document.text)
                        ),
                    }
                    for document in represented
                ],
            }

            print(
                f"  {representation:>9}: "
                f"items={len(represented)} "
                f"chars={character_count}"
            )

        task_records.append(
            {
                "id": task["id"],
                "category": task["category"],
                "task": task["task"],
                "route": routed.route.value,
                "expected_file": expected_file,
                "expected_covered": (
                    expected_covered
                ),
                "representations": (
                    representations
                ),
            }
        )

    task_count = len(tasks)

    summary: dict[str, dict[str, Any]] = {}

    for representation in REPRESENTATIONS:
        values = totals[representation]

        summary[representation] = {
            "coverage_hits": (
                values["coverage_hits"]
            ),
            "coverage": (
                values["coverage_hits"]
                / task_count
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
        }

    output = {
        "configuration": {
            "model": MODEL_NAME,
            "retrieval_representation": (
                "symbol"
            ),
            "context_representations": list(
                REPRESENTATIONS
            ),
            "evidence_limit": EVIDENCE_LIMIT,
            "document_count": len(documents),
            "ranking_policy": (
                "module-4-hybrid-frozen"
            ),
        },
        "summary": summary,
        "tasks": task_records,
    }

    RESULTS_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    output_path = (
        RESULTS_DIR
        / "representation-run-001.json"
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
        values = summary[representation]

        print(
            f"{representation:>9}: "
            f"coverage="
            f"{values['coverage_hits']}"
            f"/{task_count} "
            f"({values['coverage']:.1%}) "
            f"avg_chars="
            f"{values['average_characters']:.1f} "
            f"avg_items="
            f"{values['average_evidence_items']:.2f}"
        )

    print()
    print(f"Results: {output_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())