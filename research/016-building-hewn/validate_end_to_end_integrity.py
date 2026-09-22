from __future__ import annotations

import argparse
import ast
import json
from pathlib import Path
from typing import Any


def load_cases(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text().splitlines()
        if line.strip()
    ]


def repository_text(root: Path) -> str:
    parts: list[str] = []

    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue

        try:
            content = path.read_text()
        except UnicodeDecodeError:
            continue

        parts.append(str(path.relative_to(root)))
        parts.append(content)

    return "\n".join(parts)


def hidden_markers(test_file: Path) -> tuple[str, ...]:
    source = test_file.read_text()
    tree = ast.parse(source)

    markers: list[str] = []

    for node in tree.body:
        if not isinstance(
            node,
            (ast.FunctionDef, ast.AsyncFunctionDef),
        ):
            continue

        segment = ast.get_source_segment(source, node)

        if segment is not None:
            markers.append(segment.strip())

    return tuple(markers)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cases", type=Path, required=True)
    parser.add_argument("--fixtures", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    cases = load_cases(args.cases)
    records: list[dict[str, Any]] = []

    for case in cases:
        fixture = args.fixtures / case["fixture"]
        repository = fixture / "repository"
        evaluator = fixture / "evaluator" / "test_task.py"

        visible = repository_text(repository)
        markers = hidden_markers(evaluator)

        exposed = tuple(
            marker
            for marker in markers
            if marker in visible
        )

        evaluator_inside_repository = any(
            path.name == "evaluator_tests"
            or path.name == "evaluator"
            for path in repository.rglob("*")
        )

        reference_inside_repository = any(
            path.name == "reference"
            for path in repository.rglob("*")
        )

        correct = (
            bool(markers)
            and not exposed
            and not evaluator_inside_repository
            and not reference_inside_repository
        )

        records.append(
            {
                "task_id": case["task_id"],
                "hidden_marker_count": len(markers),
                "exposed_markers": list(exposed),
                "evaluator_inside_repository": (
                    evaluator_inside_repository
                ),
                "reference_inside_repository": (
                    reference_inside_repository
                ),
                "correct": correct,
            }
        )

    valid = sum(
        bool(record["correct"])
        for record in records
    )

    result = {
        "tasks": len(records),
        "valid": valid,
        "all_valid": valid == len(records),
        "records": records,
    }

    args.out.parent.mkdir(
        parents=True,
        exist_ok=True,
    )
    args.out.write_text(
        json.dumps(result, indent=2) + "\n"
    )

    print(f"tasks={len(records)}")
    print(f"valid={valid}")
    print(f"all_valid={result['all_valid']}")

    for record in records:
        status = "PASS" if record["correct"] else "FAIL"
        print(f"{status} {record['task_id']}")

    if not result["all_valid"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()