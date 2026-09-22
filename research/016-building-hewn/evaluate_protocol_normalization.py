from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

from hewn.model_protocol import (
    ModelProtocolError,
    ParseSource,
    parse_model_response_with_provenance,
)
from hewn.models import FinalResponse
from hewn.tools import ToolCall


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []

    with path.open() as handle:
        for line in handle:
            line = line.strip()
            if line:
                rows.append(json.loads(line))

    return rows


def evaluate_row(row: dict[str, Any]) -> dict[str, Any]:
    raw = row["raw"]
    expected = row["expected"]

    try:
        parsed = parse_model_response_with_provenance(raw)
    except ModelProtocolError:
        actual = "rejected"
        rule = None
        response = None
    else:
        actual = (
            "canonical"
            if parsed.source is ParseSource.CANONICAL
            else "normalized"
        )
        rule = parsed.normalization_rule
        response = parsed.response

    correct = actual == expected

    if correct and expected == "normalized":
        correct = rule == row["expected_rule"]

    if correct and expected in {"canonical", "normalized"}:
        if "expected_name" in row:
            correct = (
                isinstance(response, ToolCall)
                and response.name == row["expected_name"]
                and response.arguments
                == row["expected_arguments"]
            )
        elif "expected_text" in row:
            correct = (
                isinstance(response, FinalResponse)
                and response.text == row["expected_text"]
            )

    return {
        "id": row["id"],
        "category": row["category"],
        "expected": expected,
        "actual": actual,
        "normalization_rule": rule,
        "correct": correct,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--eval", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    rows = load_jsonl(args.eval)
    records = [evaluate_row(row) for row in rows]

    expected_counts = Counter(
        record["expected"] for record in records
    )
    actual_counts = Counter(
        record["actual"] for record in records
    )
    category_counts = Counter(
        record["category"] for record in records
    )

    correct = sum(
        bool(record["correct"])
        for record in records
    )

    failures = [
        record
        for record in records
        if not record["correct"]
    ]

    output = {
        "note": (
            "Fresh Module 16 deterministic protocol-boundary "
            "validation fixture, frozen before model evaluation."
        ),
        "rows": len(records),
        "correct": correct,
        "accuracy": (
            correct / len(records)
            if records
            else 0.0
        ),
        "expected_counts": dict(
            sorted(expected_counts.items())
        ),
        "actual_counts": dict(
            sorted(actual_counts.items())
        ),
        "category_counts": dict(
            sorted(category_counts.items())
        ),
        "failures": failures,
        "records": records,
    }

    args.out.parent.mkdir(
        parents=True,
        exist_ok=True,
    )
    args.out.write_text(
        json.dumps(output, indent=2) + "\n"
    )

    print(f"Wrote {args.out}")
    print(f"rows={len(records)}")
    print(f"correct={correct}")
    print(
        "accuracy="
        f"{output['accuracy']:.3f}"
    )

    if failures:
        print("failures:")
        for failure in failures:
            print(
                f"  {failure['id']}: "
                f"expected={failure['expected']} "
                f"actual={failure['actual']}"
            )


if __name__ == "__main__":
    main()
