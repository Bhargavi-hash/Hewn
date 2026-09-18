from __future__ import annotations

import ast
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
MANIFEST = (
    ROOT
    / "research"
    / "008-planning-subagents"
    / "fixtures"
    / "manifest.json"
)

EXPECTED_CATEGORIES = {
    "same_file_multi_operation": 2,
    "cross_file_dependency": 2,
    "behavior_verification": 2,
    "dependency_reasoning": 2,
}


def load_manifest() -> dict[str, Any]:
    value = json.loads(MANIFEST.read_text())

    if not isinstance(value, dict):
        raise TypeError("Manifest must be an object")

    return value


def validate_python(
    *,
    task_id: str,
    path: str,
    source: str,
) -> None:
    if not path.endswith(".py"):
        return

    try:
        ast.parse(source)
    except SyntaxError as exc:
        raise ValueError(
            f"{task_id}: invalid Python in {path}: {exc}"
        ) from exc


def main() -> None:
    manifest = load_manifest()
    tasks = manifest.get("tasks")

    if not isinstance(tasks, list):
        raise TypeError("tasks must be a list")

    if manifest.get("task_count") != len(tasks):
        raise ValueError("task_count does not match tasks")

    if len(tasks) != 8:
        raise ValueError(
            f"Expected 8 tasks, found {len(tasks)}"
        )

    seen_ids: set[str] = set()
    category_counts: dict[str, int] = {}

    for task in tasks:
        if not isinstance(task, dict):
            raise TypeError("Each task must be an object")

        task_id = task.get("task_id")
        category = task.get("category")
        prompt = task.get("task")
        files = task.get("files")
        required_files = task.get("required_files")
        required_symbols = task.get("required_symbols")
        required_operations = task.get(
            "required_operations"
        )
        required_verification = task.get(
            "required_verification"
        )

        if not isinstance(task_id, str):
            raise TypeError("task_id must be a string")

        if task_id in seen_ids:
            raise ValueError(
                f"Duplicate task id: {task_id}"
            )

        seen_ids.add(task_id)

        if not isinstance(category, str):
            raise TypeError(
                f"{task_id}: category must be a string"
            )

        category_counts[category] = (
            category_counts.get(category, 0) + 1
        )

        if not isinstance(prompt, str) or not prompt.strip():
            raise ValueError(
                f"{task_id}: task must be non-empty"
            )

        if not isinstance(files, dict) or not files:
            raise ValueError(
                f"{task_id}: files must be non-empty"
            )

        for path, source in files.items():
            if not isinstance(path, str):
                raise TypeError(
                    f"{task_id}: file path must be a string"
                )

            if not isinstance(source, str):
                raise TypeError(
                    f"{task_id}: source must be a string"
                )

            validate_python(
                task_id=task_id,
                path=path,
                source=source,
            )

        list_fields = {
            "required_files": required_files,
            "required_symbols": required_symbols,
            "required_operations": required_operations,
            "required_verification": required_verification,
        }

        validated_lists: dict[str, list[str]] = {}

        for name, values in list_fields.items():
            if not isinstance(values, list) or not values:
                raise ValueError(
                    f"{task_id}: {name} must be a "
                    "non-empty list"
                )

            if not all(
                isinstance(value, str) and value
                for value in values
            ):
                raise TypeError(
                    f"{task_id}: {name} must contain "
                    "non-empty strings"
                )

            validated_lists[name] = values

        required_file_paths = validated_lists[
            "required_files"
        ]
        available_paths = set(files)

        missing_required = (
            set(required_file_paths) - available_paths
        )

        if missing_required:
            raise ValueError(
                f"{task_id}: required files missing "
                f"from fixture: "
                f"{sorted(missing_required)}"
            )

        

    if category_counts != EXPECTED_CATEGORIES:
        raise ValueError(
            "Unexpected category distribution: "
            f"{category_counts}"
        )

    print("Module 8 fixture validation")
    print(f"Tasks: {len(tasks)}")

    for category in sorted(category_counts):
        print(
            f"{category}: "
            f"{category_counts[category]}"
        )

    print("All fixture source parses successfully.")
    print("All fixture manifests are structurally valid.")


if __name__ == "__main__":
    main()