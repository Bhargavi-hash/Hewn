from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
MODULE_ROOT = (
    ROOT / "research" / "008-planning-subagents"
)
MANIFEST_PATH = (
    MODULE_ROOT / "fixtures" / "manifest.json"
)
ORACLES_PATH = (
    MODULE_ROOT / "fixtures" / "oracles.json"
)


def load_json(path: Path) -> Any:
    return json.loads(
        path.read_text(encoding="utf-8")
    )


def require_string_map(
    value: Any,
    *,
    name: str,
) -> dict[str, str]:
    if not isinstance(value, dict):
        raise TypeError(
            f"{name} must be an object"
        )

    result: dict[str, str] = {}

    for key, item in value.items():
        if not isinstance(key, str):
            raise TypeError(
                f"{name} keys must be strings"
            )

        if not isinstance(item, str):
            raise TypeError(
                f"{name} values must be strings"
            )

        result[key] = item

    return result


def materialize(
    root: Path,
    files: dict[str, str],
    oracle: str,
) -> None:
    for relative, source in files.items():
        path = root / relative
        path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )
        path.write_text(
            source,
            encoding="utf-8",
        )

    oracle_path = (
        root / "__hewn_oracle__"
        / "test_behavior.py"
    )
    oracle_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )
    oracle_path.write_text(
        oracle,
        encoding="utf-8",
    )


def run_oracle(root: Path) -> bool:
    env = {
        "PYTHONPATH": str(root / "src"),
    }

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "-q",
            "__hewn_oracle__/test_behavior.py",
        ],
        cwd=root,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    return result.returncode == 0


def main() -> None:
    manifest = load_json(MANIFEST_PATH)
    oracles = require_string_map(
        load_json(ORACLES_PATH),
        name="oracles",
    )

    if not isinstance(manifest, dict):
        raise TypeError(
            "manifest must be an object"
        )

    raw_tasks = manifest.get("tasks")

    if not isinstance(raw_tasks, list):
        raise TypeError(
            "tasks must be a list"
        )

    task_ids: set[str] = set()

    for raw_task in raw_tasks:
        if not isinstance(raw_task, dict):
            raise TypeError(
                "each task must be an object"
            )

        task_id = raw_task.get("task_id")

        if not isinstance(task_id, str):
            raise TypeError(
                "task_id must be a string"
            )

        task_ids.add(task_id)

        files = require_string_map(
            raw_task.get("files"),
            name=f"{task_id}.files",
        )

        oracle = oracles.get(task_id)

        if oracle is None:
            raise ValueError(
                f"missing oracle for {task_id}"
            )

        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            materialize(
                root,
                files,
                oracle,
            )

            passed = run_oracle(root)

        status = (
            "PASS"
            if passed
            else "FAIL"
        )

        print(
            f"{task_id}: pristine oracle {status}"
        )

        if passed:
            raise AssertionError(
                f"{task_id}: pristine fixture "
                "already satisfies oracle"
            )

    extra = set(oracles) - task_ids

    if extra:
        raise ValueError(
            "oracles exist for unknown tasks: "
            f"{sorted(extra)}"
        )

    print()
    print(
        "All 8 pristine fixtures fail their "
        "hidden behavioral oracle."
    )


if __name__ == "__main__":
    main()